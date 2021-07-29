import base64
import json
import logging
import os
import typing as T
import uuid

from pygls import uris
from pygls.lsp.types import (ConfigurationItem, ConfigurationParams, Range, Location, Position,
							 Unregistration, UnregistrationParams,
							 MessageType)
from pygls.server import LanguageServer

from backend.sql_index_manager import SQLAnchor, SQLSymbol
from frontend import VeribleIndexer
from frontend import VeribleSyntaxChecker

logger = logging.getLogger("myLogger")

class DiplomatLanguageServer(LanguageServer):
	CMD_INDEX_WORKSPACE = 'diplomat-server.reindex'
	CMD_GET_CONFIGURATION = "diplomat-server.get-configuration"
	CMD_REORDER = "diplomat-server.reorder-files"
	CMD_REINDEX = 'diplomat-server.full-index'
	CMD_TST_PROGRESS_STRT = 'diplomat-server.test.start-progress'
	CMD_TST_PROGRESS_STOP = 'diplomat-server.test.stop-progress'
	CMD_DBG_DUMP_INDEX_DB = 'diplomat-server.dbg.dump-index'

	CONFIGURATION_SECTION = 'diplomatServer'

	def __init__(self):
		super().__init__()
		self.index_path = ""
		self.flist_path = ""
		self.skip_index = False
		self.indexed = False
		self.configured = False
		self.svindexer = VeribleIndexer(None)
		self.syntaxchecker = VeribleSyntaxChecker()
		self.progress_uuid = None
		self.debug = False
		self.check_syntax = False
		self.config = None

	def set_static_configuration(self,config : str ,base64_encoded = False):
		"""
		Override VSCode configuration system with a static config.
		:param config: A JSON string representing the configuration.
		:param base64_encoded: True if the configuration is base64-encoded
		"""
		config_string = config
		if base64_encoded :
			config_string = base64.standard_b64decode(config)
		self.config = json.loads(config_string)
		self.config["usePrebuiltIndex"] = True if self.config["usePrebuiltIndex"].lower() == "true" else False

	def process_configuration(self, config):
		self.svindexer.workspace_root = self.workspace.root_path
		verible_root = config["backend"]["veribleInstallPath"]
		self.index_path = config["indexFilePath"]
		self.flist_path = config["fileListPath"]

		verible_root = os.path.expanduser(os.path.expandvars(verible_root))
		self.flist_path = os.path.expanduser(os.path.expandvars(self.flist_path))

		verible_root += "/" if verible_root != "" and verible_root[-1] not in ["\\", "/"] else ""
		self.svindexer.exec_root = verible_root
		self.syntaxchecker.executable = f"{verible_root}verible-verilog-syntax"

		if not os.path.isabs(os.path.realpath(self.flist_path)):
			self.flist_path = os.path.normpath(os.path.join(self.workspace.root_path, self.flist_path))
		self.svindexer.workspace_root = os.path.dirname(os.path.abspath(self.flist_path))
		self.skip_index = config["usePrebuiltIndex"]
		logger.info(f"Use prebuilt index : {'True' if self.skip_index else 'False'}")
		if not os.path.isabs(self.flist_path):
			self.flist_path = os.path.abspath(os.path.normpath(os.path.join(self.workspace.root_path, self.flist_path)))
		self.show_message_log(f"   FList path : {self.flist_path}")
		self.show_message_log(f"   WS root path : {self.svindexer.workspace_root}")
		logger.info(f"FList path : {self.flist_path}")
		logger.info(f"WS root path : {self.svindexer.workspace_root}")
		self.configured = True

	@property
	def have_syntax_error(self):
		return self.syntaxchecker.nberrors > 0

	def syntax_check(self,file : str):
		if file is not None :
			f = uris.to_fs_path(file)
			self.syntaxchecker.run_incremental([f])
		else :
			self.syntaxchecker.run()

		for file,diaglist in self.syntaxchecker.diagnostic_content.items() :
			self.publish_diagnostics(file,diaglist)

	def anchor_to_location(self,anchor : SQLAnchor) -> Location:
		file_path = self.svindexer.index.get_file_by_id(anchor.file).path

		begin_line = anchor.start_line
		begin_char = anchor.start_char
		end_line = anchor.end_line
		end_char = anchor.end_char

		return Location( uri=uris.from_fs_path(file_path),
						 range=Range(
			start=Position(line=begin_line, character=begin_char -1),
			end=Position(line=end_line,character=end_char - 1)))

	def get_symbol_from_location(self, selected_loc : Location) -> SQLSymbol:
		logger.debug(f"Query symbol for location {selected_loc}")
		#wsdoc = self.workspace.get_document(selected_loc.uri)
		db_file = self.svindexer.index.get_file_by_path(uris.to_fs_path(selected_loc.uri))

		anchors_by_pos : T.List[SQLAnchor] = self.svindexer.index.get_anchor_by_position(db_file.id,selected_loc.range.start.line,selected_loc.range.start.character)
		logger.debug(f"    Anchor found {anchors_by_pos}")
		if len(anchors_by_pos) == 0 :
			return None
		selected_anchor = min(anchors_by_pos,key=lambda x : len(x))
		if selected_anchor is not None :
			symbol = self.svindexer.index.get_definition_by_anchor(selected_anchor)
			return symbol
		else:
			return None

	def disable_update_config(self):
		self.show_message_log("   Removing dynamic configuration capabilities.")
		params = UnregistrationParams(unregistrations=[
			Unregistration(id=str(uuid.uuid4()), method=self.CMD_GET_CONFIGURATION)
		])
		reply = self.unregister_capability(params)
		if reply is None :
			self.show_message_log("   Success.")
		else :
			self.show_message_log(f"   Failure. Got reply : {reply}", MessageType.Error)
		pass

	def refresh_configuration(self):
		logger.debug("Refresh configuration")
		if self.config is not None :
			logger.debug("  Static configuration in place.")
			return self.config

		self.show_message_log("Configuration requested")
		config = self.get_configuration(ConfigurationParams(items=[
			ConfigurationItem(
				scope_uri='',
				section=DiplomatLanguageServer.CONFIGURATION_SECTION)
		])).result(2)[0]
		logger.debug("Got configuration back")
		self.show_message_log("Got client configuration.")
		return config

	def get_completion(self, document, position):
		ret = list()
		current_word = document.word_at_position(position)
		logger.debug(f"  Current word is {current_word}")
		word_start = Position(line=position.line, character=position.character - len(current_word))
		if word_start.character > 0:
			prev_char_offset = document.offset_at_position(word_start) - 1
			previous_char = document.source[prev_char_offset]
			logger.debug(f"  Previous char is {previous_char}")
			if previous_char == ".":
				# We need the parent and to find children
				parent_start = Position(line=word_start.line, character=word_start.character - 2)
				parent_name =document.word_at_position(parent_start)
				logger.debug(f"  Parent is {parent_name}")
				parent_symbol_list = self.svindexer.index.get_symbols_by_name( parent_name)
				logger.debug(f"   Found {parent_symbol_list}")
				children = list()
				for parent_symbol in parent_symbol_list :
					children.extend(self.svindexer.index.get_symbol_childs(parent_symbol))
				return [x.name for x in children if x.name.startswith(current_word)]

		return ret
