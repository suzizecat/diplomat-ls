import typing as T
import base64
import os




class KytheRef:
	@classmethod
	def from_dict(cls,data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		ret = cls()
		ret.read_dict(data)

		return ret

	def __init__(self):
		self.signature: str = None
		self.path: str = None
		# self.language: str = None

	def read_dict(self, data: T.Dict[str, T.Union[T.Dict[str, str], str]]):
		self.signature = base64.b64decode(data["signature"]).decode("ascii")
		# Todo remove normpath in real run
		self.path = os.path.normpath(data["path"])
		# for file nodes
		if self.signature == "" :
			self.signature = self.path


class KytheNode(KytheRef):
	@classmethod
	def from_dict(cls,data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		ret = cls()
		ret.read_dict(data)
		return ret

	def __init__(self):
		super().__init__()

		self.facts : T.Dict[str,str] = dict()
		self.link_source : T.List[KytheEdge] = list()
		self.link_target : T.List[KytheEdge] = list()

	@property
	def kind(self):
		return self.facts["/kythe/node/kind"]

	def read_dict(self, data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		source = data["source"]
		super().read_dict(source)
		self.facts[data["fact_name"]] = base64.b64decode(data["fact_value"]).decode("utf-8")

	@property
	def anchor(self) -> "KytheNode":
		if self.kind == "anchor" :
			return self
		for edge in self.link_target :
			if edge.kind == '/kythe/edge/defines/binding' :
				return edge.source
		return None


class KytheEdge:
	@classmethod
	def from_dict(cls,data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		ret = cls()
		ret.read_dict(data)
		return ret

	def __init__(self):
		self.kind : str = ""
		self.source : T.Union[str,KytheNode] = None
		self.target : T.Union[str,KytheNode] = None

	def read_dict(self, data: T.Dict[str, T.Union[T.Dict[str, str], str]]):

		self.source = KytheRef.from_dict(data["source"]).signature
		self.target = KytheRef.from_dict(data["target"]).signature
		self.kind = data["edge_kind"]


	@property
	def resolved_source(self):
		return isinstance(self.source,KytheNode)

	@property
	def resolved_target(self):
		return isinstance(self.target, KytheNode)

	@property
	def resolved_full(self):
		return self.resolved_source and self.resolved_target


class KytheTree:
	def __init__(self):
		self.nodes : T.Dict[str, KytheNode] = dict()
		self.edges : T.List[KytheEdge]      = list()

		self.unsolved_edges : T.List[KytheEdge] = list()

	def clear(self):
		self.nodes.clear()
		self.edges.clear()
		self.unsolved_edges.clear()

	def get_node_anchor(self, node : KytheNode) -> T.Union[KytheNode,None]:
		if node.kind == "anchor" :
			return node
		else:
			for edge in node.link_target :
				if edge.kind != '/kythe/edge/defines/binding' :
					continue
				return edge.source
		return None

	def add_element(self,data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		if data["fact_name"] == "/" :
			#  We have an edge
			edge = KytheEdge.from_dict(data)
			self.edges.append(edge)
			self.unsolved_edges.append(self.edges[-1])
		else:
			node = KytheNode.from_dict(data)
			if node.signature not in self.nodes :
				self.nodes[node.signature] = node
			else :
				matching_node = self.nodes[node.signature]
				for key, val in node.facts.items() :
					matching_node.facts[key] = val

	def add_and_link_element(self,data : T.Dict[str,T.Union[T.Dict[str,str],str]]) :
		if data["fact_name"] == "/" :
			#  We have an edge
			edge = KytheEdge.from_dict(data)
			self.edges.append(edge)

			if not edge.resolved_source:
				try:
					edge.source = self.nodes[edge.source]
					edge.source.link_source.append(edge)
				except KeyError:
					pass
			if not edge.resolved_target:
				try:
					edge.target = self.nodes[edge.target]
					edge.target.link_target.append(edge)
				except KeyError:
					pass
			if not edge.resolved_full:
				self.unsolved_edges.append(edge)

		else:
			node = KytheNode.from_dict(data)
			if node.signature not in self.nodes :
				self.nodes[node.signature] = node
			else :
				matching_node = self.nodes[node.signature]
				for key, val in node.facts.items() :
					matching_node.facts[key] = val

	def solve_edges(self):
		i = 0
		while i < len(self.unsolved_edges):
			e = self.unsolved_edges[i]
			if not e.resolved_source :
				try :
					e.source = self.nodes[e.source]
					e.source.link_source.append(e)
				except KeyError :
					pass
			if not e.resolved_target :
				try :
					e.target = self.nodes[e.target]
					e.target.link_target.append(e)
				except KeyError :
					pass
			if e.resolved_full :
				self.unsolved_edges.pop(i)
			else :
				i += 1

