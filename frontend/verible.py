import base64
import json
import typing as T

from .indexers import IndexItems,KytheIndexer
from .indexers import KytheRef
from subprocess import Popen, PIPE
import tempfile
import gc
import time

import os
import logging

# bfrom vunit.ui import VUnit


logger = logging.getLogger("myLogger")

class VeribleIndexer(KytheIndexer) :
	def __init__(self):
		super().__init__()
		self.command_path = "verible-verilog-kythe-extractor"
		self.filelist : T.List[str] = list()
		self.exec_root = ""

	def clear(self):
		super().clear()
		self.filelist.clear()

	def dump_file_list(self, path):
		with open(path,"w") as file_handler :
			file_handler.write("\n".join(self.filelist))

	def read_file_list(self,path):
		with open(path,"r",newline="") as flist :
			for f in flist :
				self.filelist.append(f)

	def sort_files(self):
		# vu = VUnit.from_argv()
		# vu.add_verification_components()
		# lib = vu.add_library("lib")
		#
		# for f in self.filelist :
		# 	lib.add_source_file(file_name=f)
		# self.filelist = [f.name for f in vu.get_compile_order()]
		pass

	def run_indexer(self):
		data = None
		with tempfile.TemporaryDirectory() as work_dir :
			filelist = f"{work_dir}/files.fls"
			self.dump_file_list(filelist)
			command = [self.exec_root+self.command_path,
							 "--file_list_root",
							 self.workspace_root,
							 "--print_kythe_facts",
							 "json",
							 "--file_list_path",
							 filelist]
			logger.info(f"Run indexer command {' '.join(command)}")
			index_path = f"{work_dir}/index.json"
			with open(index_path,"w") as index_file :
				process = Popen(command, stdout=index_file, stderr=PIPE)
				(t,err) = process.communicate()

				exit_code = process.wait()

			if exit_code != 0 or err != b"":
				logger.error(f"Error when running the indexer. Output code ",exit_code, "\n",err.decode("ascii"))
				return

			self.clear()
			self.read_index_file(index_path)

	def read_index_file(self, index_path):
		with open(index_path, "r") as f:
			KytheRef.root_path = os.path.dirname(os.path.abspath(index_path))
			tstart = time.time()
			logger.info(f"Reading data from {index_path}...")
			text = ""

			gc.disable()
			i = 0
			for line in f:
				if line.strip() == "" :
					continue
				data = json.loads(line)
				self.tree.add_and_link_element(data)
				i += 1
				if (i % 1000) == 0:
					logger.debug(f"Handled {i:6d} elements")

			gc.enable()
		logger.debug(f"Done {i} elements in {time.time() - tstart}s.")
		logger.info("Resolving tree...")
		self.tree.solve_edges()
		self.refresh_files()
		self.refresh_anchors()


# Press the green button in the gutter to run the script.
if __name__ == '__main__' :
	#run()
	pass

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
