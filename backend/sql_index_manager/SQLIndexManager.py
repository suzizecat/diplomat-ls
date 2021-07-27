import base64
import sqlite3
import os

import typing as T
from . import SQLAnchor, SQLSymbol, SQLFile
import gc
import json
import base64
import logging

logger = logging.getLogger("myLogger")

class KytheVName:
	def __init__(self, signature : str = None, path : str = None, lang : str = None, root : str = None, corpus :str = None):
		self.signature = signature
		self.path = path
		self.lang = lang
		self.root = root
		self.corpus = corpus

	@classmethod
	def from_dict(cls,data):

		return cls(data["signature"],data["path"],data["language"],data["root"], data["corpus"])

class JSONRecord:
	AUTO_DECODE = True
	def __init__(self):
		self.source : KytheVName = None
		self.target : KytheVName = None
		self.edge_kind : str = None
		self.facts : T.Dict[str,str] = dict()

	def is_record_appendable(self,data):
		if self.source is not None and self.source.signature != KytheVName.from_dict(data["source"]).signature :
			return False
		if "fact_value" in data and data["fact_name"] in self.facts :
			return False
		return True

	def append_record(self,data):

		if self.source is None :
			self.source = KytheVName.from_dict(data["source"])
		if "target" in data :
			self.target = KytheVName.from_dict(data["target"])
		if "edge_kind" in data :

			self.edge_kind = data["edge_kind"][len("/kythe/edge"):]

		if "fact_value" in data :
			self.facts[data["fact_name"]] = data["fact_value"] if not self.AUTO_DECODE else base64.standard_b64decode(data["fact_value"]).decode("utf-8")
		return True

	def clear(self):
		self.source = None
		self.target = None
		self.edge_kind = None
		self.facts.clear()

	@property
	def is_node(self):
		return "/kythe/node/kind" in self.facts and self.source.signature != ""

	@property
	def is_anchor(self):
		return self.is_node and self.facts["/kythe/node/kind"] == "anchor"

	@property
	def is_symbol(self):
		return self.is_node and not self.is_anchor

	@property
	def symbol_type(self):
		if not self.is_symbol :
			return None
		if "/kythe/subkind" in self.facts :
			return self.facts["/kythe/subkind"]
		else:
			return self.facts["/kythe/node/kind"]

	@property
	def	is_file(self):
		if "/kythe/node/kind" in self.facts and self.facts["/kythe/node/kind"] == "file" :
			return True
		return False

	@property
	def is_edge(self):
		return self.target is not None



class SQLIndexManager:
	SQL_ROOT_PATH = os.path.join(os.path.dirname(__file__), "sql")
	"""
	This class provide a high level index manager using SQLite DB
	"""
	def __init__(self):
		self.db = sqlite3.connect(":memory:",check_same_thread=False)
		self._signature_cache : T.Dict[str,int] = dict()
		self._file_id_mapping : T.Dict[str,int] = dict()
		self._cached_file : SQLFile = None
		self._setup_db()

	def __del__(self):
		self.db.close()

	def _setup_db(self):
		"""
		Perform setup step for the database (files and structure creation)
		:return:
		"""
		self.db.row_factory = sqlite3.Row
		self.clear()

	def clear(self):
		self._delete_db()
		self._create_db()

	def _create_db(self):
		script_path = f"{self.SQL_ROOT_PATH}/create_index_db.sql"
		self._run_sql_script(script_path)

	def _delete_db(self):
		script_path = f"{self.SQL_ROOT_PATH}/delete_index_db.sql"
		self._run_sql_script(script_path)

	def _run_sql_script(self, script_path):
		with open(script_path, "r") as script:
			with self.db :
				self.db.executescript(script.read())

	def dump_db(self, path : str):
		dump = sqlite3.connect(path)
		with dump :
			self.db.backup(dump)
		dump.close()

	def add_file(self,file_path : str, content : str):
		"""
		Low level creation of a file in db.
		:param file_path:
		:param content:
		:return: ID column of the given file
		"""
		with self.db :
			return self.db.execute("INSERT INTO files(path,content) VALUES (?,?)",[file_path,content]).lastrowid


	def add_anchor(self,file_id : int,start : int, end : int) -> int:
		"""
		Low-level creation of an anchor object in db.
		Return the row id upon success.
		:param file_id: File identifier for the anchor
		:param start: Start position, in absolute character from the beginning of the file.
		:param end: End position, in absolute character from the beginning of the file.
		:return: ID column of the created anchor.
		"""
		with self.db :
			return self.db.execute("INSERT INTO anchors(file,start,stop) VALUES (?,?,?)",[file_id,start,end]).lastrowid

	def add_symbol(self,name : str, type : str, declaration_anchor_id : int) -> int:
		"""
		Low-level creation of a symbol in DB. Must be linked to a definition anchor.
		:param name: Name of the symbol, usually the value of the symbol.
		:param type: Type description.
		:param declaration_anchor_id: Anchor which describe the symbol declaration location.
		:return: ID column of the created anchor.
		"""
		with self.db :
			return self.db.execute("INSERT INTO symbols(name,type,declaration_anchor) VALUES (?,?,?)",[name,type,declaration_anchor_id]).lastrowid

	def update_symbol_name(self,id : int, new_name : str):
		with self.db:
			self.db.execute("UPDATE symbols SET name = ? WHERE id = ?",[new_name,id])

	def _update_symbol_anchor(self,id : int, anchor_id : int):
		with self.db:
			self.db.execute("UPDATE symbols SET declaration_anchor = ? WHERE id = ?",[anchor_id,id])

	def add_ref(self,anchor : int, symbol : int) -> int:
		"""
		Low-level creation of a single reference link between an already existing symbol and an already existing anchor.
		This anchor is then supposed to be a reference to its linked symbol.
		:param anchor: Already existing anchor ID from DB id column.
		:param symbol: Already existing symbol ID from DB id column.
		:return: ID column of the created reference link
		"""
		with self.db :
			return self.db.execute("INSERT INTO refs(anchor, symbol) VALUES (?,?)",[anchor, symbol]).lastrowid

	def add_ref_batch(self,data : T.List[T.Tuple[int,int]]):
		"""
		Add several references at once.
		:param data:
		:return:
		"""
		with self.db:
			self.db.executemany("INSERT INTO refs(anchor, symbol) VALUES (?,?)",data)

	def get_symbols_by_name(self,name : str) -> T.List[SQLSymbol]:
		"""
		Retrieve data and return according Symbols objects for a given name.
		:param name: Name to lookup
		:return: a list of all matching symbols
		"""
		results_items : T.List[SQLSymbol] = list()
		with self.db :
			results = self.db.execute("SELECT * FROM fully_qualified_symbols WHERE name == ?", [name]).fetchall()
			results_items = [SQLSymbol.from_fully_qualified_sql_record(x) for x in results]

		return results_items

	def get_symbol_references(self, symbol : SQLSymbol) -> T.List[SQLAnchor]:
		"""
		Retrieve all references anchors for the given symbol object, based upon symbol ID
		:param symbol: Symbol to look references up for.
		:return: A list of references objects
		"""

		with self.db :
			results = self.db.execute("SELECT anchors.*, refs.id as rid, anchor FROM refs INNER JOIN anchors ON anchors.id == refs.anchor WHERE refs.symbol == ?", [symbol.id]).fetchall()
			results_items = [SQLAnchor(x["id"],x["file"],x["start"], x["stop"]) for x in results]
			logger.debug(f"Found references : {results_items}")

		return results_items

	def get_anchor_by_position(self, file : int, position : int) -> T.List[SQLAnchor]:
		"""
		Retrieve the anchor at the given position.
		:param file: File to look into
		:param position: looked up position
		:return: Anchors if any, None otherwise
		"""
		ret = list()
		with self.db :
			result = self.db.execute("SELECT * FROM anchors "
									 "WHERE "
									 "	file == ? "
									 "	AND start <= ? "
									 "	AND stop >= ?",
									 [file,position,position]).fetchall()

			ret = [SQLAnchor(x["id"],x["file"],x["start"],x["stop"]) for x in result]
		return ret

	def get_anchor_by_id(self, aid : int) -> T.Optional[SQLAnchor]:
		with self.db:
			r = self.db.execute("SELECT * FROM anchors WHERE id = ?",[aid]).fetchone()
			if r is not None :
				return SQLAnchor(r["id"], r["file"], r["start"], r["stop"])
		return None

	def get_symbol_by_id(self, sid : int) -> T.Optional[SQLSymbol]:
		"""
		Return a symbol object when given its database ID
		:param sid: Symbol database ID
		:return: Symbol object, or None if not found
		"""
		ret = None
		with self.db :
			r = self.db.execute("SELECT * FROM fully_qualified_symbols WHERE sid == ?",[sid]).fetchone()
			ret = SQLSymbol.from_fully_qualified_sql_record(r)
		return ret

	def get_definition_by_anchor(self,anchor : SQLAnchor) -> T.Optional[SQLSymbol] :
		# First, try to get the symbol from the anchor.
		with self.db :
			r = self.db.execute("SELECT * FROM fully_qualified_symbols WHERE aid == ?",[anchor.id]).fetchone()
			if r is not None :
				return SQLSymbol.from_fully_qualified_sql_record(r)

			else :
				# We have an actual reference.
				r = self.db.execute("SELECT * FROM fully_qualified_symbols "
									"	INNER JOIN refs ON refs.symbol == sid "
									"WHERE anchor == ?",[anchor.id]).fetchone()
				if r is not None :
					return SQLSymbol.from_fully_qualified_sql_record(r)
		return None

	def get_file_by_path(self, path : str):
		with self.db :
			r = self.db.execute("SELECT * FROM files WHERE path == ?",[path]).fetchone()
			if r is not None :
				return SQLFile(r["id"],r["path"],r["content"])
		return None

	def get_file_by_id(self, fid : int):
		with self.db :
			r = self.db.execute("SELECT * FROM files WHERE id == ?",[fid]).fetchone()
			if r is not None :
				return SQLFile(r["id"],r["path"],r["content"])
		return None

	def update_file_content(self,path, content):
		with self.db:
			self.db.execute("UPDATE files SET content = ? WHERE path = ?",[content,path])

	def read_kythe_index(self,index_path : str):
		"""
		Read the .json output of a kythe index run.
		We assume that the definitions are ordered.
		:param path: Path to the JSON file
		:return: None
		"""
		current_node = JSONRecord()
		with open(index_path, "r") as f:
			gc.disable()
			i = 0
			for line in f:
				if line.strip() == "" :
					continue
				data = json.loads(line)
				if not current_node.is_record_appendable(data):
					self._process_kythe_node(current_node)
					current_node.clear()
				current_node.append_record(data)
			self._process_kythe_node(current_node)
			gc.enable()

	def _process_kythe_node(self, node_content : JSONRecord):
		if node_content.is_file :
			self._file_id_mapping[node_content.source.path] = self.add_file(node_content.source.path,node_content.facts["/kythe/text"])
		if node_content.is_anchor :
			self._signature_cache[node_content.source.signature] = self.add_anchor(self._file_id_mapping[node_content.source.path],int(node_content.facts["/kythe/loc/start"]),int(node_content.facts["/kythe/loc/end"]))
			return
		if node_content.is_symbol :
			self._signature_cache[node_content.source.signature] = self.add_symbol(node_content.source.signature,node_content.symbol_type,None)
			return
		if node_content.is_edge :
			if node_content.edge_kind in ["/defines/binding"]:
				anchor_signature = node_content.source.signature
				anchor = self.get_anchor_by_id(self._signature_cache[anchor_signature])
				symbol_id = self._signature_cache[node_content.target.signature]

				self._cache_file_id(anchor.file)

				self._update_symbol_anchor(symbol_id,anchor.id)
				self.update_symbol_name(symbol_id,self._cached_file.content[anchor.start:anchor.end])

			if node_content.edge_kind in ["/ref"]:
				self.add_ref(self._signature_cache[node_content.source.signature], self._signature_cache[node_content.target.signature])
			else:
				return
		return

	def _cache_file_path(self, file_path : str):
		if self._cached_file is None or self._cached_file.path != file_path:
			self._cached_file = self.get_file_by_path(file_path)

	def _cache_file_id(self, file_id : int):
		if self._cached_file is None or self._cached_file.id != file_id:
			self._cached_file = self.get_file_by_id(file_id)