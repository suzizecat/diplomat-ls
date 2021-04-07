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
import json
import time
import uuid
import typing as T
from json import JSONDecodeError
from typing import Optional
import logging
from pygls.lsp.methods import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
							   TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,REFERENCES)
from pygls.lsp.types import (CompletionItem, CompletionList, CompletionOptions,
							 CompletionParams, ConfigurationItem,
							 ConfigurationParams, Diagnostic, ReferenceParams,
							 DidChangeTextDocumentParams,
							 DidCloseTextDocumentParams,
							 DidOpenTextDocumentParams, MessageType, Position,
							 Range, Registration, RegistrationParams,
							 Unregistration, UnregistrationParams, Location)
from pygls.server import LanguageServer

COUNT_DOWN_START_IN_SECONDS = 10
COUNT_DOWN_SLEEP_IN_SECONDS = 1

logger = logging.getLogger(__name__)
logger.setLevel(10)

class DiplomatLanguageServer(LanguageServer):
	CMD_COUNT_DOWN_BLOCKING = 'countDownBlocking'
	CMD_COUNT_DOWN_NON_BLOCKING = 'countDownNonBlocking'
	CMD_REGISTER_COMPLETIONS = 'registerCompletions'
	CMD_SHOW_CONFIGURATION_ASYNC = 'showConfigurationAsync'
	CMD_SHOW_CONFIGURATION_CALLBACK = 'showConfigurationCallback'
	CMD_SHOW_CONFIGURATION_THREAD = 'showConfigurationThread'
	CMD_UNREGISTER_COMPLETIONS = 'unregisterCompletions'
	CMD_ADD_FILE = 'indexWorkspace'

	CONFIGURATION_SECTION = 'jsonServer'

	def __init__(self):
		super().__init__()


diplomat_server = DiplomatLanguageServer()

def _validate(ls, params):
	ls.show_message_log('Validating json...')

	text_doc = ls.workspace.get_document(params.text_document.uri)

	source = text_doc.source
	diagnostics = _validate_json(source) if source else []

	ls.publish_diagnostics(text_doc.uri, diagnostics)


def _validate_json(source):
	"""Validates json file."""
	diagnostics = []

	try:
		json.loads(source)
	except JSONDecodeError as err:
		msg = err.msg
		col = err.colno
		line = err.lineno

		d = Diagnostic(
			range=Range(
				start=Position(line=line - 1, character=col - 1),
				end=Position(line=line - 1, character=col)
			),
			message=msg,
			source=type(diplomat_server).__name__
		)

		diagnostics.append(d)

	return diagnostics


@diplomat_server.feature(COMPLETION, CompletionOptions(trigger_characters=[',']))
def completions(params: Optional[CompletionParams] = None) -> CompletionList:
	"""Returns completion items."""
	return CompletionList(
		is_incomplete=False,
		items=[
			CompletionItem(label='"'),
			CompletionItem(label='['),
			CompletionItem(label=']'),
			CompletionItem(label='{'),
			CompletionItem(label='}'),
		]
	)

@diplomat_server.feature(REFERENCES)
def references(ls,params : ReferenceParams) -> T.List[Location]:
	"""Returns completion items."""
	uri_source = params.text_document.uri
	ref_range = Range(start=Position(line=2,character=3),
					  end=Position(line=2, character=10))

	return [Location(uri=uri_source,range=ref_range)]



@diplomat_server.command(DiplomatLanguageServer.CMD_COUNT_DOWN_BLOCKING)
def count_down_10_seconds_blocking(ls, *args):
	"""Starts counting down and showing message synchronously.
	It will `block` the main thread, which can be tested by trying to show
	completion items.
	"""
	for i in range(COUNT_DOWN_START_IN_SECONDS):
		ls.show_message(f'Counting down... {COUNT_DOWN_START_IN_SECONDS - i}')
		time.sleep(COUNT_DOWN_SLEEP_IN_SECONDS)


@diplomat_server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: DidChangeTextDocumentParams):
	"""Text document did change notification."""
	_validate(ls, params)


@diplomat_server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: DiplomatLanguageServer, params: DidCloseTextDocumentParams):
	"""Text document did close notification."""
	server.show_message('Text Document Did Close')


@diplomat_server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
	"""Text document did open notification."""
	ls.show_message('Text Document Did Open')
	_validate(ls, params)


@diplomat_server.command(DiplomatLanguageServer.CMD_REGISTER_COMPLETIONS)
async def register_completions(ls: DiplomatLanguageServer, *args):
	"""Register completions method on the client."""

	params = RegistrationParams(registrations=[
		Registration(
			id=str(uuid.uuid4()),
			method=COMPLETION,
			register_options={"triggerCharacters": "[':']"})
	])
	print("register")
	response = await ls.register_capability_async(params)
	if response is None:
		ls.show_message('Successfully registered completions method')
	else:
		ls.show_message('Error happened during completions registration.',
						MessageType.Error)


@diplomat_server.command(DiplomatLanguageServer.CMD_SHOW_CONFIGURATION_ASYNC)
async def show_configuration_async(ls: DiplomatLanguageServer, *args):
	"""Gets exampleConfiguration from the client settings using coroutines."""
	try:
		config = await ls.get_configuration_async(
			ConfigurationParams(items=[
				ConfigurationItem(
					scope_uri='',
					section=DiplomatLanguageServer.CONFIGURATION_SECTION)
			]))

		example_config = config[0].get('exampleConfiguration')

		ls.show_message(f'jsonServer.exampleConfiguration value: {example_config}')

	except Exception as e:
		ls.show_message_log(f'Error ocurred: {e}')


@diplomat_server.command(DiplomatLanguageServer.CMD_SHOW_CONFIGURATION_CALLBACK)
def show_configuration_callback(ls: DiplomatLanguageServer, *args):
	"""Gets exampleConfiguration from the client settings using callback."""
	def _config_callback(config):
		try:
			example_config = config[0].get('exampleConfiguration')

			ls.show_message(f'jsonServer.exampleConfiguration value: {example_config}')

		except Exception as e:
			ls.show_message_log(f'Error ocurred: {e}')

	ls.get_configuration(ConfigurationParams(items=[
		ConfigurationItem(
			scope_uri='',
			section=DiplomatLanguageServer.CONFIGURATION_SECTION)
	]), _config_callback)


@diplomat_server.thread()
@diplomat_server.command(DiplomatLanguageServer.CMD_SHOW_CONFIGURATION_THREAD)
def show_configuration_thread(ls: DiplomatLanguageServer, *args):
	"""Gets exampleConfiguration from the client settings using thread pool."""
	try:
		config = ls.get_configuration(ConfigurationParams(items=[
			ConfigurationItem(
				scope_uri='',
				section=DiplomatLanguageServer.CONFIGURATION_SECTION)
		])).result(2)

		example_config = config[0].get('exampleConfiguration')

		ls.show_message(f'jsonServer.exampleConfiguration value: {example_config}')

	except Exception as e:
		ls.show_message_log(f'Error ocurred: {e}')


@diplomat_server.command(DiplomatLanguageServer.CMD_UNREGISTER_COMPLETIONS)
async def unregister_completions(ls: DiplomatLanguageServer, *args):
	"""Unregister completions method on the client."""
	params = UnregistrationParams(unregisterations=[
		Unregistration(id=str(uuid.uuid4()), method=COMPLETION)
	])
	response = await ls.unregister_capability_async(params)
	if response is None:
		ls.show_message('Successfully unregistered completions method')
	else:
		ls.show_message('Error happened during completions unregistration.',
						MessageType.Error)

diplomat_server.start_tcp('localhost', 8080)