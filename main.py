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
import asyncio
import time
import uuid
import typing as T
import os
from typing import Optional
import logging
from pygls.lsp.methods import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
							   TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,REFERENCES,DEFINITION,
							   WORKSPACE_DID_CHANGE_CONFIGURATION)
from pygls.lsp.types import (CompletionItem, CompletionList, CompletionOptions,
							 CompletionParams, ConfigurationItem,
							 ConfigurationParams, Diagnostic, ReferenceParams,
							 DidChangeTextDocumentParams,
							 DidCloseTextDocumentParams,
							 DidOpenTextDocumentParams, MessageType, Position,
							 Range, Registration, RegistrationParams,
							 Unregistration, UnregistrationParams, Location, DeclarationParams)


from pygls.server import LanguageServer
from frontend import VeribleIndexer

logger = logging.getLogger(__name__)
logger.setLevel(10)

class DiplomatLanguageServer(LanguageServer):
	CMD_INDEX_WORKSPACE = 'indexWorkspace'
	CMD_GET_CONFIGURATION = "diplomat-server.get-configuration"
	CMD_REINDEX = 'diplomat-server.full-index'
	CONFIGURATION_SECTION = 'diplomatServer'

	def __init__(self):
		super().__init__()
		self.index_path = ""
		self.indexed = False
		self.svindexer = VeribleIndexer()



diplomat_server = DiplomatLanguageServer()

# @diplomat_server.thread()
# @diplomat_server.feature(WORKSPACE_CONFIGURATION)
# def configure(ls):
# 	try:
# 		config = ls.get_configuration(ConfigurationParams(items=[
# 			ConfigurationItem(
# 				scope_uri='',
# 				section=DiplomatLanguageServer.CONFIGURATION_SECTION)
# 		])).result(2)
#
# 		vbend = config[0].get('backend.verilog')
# 		svbend = config[0].get('backend.systemVerilog')
#
# 		ls.show_message(f'Verilog : {vbend}\nSV : {svbend}')
#
# 	except Exception as e:
# 		ls.show_message_log(f'Error ocurred: {e}')

# @diplomat_server.feature(COMPLETION, CompletionOptions(trigger_characters=[',']))
# def completions(params: Optional[CompletionParams] = None) -> CompletionList:
# 	"""Returns completion items."""
# 	return CompletionList(
# 		is_incomplete=False,
# 		items=[
# 			CompletionItem(label='"'),
# 			CompletionItem(label='['),
# 			CompletionItem(label=']'),
# 			CompletionItem(label='{'),
# 			CompletionItem(label='}'),
# 		]
# 	)

@diplomat_server.feature(DEFINITION)
def declaration(ls : DiplomatLanguageServer,params : DeclarationParams) -> Location :
	if not ls.indexed :
		reindex_all(ls)
	uri_source = params.text_document.uri.replace(ls.workspace.root_uri,".")
	ref_range = Range(start=params.position,
					  end=params.position)
	ret = ls.svindexer.get_definition_from_location(Location(uri=uri_source, range=ref_range))
	if ret is not None :
		ret.uri = ret.uri.replace("file:///.", ls.workspace.root_uri)
	return ret

@diplomat_server.feature(REFERENCES)
def references(ls : DiplomatLanguageServer ,params : ReferenceParams) -> T.List[Location]:
	"""Returns completion items."""
	if not ls.indexed :
		reindex_all(ls)
	uri_source = params.text_document.uri.replace(ls.workspace.root_uri,".")
	ref_range = Range(start=params.position,
					  end=params.position)

	ret = ls.svindexer.get_refs_from_location(Location(uri=uri_source,range=ref_range))
	for r in ret :
		r.uri = r.uri.replace("file:///.",ls.workspace.root_uri)
	return ret


# @diplomat_server.feature(TEXT_DOCUMENT_DID_CHANGE)
# def did_change(ls, params: DidChangeTextDocumentParams):
# 	"""Text document did change notification."""


@diplomat_server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: DiplomatLanguageServer, params: DidCloseTextDocumentParams):
	"""Text document did close notification."""
	server.show_message('Text Document Did Close')

#
# @diplomat_server.feature(TEXT_DOCUMENT_DID_OPEN)
# async def did_open(ls, params: DidOpenTextDocumentParams):
# 	"""Text document did open notification."""
# 	ls.show_message('Text Document Did Open')
#

@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_GET_CONFIGURATION)
def get_client_config(ls: DiplomatLanguageServer, *args):
	print("Refresh configuration")
	ls.show_message("Configuration requested")
	try:
		config = ls.get_configuration(ConfigurationParams(items=[
			ConfigurationItem(
				scope_uri='',
				section=DiplomatLanguageServer.CONFIGURATION_SECTION)
		])).result(2)[0]

		vbend = config["backend"]["verilog"]
		svbend = config["backend"]["systemVerilog"]
		ls.index_path = config["indexFilePath"]

		ls.show_message(f'Verilog : {vbend}\nSV : {svbend}')

	except Exception as e:
		ls.show_message_log(f'Error ocurred: {e}')
		print("Error :" , str(e))

@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_REINDEX)
def reindex_all(ls : DiplomatLanguageServer, *args):
	print(f"Reindex using file {os.path.abspath(ls.index_path)}")
	ls.svindexer.clear()
	ls.svindexer.read_index_file(ls.index_path)
	ls.indexed = True
	ls.show_message("Indexing done")

# @diplomat_server.thread()
# @diplomat_server.command(WORKSPACE_DID_CHANGE_CONFIGURATION)
# def on_workspace_did_change_configuration(ls : DiplomatLanguageServer, *args) :
# 	print("WS config change notif")
# 	print(args)
# 	get_client_config(ls)


# @diplomat_server.command(DiplomatLanguageServer.CMD_REGISTER_COMPLETIONS)
# async def register_completions(ls: DiplomatLanguageServer, *args):
# 	"""Register completions method on the client."""
#
# 	params = RegistrationParams(registrations=[
# 		Registration(
# 			id=str(uuid.uuid4()),
# 			method=COMPLETION,
# 			register_options={"triggerCharacters": "[':']"})
# 	])
# 	print("register")
# 	response = await ls.register_capability_async(params)
# 	if response is None:
# 		ls.show_message('Successfully registered completions method')
# 	else:
# 		ls.show_message('Error happened during completions registration.',
# 						MessageType.Error)

print("Start server")
diplomat_server.start_tcp('localhost', 8080)