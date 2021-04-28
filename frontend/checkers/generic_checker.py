import typing as T

from pygls.lsp.types import Diagnostic, DiagnosticSeverity

class GenericChecker:
	def __init__(self):
		self.executable : str = None
		self.args : T.List[str] = list()
		self.filelist : T.List[str] = list()

		self.diagnostic_content : T.Dict[str,T.List[Diagnostic]] = dict()
		self.nberrors : int = 0

	def run(self) -> Diagnostic:
		raise NotImplementedError

	def clear_file(self,uri):
		if uri in self.diagnostic_content :
			self.nberrors -= len([d for d in self.diagnostic_content[uri] if d.severity == DiagnosticSeverity.Error])
			self.diagnostic_content[uri].clear()

	def clear(self):
		for uri in self.diagnostic_content :
			self.clear_file(uri)

