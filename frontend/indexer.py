import typing as T
from pygls.lsp.types import Location

class IndexItems:
	def __init__(self):
		self.source_file : str = None
		self.location : Location = None
		self.references : T.List["IndexItems"] = list()
		self.id = None

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

	def add_index_item(self,i : IndexItems):
		raise NotImplementedError

	def remove_index_item(self,i : IndexItems, purge : bool = False):
		raise NotImplementedError

	def clear(self):
		raise NotImplementedError

class SimpleIndexer(GenericIndexerInterface):
	def __init__(self):
		super().__init__()
		self.items : T.Dict[str,IndexItems] = dict()
		self.location_to_id_map : T.Dict[Location, str] = dict()

	def run_indexer(self):
		raise NotImplementedError

	def get_definition_from_location(self, position : Location) -> Location:
		if position in self.location_to_id_map :
			return self.items[self.location_to_id_map[position]].location

	def get_refs_from_location(self, position : Location) -> T.List[Location]:
		if position in self.location_to_id_map :
			return self.items[self.location_to_id_map[position]].references_locations

	def add_index_item(self,i : IndexItems):
		self.items[i.id] = i
		self.location_to_id_map[i.location] = i.id

	def remove_index_item(self,i : IndexItems, purge : bool = False):
		self.items.pop(i.id)
		self.location_to_id_map.pop(i.location)
		if purge :
			for c in i.references :
				self.remove_index_item(c,purge)

	def clear(self):
		self.items.clear()
		self.location_to_id_map.clear()