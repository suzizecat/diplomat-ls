import typing as T
from pygls.lsp.types import Location
from urllib.parse import unquote, urlparse


class IndexItems:
	def __init__(self):
		self.location : Location = None
		self.references : T.List["IndexItems"] = list()
		self.definition : "IndexItems" = None
		self.id = None


	@property
	def source_file(self):
		return unquote(urlparse(self.location.uri).path)

	@property
	def references_locations(self):
		return [r.location for r in self.references] + [self.location]


class GenericIndexerInterface:
	def __init__(self):
		pass

	def run_indexer(self):
		raise NotImplementedError

	def get_definition_from_location(self, position : Location) -> Location:
		raise NotImplementedError

	def get_refs_from_location(self, position : Location) -> T.List[Location]:
		raise NotImplementedError
