import base64
import json
import typing as T

from subprocess import Popen, PIPE
import tempfile
import gc
import time
import toml

import os
import logging

# bfrom vunit.ui import VUnit

from backend.sql_index_manager import SQLIndexManager

logger = logging.getLogger("myLogger")

class VeribleIndexer :
	def __init__(self, workspace_root):
		self.workspace_root = workspace_root
		self.command_path = "verible-verilog-kythe-extractor"
		self.index = SQLIndexManager()
		self.filelist : T.List[str] = list()
		self.exec_root = ""

	def clear(self):
		self.index.clear()
		#super().clear()
		self.filelist.clear()

	def dump_file_list(self, path):
		with open(path,"w") as file_handler :
			logger.debug(self.filelist)
			file_handler.write("\n".join(self.filelist))

	def read_file_list(self,path):
		if os.path.splitext(path)[1] == ".toml" :
			logger.info(f"Reading TOML file {path}")
			toml_content = toml.load(path)
			flist = toml_content["libraries"]["lib"]["files"]
			valid_extension = [".sv",".v",".svh"]
			new_files = [path for path in flist if os.path.splitext(path)[1].lower() in valid_extension]
			logger.debug(f"Got files {' '.join(new_files)}")
			self.filelist.extend(new_files)
		else :
			with open(path,"r",newline="") as flist :
				for f in flist :
					self.filelist.append(f)

	@property
	def incdir_list(self):
		incdir_list = {os.path.dirname(f) for f in self.filelist}
		ret = list()
		for p in incdir_list :
			if os.path.isabs(p) :
				ret.append(p)
			else:
				ret.append(os.path.join(self.workspace_root,p))
		return ret

	def dump_json_index(self, path):
		data = None
		with tempfile.TemporaryDirectory() as work_dir:
			filelist = f"{work_dir}/files.fls"
			self.dump_file_list(filelist)
			incdir_list = ",".join(self.incdir_list)

			command = [self.exec_root + self.command_path,
					   "--file_list_root",
					   "/",
					   # self.workspace_root,
					   "--print_kythe_facts",
					   "json_debug",
					   "--include_dir_paths",
					   incdir_list,
					   "--file_list_path",
					   filelist]
			logger.info(f"Run indexer command {' '.join(command)}")
			index_path = path
			with open(index_path, "w") as index_file:
				process = Popen(command, stdout=index_file, stderr=PIPE)
				(t, err) = process.communicate()

				exit_code = process.wait()

			if exit_code != 0 or err != b"":
				err_string = f"Error when running the indexer. Output code {exit_code}\n{err.decode('ascii')}"
				for line in err_string.split("\n"):
					logger.error(line)
				return

	def run_indexer(self):
		data = None
		with tempfile.TemporaryDirectory() as work_dir :
			filelist = f"{work_dir}/files.fls"
			self.dump_file_list(filelist)
			incdir_list = ",".join(self.incdir_list)

			command = [self.exec_root+self.command_path,
							 "--file_list_root",
							 "/",
							 #self.workspace_root,
							 "--print_kythe_facts",
							 "json",
					        "--include_dir_paths",
					        incdir_list,
							 "--file_list_path",
							 filelist]
			logger.info(f"Run indexer command {' '.join(command)}")
			index_path = f"{work_dir}/index.json"
			with open(index_path,"w") as index_file :
				process = Popen(command, stdout=index_file, stderr=PIPE)
				(t,err) = process.communicate()

				exit_code = process.wait()

			if exit_code != 0 or err != b"":
				err_string = f"Error when running the indexer. Output code {exit_code}\n{err.decode('ascii')}"
				for line in err_string.split("\n") :
					logger.error(line)
				return

			self.clear()
			self.read_index_file(index_path)

	def read_index_file(self, index_path):
		self.index.read_kythe_index(index_path)


# Press the green button in the gutter to run the script.
if __name__ == '__main__' :
	#run()
	pass

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
