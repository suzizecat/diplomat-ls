import typing as T
from enum import Flag


class Capabilities(Flag) :
	VALIDATOR = 0
	LINT = 1
	INDEX = 2

class GenericFrontend:
	def __init__(self):
		self.capabilities : Capabilities = None

	def run_index(self, filelist : T.List[str]) :
		raise NotImplementedError
