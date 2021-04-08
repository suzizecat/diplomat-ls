import typing as T
from pygls.lsp.types import Location
from urllib.parse import unquote, urlparse

from .generic_indexer import IndexItems
from .generic_indexer import GenericIndexerInterface


class TreeIndexer(GenericIndexerInterface):
	def __init__(self):
		super().__init__()
		self.items = dict()

	def run_indexer(self):
		raise NotImplementedError

	def create_path(self, path : T.Tuple[str,...]):
		d = self.items
		for p in path :
			if p not in d :
				d[p] = dict()
				d = d[p]

	@staticmethod
	def _items_in_dict(dict) -> T.List[IndexItems]:
		ret = list()
		for i in dict :
			if isinstance(i,IndexItems) :
				ret.append(i)
			else:
				ret.extend(TreeIndexer._items_in_dict(i))
		return ret

	def get_items(self):
		return TreeIndexer._items_in_dict(self.items)

	def get_definition_from_location(self, search_loc : Location) -> Location:
		for i in self._items_in_dict(search_loc.uri) :
			if i.location == search_loc :
				if i.definition is None :
					return i.location
				else:
					return i.definition.location

	def get_refs_from_location(self, search_loc : Location) -> T.List[Location]:
		for i in self._items_in_dict(search_loc.uri):
			if i.location == search_loc:
					return [x.location for x in i.references]

	def add_index_item(self,i : IndexItems, path : T.Tuple[str,...] = None) :
		if path is None :
			path = (i.source_file)

		self.create_path(path)
		d = self.items

		# Navigate in the tree
		for p in path[:-1] :
			d = d[p]

		d[path[-1]] = i

	def cleanup(self, path : T.Iterable[str]):
		internal_path : T.List[T.Union[IndexItems,T.Dict[str,T.Any]]] = [self.items]
		for p in path :
			internal_path.append(internal_path[-1][p])

		while len(internal_path) > 1 :
			if len(internal_path[-1]) == 0 :
				# Removal of empty dict in actual object
				internal_path[-2].clear()
				# Removal of removed dict in path
				internal_path.pop()
			else:
				return

	def _remove_index_item_from_path(self, i : IndexItems, path : T.Iterable[str]) -> bool:
		d = self.items
		for p in path :
			d = d[p]
		for key, item in [(x,y) for x,y in d.items() if isinstance(y,IndexItems)] :
			if item == i :
				d.pop(key)
				return True
		return False


	@staticmethod
	def _for_all_paths(start_dict : T.Dict[str,T.Any], fct : T.Callable[[T.List[str]],bool],start : T.List[str] = None) -> bool:

		path = start if start is not None else []
		res = fct(path)
		if res :
			return True
		else :
			for key, d in [(x,y) for x,y in start_dict.items() if isinstance(y,dict)] :
				res = TreeIndexer._for_all_paths(d,fct, path + [key])
				if res :
					return True
		return False


	def remove_index_item(self,i : IndexItems, purge : bool = False):
		path = []
		d = self.items
		if self._for_all_paths(d,lambda p : self._remove_index_item_from_path(i,p),path) and purge:
			if purge :
				for c in i.references :
					self.remove_index_item(c,purge)

	def clear(self):
		self.items.clear()


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