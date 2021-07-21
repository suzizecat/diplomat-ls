import typing as T
import base64
import os
import sqlite3
from pygls import uris

class KytheRef:

	test_mode = False
	root_path: str = "."

	@classmethod
	def from_dict(cls,data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		ret = cls()
		ret.read_dict(data)

		return ret

	def __init__(self):
		self.signature: str = None
		self._path: str = None

		# self.language: str = None

	@property
	def path(self):
		return self._path

	@path.setter
	def path(self,val):
		self._path = uris.from_fs_path(os.path.abspath(os.path.join(self.root_path,val)))

	def read_dict(self, data: T.Dict[str, T.Union[T.Dict[str, str], str]]):
		self.signature = base64.b64decode(data["signature"]).decode("ascii")

		loc_path = os.path.normpath(data["path"]) if KytheRef.test_mode else data["path"]
		self.path = loc_path
		# for file nodes
		if self.signature == "" :
			self.signature = f"{loc_path}#"


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

		self.id : int = None

	@property
	def kind(self):
		return self.facts["/kythe/node/kind"] if "/kythe/node/kind" in self.facts else None

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
	SQL_ROOT_PATH = os.path.join(os.path.dirname(__file__), "sql")

	def __init__(self, sql_db = ":memory:"):
		self.nodes : T.Dict[str, KytheNode] = dict()
		self.edges : T.List[KytheEdge]      = list()
		self.files : T.Dict[str,T.Optional[int]] = dict()
		self.unsolved_edges : T.List[KytheEdge] = list()

		self.db = sqlite3.connect(sql_db, check_same_thread=False)
		self.db.row_factory = sqlite3.Row

		self._sql_create_db()

	def __del__(self):
		self.db.close()

	def _sql_create_db(self):
		with open(f"{self.SQL_ROOT_PATH}/create_db.sql", "r") as f:
			with self.db :
				self.db.executescript(f.read())

	def _sql_delete_db(self):
		with open(f"{self.SQL_ROOT_PATH}/delete_db.sql", "r") as f:
			with self.db:
				self.db.executescript(f.read())

	def _sql_node_get_anchor_id(self,node : KytheNode) -> T.Union[int,None]:
		ret : sqlite3.Row = self.db.execute("SELECT anchor FROM nodes WHERE id = ?",[node.id]).fetchone()
		return ret["anchor"] if ret is not None else None

	def _sql_get_node_id_from_signatures(self,sig : T.List[str]) -> T.Dict[str,int]:
		req =f"SELECT id, signature FROM nodes WHERE signature IN ({','.join(['?' for f in sig])})"
		ret: T.List[sqlite3.Row] = self.db.execute(req, sig).fetchall()
		if ret is None :
			raise KeyError
		return {r['signature']:r['id'] for r in ret}

	def _sql_set_anchor(self,anchor_id,target_id):
		with self.db :
			self.db.execute("UPDATE nodes SET anchor=? WHERE id=?",[anchor_id,target_id])

	def sql_clear(self):
		self._sql_delete_db()
		self._sql_create_db()

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

	def _sql_add_edge(self,edge : KytheEdge):
		source = edge.source if isinstance(edge.source,str) else edge.source.signature
		target = edge.target if isinstance(edge.target, str) else edge.target.signature

		idmap = self._sql_get_node_id_from_signatures([source,target])

		if source not in idmap or target not in idmap :
			# todo log error
			print(f"Skip edge {source} -> {target}")
			return

		data= [idmap[source],idmap[target],edge.kind]
		with self.db :
			self.db.execute("INSERT INTO edges (source,target,kind) VALUES (?,?,?)",data)

		if edge.kind ==	'/kythe/edge/defines/binding' :
				self._sql_set_anchor(anchor_id=data[0],target_id=data[1])

	def _sql_add_file(self,uri : str):
		with self.db:
			if uri not in self.files :
				self.db.execute("INSERT INTO files (path) VALUES (?)", [uri])
				self.files[uri] = self.db.execute("SELECT id FROM files WHERE path=?",[uri]).fetchone()['id']

	def _sql_add_node(self,node : KytheNode) -> int:
		with self.db :
			self._sql_add_file(node.path)
			return self.db.execute("INSERT INTO nodes (signature,file_id) VALUES (?,?)",
								   [node.signature,self.files[node.path]]).lastrowid

	def _sql_add_node_fact(self,node_id, fact,value) -> T.Union[int,None]:
		with self.db:
			if fact == "/kythe/node/kind" :
				self.db.execute("UPDATE nodes SET kind=? WHERE id=?",[value,node_id])
				return None
			else :
				return self.db.execute("INSERT INTO facts (node,name,val) VALUES (?,?,?)",
									   [node_id,fact,value]).lastrowid

	def sql_add_element(self,data : T.Dict[str,T.Union[T.Dict[str,str],str]]):
		if data["fact_name"] == "/":
			#  We have an edge
			edge = KytheEdge.from_dict(data)
			self._sql_add_edge(edge)
		else:
			node = KytheNode.from_dict(data)
			try :
				node_id = self._sql_get_node_id_from_signatures([node.signature])[node.signature]
			except KeyError :
				node_id = self._sql_add_node(node)
			for key, val in node.facts.items():
				self._sql_add_node_fact(node_id,key,val)

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

