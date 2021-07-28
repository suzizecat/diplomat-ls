############################################################################
# Copyright(c) Open Law Library. All rights reserved.                      #
# See ThirdPartyNotices.txt in the project root for additional notices.    #
#                                                                          #
# Licensed under the Apache License, Version 2.0 (the "License")           #
# you may not use this file except in compliance with the License.         #
# You may obtain a copy of the License at                                  #
#                                                                          #
#     http: // www.apache.org/licenses/LICENSE-2.0                         #
#                                                                          #
# Unless required by applicable law or agreed to in writing, software      #
# distributed under the License is distributed on an "AS IS" BASIS,        #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. #
# See the License for the specific language governing permissions and      #
# limitations under the License.                                           #
############################################################################
import typing as T
import os

from typing import Optional, Any
import functools
import threading
import logging
from backend.sql_index_manager import SQLAnchor, SQLSymbol
from pygls.lsp.methods import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE, TEXT_DOCUMENT_DID_OPEN,
							   TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_SAVE,REFERENCES,DEFINITION,
							   WORKSPACE_DID_CHANGE_CONFIGURATION, WINDOW_WORK_DONE_PROGRESS_CREATE, INITIALIZED, PREPARE_RENAME, RENAME)

from pygls.lsp.types import (CompletionItem, CompletionList, CompletionOptions,
							 CompletionParams, ConfigurationItem, DidOpenTextDocumentParams,
							 ConfigurationParams, Diagnostic, ReferenceParams,
							 DidChangeTextDocumentParams,
							 DidCloseTextDocumentParams,
							 Range, Location, DeclarationParams, Position,
							 DidSaveTextDocumentParams, InitializedParams, PrepareRenameParams, RenameParams,
							 TextDocumentEdit, OptionalVersionedTextDocumentIdentifier, TextEdit, WorkspaceEdit)


from pygls.lsp.types import  Model
from pygls.server import LanguageServer

from urllib.parse import unquote
from pygls import uris


from frontend import VeribleIndexer
from frontend import VeribleSyntaxChecker

logger = logging.getLogger("myLogger")


# Add this until we update pygls models
# class ProgressParams(Model):
# 	token: ProgressToken
# 	value: Any


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


diplomat_server = DiplomatLanguageServer()


@diplomat_server.feature(INITIALIZED)
def on_initialized(ls : DiplomatLanguageServer,params : InitializedParams) :
	ls.show_message_log("Diplomat server is initialized.")
	return None


@diplomat_server.thread()
@diplomat_server.feature(PREPARE_RENAME)
def prepare_rename(ls : DiplomatLanguageServer, params : PrepareRenameParams) -> Range:
	if not ls.indexed :
		reindex_all(ls)
	selected_loc = Location(uri=params.text_document.uri,range=Range(start=params.position, end= params.position))
	symbol = ls.get_symbol_from_location(selected_loc)
	if symbol is None :
		return None
	else:
		return ls.anchor_to_location(symbol.declaration_anchor).range

@diplomat_server.thread()
@diplomat_server.feature(RENAME)
def perform_rename(ls : DiplomatLanguageServer, params : RenameParams) -> WorkspaceEdit:
	"""
	Search for all symbol references, generate a text edit for each and send them.
	:param ls:
	:param params:
	:return:
	"""
	new_name = params.new_name
	if not new_name.isidentifier() :
		# If invalid identifier, we don't want to perform rename.
		return None

	selected_loc = Location(uri=params.text_document.uri, range=Range(start=params.position, end=params.position))
	symbol = ls.get_symbol_from_location(selected_loc)

	delta_name_len = len(new_name) - len(symbol.name)

	anchor_list = [symbol.declaration_anchor]
	anchor_list.extend(ls.svindexer.index.get_symbol_references(symbol))

	# Client-side preparation
	locations_list : T.List[Location] = [ls.anchor_to_location(a) for a in anchor_list]
	files_list = {l.uri for l in locations_list}

	edits = dict()
	for f_uri in files_list :
		edits[f_uri] = [TextEdit(range=x.range,new_text=new_name) for x in locations_list if x.uri == f_uri]

	ret = WorkspaceEdit(changes=edits)

	# Server-side, SQL db update
	# This will change the anchor objects, all action taken on original anchor location shall be done before.
	files_id = {x.file for x in anchor_list}
	for fid in files_id :
		per_file_anchor_list = {x.start_line : sorted([j for j in anchor_list if j.file == fid and j.start_line == x.start_line],key=lambda x : x.start_char) for x in anchor_list if x.file == fid}
		alist : T.List[SQLAnchor]
		for line, alist in per_file_anchor_list.items():
			for i in range(len(alist)) :
				alist[i].start_char += i * delta_name_len
				alist[i].end_char += (i+1) * delta_name_len

	ls.svindexer.index.bulk_update_anchors(anchor_list)

	logger.debug(f"Reply for edit : {ret}")
	return ret



@diplomat_server.thread()
@diplomat_server.feature(DEFINITION)
def definition(ls : DiplomatLanguageServer, params : DeclarationParams) -> Location :
	if not ls.indexed :
		reindex_all(ls)

	selected_loc = Location(uri=params.text_document.uri,range=Range(start=params.position, end= params.position))
	symbol = ls.get_symbol_from_location(selected_loc)
	if symbol is None :
		logger.info("Symbol not found")
		return None

	anchor = symbol.declaration_anchor
	ret = ls.anchor_to_location(anchor)
	return ret


@diplomat_server.thread()
@diplomat_server.feature(REFERENCES)
def references(ls : DiplomatLanguageServer ,params : ReferenceParams) -> T.List[Location]:
	"""Returns references to the currently selected item."""
	if not ls.indexed :
		reindex_all(ls)

	selected_loc = Location(uri=params.text_document.uri, range=Range(start=params.position, end=params.position))
	symbol = ls.get_symbol_from_location(selected_loc)
	if symbol is None :
		logger.info("Symbol not found")
		return None
	logger.debug(f"Requested references for symbol {symbol.name}")
	refs  : T.List[SQLAnchor] = ls.svindexer.index.get_symbol_references(symbol)
	ret = [ls.anchor_to_location(r) for r in refs]
	logger.debug(f"References found is {ret}")
	return ret


@diplomat_server.feature(TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: DiplomatLanguageServer, params: DidSaveTextDocumentParams):
	"""Text document did change notification."""
	ls.indexed = False
	if ls.check_syntax :
		ls.syntax_check(params.text_document.uri)
	if ls.syntaxchecker.nberrors == 0 :
		reindex_all(ls)


@diplomat_server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: DiplomatLanguageServer, params: DidCloseTextDocumentParams):
	"""Text document did close notification."""
	pass

@diplomat_server.thread()
@diplomat_server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls : DiplomatLanguageServer, params : DidOpenTextDocumentParams):
	"""Text document did open notification."""
	if ls.configured :
		ls.syntax_check(params.text_document.uri)

@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_DBG_DUMP_INDEX_DB)
def dump_index(ls: DiplomatLanguageServer, *args):
	logger.info(f"Dump SQL index database into {os.path.abspath('index_dump.db')}")
	ls.svindexer.index.dump_db("index_dump.db")
	ls.svindexer.read_file_list(ls.flist_path)
	ls.svindexer.dump_json_index("index_dump.json")

@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_GET_CONFIGURATION)
def get_client_config(ls: DiplomatLanguageServer, *args):
	logger.debug("Refresh configuration")
	ls.show_message_log("Configuration requested")

	config = ls.get_configuration(ConfigurationParams(items=[
		ConfigurationItem(
			scope_uri='',
			section=DiplomatLanguageServer.CONFIGURATION_SECTION)
	])).result(2)[0]
	logger.debug("Got configuration back")
	ls.show_message_log("Got client configuration.")
	process_configuration(ls, config)


def process_configuration(ls, config):
	ls.svindexer.workspace_root = ls.workspace.root_path
	verible_root = config["backend"]["veribleInstallPath"]
	verible_root += "/" if verible_root != "" and verible_root[-1] not in ["\\", "/"] else ""
	ls.svindexer.exec_root = verible_root
	ls.syntaxchecker.executable = f"{verible_root}verible-verilog-syntax"
	ls.index_path = config["indexFilePath"]
	ls.flist_path = config["fileListPath"]
	if not os.path.isabs(ls.flist_path):
		ls.flist_path = os.path.normpath(os.path.join(ls.workspace.root_path, ls.flist_path))
	ls.svindexer.workspace_root = os.path.dirname(os.path.abspath(ls.flist_path))
	ls.skip_index = config["usePrebuiltIndex"]
	logger.info(f"Use prebuilt index : {'True' if ls.skip_index else 'False'}")
	if not os.path.isabs(ls.flist_path):
		ls.flist_path = os.path.abspath(os.path.normpath(os.path.join(ls.workspace.root_path, ls.flist_path)))
	ls.show_message_log(f"   FList path : {ls.flist_path}")
	ls.show_message_log(f"   WS root path : {ls.svindexer.workspace_root}")
	logger.info(f"FList path : {ls.flist_path}")
	logger.info(f"WS root path : {ls.svindexer.workspace_root}")
	ls.configured = True


@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_REINDEX)
def reindex_all(ls : DiplomatLanguageServer, *args):
	if not ls.configured :
		ls.show_message("You need to update server configuration before indexing")
		ls.show_message_log(f"Trying to reindex without configuration")
	else :
		ls.svindexer.clear()
		if not ls.skip_index :
			ls.show_message_log(f"Reindex using file {os.path.abspath(ls.flist_path)}")
			ls.svindexer.read_file_list(ls.flist_path)
			ls.svindexer.run_indexer()
		else :
			ls.show_message_log(f"Reindex using file {os.path.abspath(ls.index_path)}")
			ls.svindexer.read_index_file(ls.index_path)

		ls.indexed = True
		ls.show_message("Indexing done")

@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_REORDER)
def reorder(ls : DiplomatLanguageServer, *args):
	logger.debug(f"Reorder filelist")
	ls.svindexer.filelist = [ d.path for d in ls.workspace.documents.values() ]
	ls.svindexer.sort_files()
	ls.show_message("File sorting done")


# @diplomat_server.command(DiplomatLanguageServer.CMD_TST_PROGRESS_STRT)
# async def on_progress_show(ls: DiplomatLanguageServer, *args):
# 	progress_token = uuid.uuid4().int
#
# 	# Tell the client to create a progress bar
# 	await ls.lsp.send_request_async(
# 		WINDOW_WORK_DONE_PROGRESS_CREATE,
# 		WorkDoneProgressCreateParams(
# 			token=progress_token
# 		)
# 	)
#
# 	# Begin
# 	ls.send_notification(
# 		'$/progress',
# 		ProgressParams(
# 			token=progress_token,
# 			value=WorkDoneProgressBegin(
# 				kind='begin',   # <- for some reason you need to pass "kind" (this is a serialization issue that needs to be addressed)
# 				title='Begin',
# 				percentage=0
# 			)
# 		)
# 	)
#
# 	for i in range(1, 10):
# 		ls.send_notification(
# 			'$/progress',
# 			ProgressParams(
# 				token=progress_token,
# 				value=WorkDoneProgressReport(
# 					kind='report',
# 					message=f'Message {i}',
# 					percentage= i * 10
# 				)
# 			)
# 		)
#
# 		await asyncio.sleep(2)
#
#
# 	ls.send_notification(
# 		'$/progress',
# 		ProgressParams(
# 			token=progress_token,
# 			value=WorkDoneProgressEnd(
# 				kind='end',
# 				message='End',
# 			)
# 		)
# 	)


@diplomat_server.thread()
@diplomat_server.command(WORKSPACE_DID_CHANGE_CONFIGURATION)
def on_workspace_did_change_configuration(ls : DiplomatLanguageServer, *args) :
	logger.info("WS config change notif")
	get_client_config(ls)