import typing as T
from pygls.lsp.types import Location

class IndexItems:
	def __init__(self):
		self.source_file : str = None
		self.definition : Location = None
		self.references : T.List[Location] = list()
		self.id = None

class Indexer:
	def __init__(self):
		self.items : T.List[IndexItems] = list()

	def run_indexer(self):
		raise NotImplementedError

	def get_definition_from_location(self, position : Location) -> Location:
		for i in self.items :
			if i.definition == position or position in i.references:
				return i.definition

	def get_refs_from_location(self, position : Location) -> T.List[Location]:
		for i in self.items:
			if i.definition == position or position in i.references:
				return [i.definition] + i.references