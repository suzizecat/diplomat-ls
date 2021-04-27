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
import logging
from pygls.lsp.methods import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
							   TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_SAVE,REFERENCES,DEFINITION,
							   WORKSPACE_DID_CHANGE_CONFIGURATION, WINDOW_WORK_DONE_PROGRESS_CREATE)

from pygls.lsp.types import (CompletionItem, CompletionList, CompletionOptions,
							 CompletionParams, ConfigurationItem,
							 ConfigurationParams, Diagnostic, ReferenceParams,
							 DidChangeTextDocumentParams,
							 DidCloseTextDocumentParams,
							 DidOpenTextDocumentParams, MessageType, Position,
							 Range, Registration, RegistrationParams,
							 Unregistration, UnregistrationParams, Location, DeclarationParams,
							 WorkDoneProgressBegin,WorkDoneProgressEnd, WorkDoneProgressReport, ProgressToken,
							 WorkDoneProgressParams,WorkDoneProgressCreateParams, DidSaveTextDocumentParams)


from pygls.lsp.types import  Model
from pygls.server import LanguageServer

from urllib.parse import unquote



from frontend import VeribleIndexer

logger = logging.getLogger()


# Add this until we update pygls models
class ProgressParams(Model):
	token: ProgressToken
	value: Any


class DiplomatLanguageServer(LanguageServer):
	CMD_INDEX_WORKSPACE = 'diplomat-server.reindex'
	CMD_GET_CONFIGURATION = "diplomat-server.get-configuration"
	CMD_REORDER = "diplomat-server.reorder-files"
	CMD_REINDEX = 'diplomat-server.full-index'
	CMD_TST_PROGRESS_STRT = 'diplomat-server.test.start-progress'
	CMD_TST_PROGRESS_STOP = 'diplomat-server.test.stop-progress'

	CONFIGURATION_SECTION = 'diplomatServer'

	def __init__(self):
		super().__init__()
		self.index_path = ""
		self.flist_path = ""
		self.skip_index = False
		self.indexed = False
		self.svindexer = VeribleIndexer()
		self.progress_uuid = None



diplomat_server = DiplomatLanguageServer()

@diplomat_server.feature(DEFINITION)
def declaration(ls : DiplomatLanguageServer,params : DeclarationParams) -> Location :
	if not ls.indexed :
		reindex_all(ls)
	uri_source = unquote(params.text_document.uri)
	ref_range = Range(start=params.position,
					  end=params.position)
	ret = ls.svindexer.get_definition_from_location(Location(uri=uri_source, range=ref_range))
	return ret

@diplomat_server.feature(REFERENCES)
def references(ls : DiplomatLanguageServer ,params : ReferenceParams) -> T.List[Location]:
	"""Returns completion items."""
	if not ls.indexed :
		reindex_all(ls)
	uri_source = unquote(params.text_document.uri)
	ref_range = Range(start=params.position,
					  end=params.position)
	ret = ls.svindexer.get_refs_from_location(Location(uri=uri_source,range=ref_range))
	return ret


@diplomat_server.feature(TEXT_DOCUMENT_DID_SAVE)
def did_change(ls, params: DidSaveTextDocumentParams):
	"""Text document did change notification."""
	ls.indexed = False
	reindex_all(ls)


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
	logger.debug("Refresh configuration")
	ls.show_message("Configuration requested")
	try:
		config = ls.get_configuration(ConfigurationParams(items=[
			ConfigurationItem(
				scope_uri='',
				section=DiplomatLanguageServer.CONFIGURATION_SECTION)
		])).result(2)[0]
		t = ls.client_capabilities
		ls.svindexer.exec_root = config["backend"]["veribleInstallPath"]
		ls.svindexer.exec_root += "/" if ls.svindexer.exec_root != "" and ls.svindexer.exec_root[-1] not in ["\\","/"] else ""
		ls.index_path = config["indexFilePath"]

		ls.flist_path = config["fileListPath"]
		if not os.path.isabs(ls.flist_path) :
			ls.flist_path = os.path.normpath(os.path.join(ls.workspace.root_path,ls.flist_path))

		ls.svindexer.workspace_root = os.path.dirname(os.path.abspath(ls.flist_path))
		ls.skip_index = config["usePrebuiltIndex"]

		if not os.path.isabs(ls.flist_path) :
			ls.flist_path =  os.path.abspath(os.path.normpath(os.path.join(ls.workspace.root_path,ls.flist_path)))


	except Exception as e:
		ls.show_message_log(f'Error ocurred: {e}')


@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_REINDEX)
def reindex_all(ls : DiplomatLanguageServer, *args):
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
