import tempfile
import logging
import json
import typing as T

from pygls.lsp.types import Position
from pygls.lsp.types import Diagnostic, Range, DiagnosticSeverity
from pygls.uris import from_fs_path, to_fs_path
from subprocess import Popen, PIPE
from .generic_checker import GenericChecker

logger = logging.getLogger("myLogger")

class VeribleSyntaxChecker(GenericChecker):
	def __init__(self):
		super().__init__()
		self.default_args = ["--export_json"]


	def run(self):
		self._run(incr=False)

	def run_incremental(self,files : T.Optional[T.List[str]] = None):
		for f in files :
			if f not in self.filelist :
				self.filelist.append(f)
			self.clear_file(from_fs_path(f))
		self._run(incr=True,force_fset = files)

	def _run(self,incr = False, force_fset : T.Optional[T.List[str]] = None):
		with tempfile.TemporaryDirectory() as work_dir:
			filelist = self.filelist if force_fset is None else force_fset
			command = [self.executable]
			command.extend(self.default_args)
			command.extend(self.args)
			command.extend(filelist)

			logger.info(f"Run syntax checker command {' '.join(command)}")

			error_return = f"{work_dir}/syntax-check.json"
			with open(error_return, "w") as error_file:
				process = Popen(command, stdout=error_file, stderr=PIPE)
				(t, err) = process.communicate()
				exit_code = process.wait()

			if exit_code not in (0,1) or err != b"":
				err_string = f"Error when running the syntax checker. Output code {exit_code}\n{err.decode('ascii')}"
				for line in err_string.split("\n"):
					logger.error(line)
				return

			if not incr:
				self.clear()
			# If no error found, will return 0
			if exit_code == 1 :
				self.read_error_file(error_return)

	def _register_diagnostic(self, uri : str, d : Diagnostic):
		if d.severity == DiagnosticSeverity.Error :
			self.nberrors += 1
		if uri not in self.diagnostic_content:
			self.diagnostic_content[uri] = list()
		self.diagnostic_content[uri].append(d)

	def read_error_file(self,path : str):
		with open(path,"r") as jsfile :
			data = json.load(jsfile)
			for file, content in data.items() :
				uri = from_fs_path(file)
				for severity_label, record_list in content.items() :
					severity = DiagnosticSeverity.Error
					# To change if we have something else than error
					for r in record_list :
						position = Position(line=r["line"],character=r["column"])
						diagnostic = Diagnostic(range = Range(start=position,end=position),
												message = "Parse error : rejected token.  ",
												source="Verible Syntax",
												code="syntax-error",
												severity=severity)
						logger.info(f"Register error {uri}:{r['line']}")
						self._register_diagnostic(uri, diagnostic)



