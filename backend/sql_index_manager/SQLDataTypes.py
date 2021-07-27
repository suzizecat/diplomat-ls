import typing as T


class SQLFile:
	def __init__(self, id : T.Optional[int] = None, path : T.Optional[str]= None, content : T.Optional[str] = None):
		self.id = id
		self.path = path
		self.content = content

class SQLAnchor:
	def __init__(self, id : int = None, file : int = None, start : int = None, end : int = None):
		self.id= id
		self.file = file
		self.start = start
		self.end = end

	@property
	def is_valid(self) -> bool:
		return self.id is not None and self.file is not None and self.start is not None and self.end is not None

	def __len__(self):
		return self.end - self.start

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
		ret = cls(record["sid"], record["name"], record["type"], SQLAnchor(record["aid"], record["file"], record["start"], record["stop"]))
		return ret

	@property
	def is_valid(self):
		# Don't use type at the moment
		return self.id is not None and self.name is not None and self.declaration_anchor is not None
