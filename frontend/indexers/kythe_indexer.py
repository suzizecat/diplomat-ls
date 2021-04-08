import typing as T
from pygls.lsp.types import Location, Range, Position
from urllib.parse import unquote, quote as urlquote, urlparse, urlunparse, ParseResult

from .generic_indexer import GenericIndexerInterface
from .kythe import KytheTree
from .kythe import KytheNode


class WrongNodeKindError(RuntimeError):
	pass

class KytheLocation:
	def __init__(self):
		self.file : KytheNode = None
		self.start: int = 0
		self.end  : int = 0


	def range_from_anchor(self, anchor : KytheNode):
		if anchor.kind != "anchor" :
			raise WrongNodeKindError
		self.start = int(anchor.facts["/kythe/loc/start"])
		self.end   = int(anchor.facts["/kythe/loc/end"])


	@property
	def path(self):
		return self.file.path

	@property
	def _filetext(self):
		return self.file.facts["/kythe/text"]

	@property
	def start_line(self) -> int:
		return self._filetext[:self.start].count("\n")

	@property
	def start_char(self) -> int:
		return self.start - self._filetext.rindex("\n",0,self.start)

	@property
	def end_line(self) -> int:
		return self._filetext[:self.end].count("\n")

	@property
	def end_char(self) -> int:
		return self.end - self._filetext.rindex("\n",0,self.end)


class KytheIndexer(GenericIndexerInterface):
	def __init__(self):
		super().__init__()

		self.tree : KytheTree = KytheTree()
		self.anchors : T.List[KytheNode]   = list()
		self.files : T.Dict[str,KytheNode] = dict()

	def run_indexer(self):
		raise NotImplementedError

	def refresh_files(self):
		self.files.clear()
		self.files = {n.path:n for n in self.tree.nodes.values() if n.kind == "file"}

	def refresh_anchors(self):
		self.anchors.clear()
		self.anchors = [n for n in self.tree.nodes.values() if n.kind == "anchor"]

	def get_definition_from_location(self, loc: Location) -> T.Union[Location, None]:
		anchor = self.get_anchor_from_location(loc)
		def_anchor : KytheNode = None

		if anchor is None :
			return None
		# Get definition node from target anchor
		for edge in anchor.link_source :
			if edge.kind != '/kythe/edge/ref' :
				continue
			else :
				def_anchor = self.tree.get_node_anchor(edge.target)

		if def_anchor is None :
			return None

		kloc = KytheLocation()
		kloc.file = self.files[def_anchor.path]
		kloc.range_from_anchor(def_anchor)
		return self._kythe_to_lsp_location(kloc)

	def get_refs_from_location(self, loc : Location) -> T.List[Location]:
		anchor = self.get_anchor_from_location(loc)
		ret = list()
		if anchor is None :
			return ret
		semnode = None
		for edge in anchor.link_source :
			if edge.kind != '/kythe/edge/defines/binding' :
				continue
			semnode = edge.target
		if semnode is None :
			return list()

		for edge in semnode.link_target :
			if edge.kind != '/kythe/edge/ref':
				continue
			ref_anchor = edge.source
			kloc = KytheLocation()
			kloc.file = self.files[ref_anchor.path]
			kloc.range_from_anchor(ref_anchor)
			ret.append(self._kythe_to_lsp_location(kloc))

		return ret

	def get_anchor_from_location(self,loc : Location) -> KytheNode:
		kloc = self._lsp_to_kythe_location(loc)
		for anchor in self.anchors :
			if anchor.path != kloc.path :
				continue
			if int(anchor.facts["/kythe/loc/start"]) > kloc.start or int(anchor.facts["/kythe/loc/end"]) < kloc.end :
				continue
			return anchor

	def get_file_from_location(self,loc : Location) -> KytheNode:
		path = unquote(urlparse(loc.uri).path)
		return self.files[path]

	def _lsp_to_kythe_location(self, loc : Location) -> KytheLocation:
		kloc = KytheLocation()
		text = self.get_file_from_location(loc).facts["/kythe/text"]

		kloc.file = self.get_file_from_location(loc)
		kloc.start= self._pos_from_coord(text,loc.range.start.line, loc.range.start.character)
		kloc.end  = self._pos_from_coord(text,loc.range.end.line  , loc.range.end.character)
		return kloc

	def _kythe_to_lsp_location(self, kloc : KytheLocation) -> Location:
		uri_base = ParseResult(scheme='file',path=urlquote(kloc.path),netloc="",params="",query="",fragment="")

		start_line = kloc.start_line
		start_character = kloc.start_char
		end_line = kloc.end_line
		end_character = kloc.end_char

		loc = Location(uri=urlunparse(uri_base),
					   range=Range(
						   start=Position(line=start_line, character=start_character),
						   end=Position(line=end_line, character=end_character))
					   )

		return loc

	@staticmethod
	def _pos_from_coord( text : str, line : int = 0, col : int = 0):
		ret = 0
		if line > 0 :
			ret = text.find("\n")
			for i in range(line-1) :
				ret = text.find("\n",ret + 1)
		ret += col
		return ret

