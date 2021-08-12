import typing as T
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
		if self.is_edge :
			return False
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

	@property
	def anchor_start(self) -> int:
		ret = self.get_fact("/kythe/loc/start")
		return None if ret is None else int(ret)

	@property
	def anchor_end(self) -> int:
		ret = self.get_fact("/kythe/loc/end")
		return None if ret is None else int(ret)

	@property
	def file_content(self) -> str:
		return self.get_fact("/kythe/text")

	def get_fact(self,fact) -> T.Union[None,str]:
		return self.facts[fact] if fact in self.facts else None


class SQLFile:
	def __init__(self, id : T.Optional[int] = None, path : T.Optional[str]= None, content : T.Optional[str] = None):
		self.id = id
		self.path = path
		self.content = content

	def position_from_offset(self,offset : int) -> T.Tuple[int,int]:
		"""
		First line is 0
		First char is 1
		:param offset:
		:return:
		"""
		line = max(0,self.content[:offset].count("\n"))
		char = offset - self.content[:offset].rfind("\n")
		return (line,char)

	def offset_from_position(self,line : int, char : int):
		# Lets assume first line = 0

		position = 0
		line_start = self.content.find("\n")
		if line == 0 :
			line_start = 0
		else :
			for i in range(line-1) :
				line_start = self.content.find("\n",line_start +1)
				if line_start == -1 :
					logger.warning(f"offset_from_position : offset not found for position {line}:{char} in file {self.path}")
					return -1
		position = line_start + char - (1 if line_start == 1 else 0)

		logger.debug(f"Query offset for {line}:{char} got {position} on file {self.path}")
		return position


class SQLAnchor:
	def __init__(self, id : int = None, file : int = None, start : T.Tuple[int,int] = None, end : T.Tuple[int,int] = None):
		self.id= id
		self.file = file
		self.start_line = start[0]
		self.start_char = start[1]
		self.end_line = end[0]
		self.end_char = end[1]

	@property
	def is_valid(self) -> bool:
		return self.id is not None and self.file is not None and self.start is not None and self.end is not None

	def __len__(self):
		return self.end_char - self.start_char

	@property
	def db_record(self):
		return [self.id, self.file,self.start_line,self.start_char,self.end_line,self.end_char]

	@classmethod
	def from_json_record(cls,record : JSONRecord, resolved_file : SQLFile ) -> "SQLAnchor":
		"""
		Generate an anchor object given a JSON record and the proper resolved file.
		The ID field won't be set.
		:param record: JSON record object
		:param resolved_file: SQL File descriptor attached to the new anchor
		:return:
		"""

		return cls(None,resolved_file.id,
				  resolved_file.position_from_offset(record.anchor_start),
				  resolved_file.position_from_offset(record.anchor_end))

	@classmethod
	def from_sql_record(cls,row : T.Dict[str,T.Any] ) -> "SQLAnchor":
		"""
		Generate an anchor object given a JSON record and the proper resolved file.
		The ID field won't be set.
		:param record: JSON record object
		:param resolved_file: SQL File descriptor attached to the new anchor
		:return:
		"""

		return cls(row["id"],row["file"],
				   (row["start_line"],row["start_char"]),
				  (row["stop_line"],row["stop_char"]))

class SQLSymbol :
	def __init__(self, id : int = None , name : str = None, type : str = None , declaration_anchor : SQLAnchor = None):
		self.id = id
		self.name = name
		self.type = type
		self.declaration_anchor = declaration_anchor

	@classmethod
	def from_fully_qualified_sql_record(cls, record):
		"""
		Create a SQLSymbol from a row from "fully qualified symbols" table
		:param record: Dictionnary which keys matches the fully_qualified_symbols row definition
		:return: the build Symbol
		"""
		ret = cls(record["sid"], record["name"], record["type"],
				  SQLAnchor(
					  record["aid"],
					  record["file"],
					  (record["start_line"],record["start_char"]),
					  (record["stop_line"],record["stop_char"])))
		return ret

	@property
	def is_valid(self):
		# Don't use type at the moment
		return self.id is not None and self.name is not None and self.declaration_anchor is not None
