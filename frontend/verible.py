import base64
import json
import typing as T

from .indexers import IndexItems,KytheIndexer
from subprocess import Popen, PIPE
import tempfile
import gc
import time

from vunit.ui import VUnit


class VeribleIndexer(KytheIndexer) :
	def __init__(self):
		super().__init__()
		self.command_path = "verible-verilog-kythe-extractor"
		self.filelist : T.List[str] = list()
		self.source_root = "/home/julien/Projets/HDL/MPU_KATSV/rtl/sv"

	def dump_file_list(self, path):
		with open(path,"w") as file_handler :
			file_handler.write("\n".join(self.filelist))

	def sort_files(self):
		unit = VUnit("")
		for f in self.filelist :
			VUnit.add_source_file(file_name=f,library_name="work")
		self.filelist = [f.name for f in VUnit.get_compile_order()]

	def run_indexer(self):
		data = None
		with tempfile.TemporaryDirectory() as work_dir :
			filelist = f"{work_dir}/files.fls"
			self.dump_file_list(filelist)
			command = [self.command_path,
							 "--file_list_root",
							 self.source_root,
							 "--print_kythe_facts",
							 "json",
							 "--file_list_path",
							 filelist]
			print(f"Run command {' '.join(command)}")
			process = Popen(command, stdout=PIPE, stderr=PIPE)
			(output, err) = process.communicate()
			exit_code = process.wait()

			if exit_code != 0 or err != b"":
				print(f"Error when running the indexer. Output code ",exit_code, "\n",err.decode("ascii"))
				return

			self.clear()
			self.read_index_file(filelist)

	def read_index_file(self, index_path):
		with open(index_path, "r") as f:
			tstart = time.time()
			print("Reading data...")
			text = ""

			gc.disable()
			i = 0
			for line in f:
				text += line
				if line == "}\n":
					data = json.loads(text)
					self.tree.add_and_link_element(data)
					text = ""
					i += 1
					if (i % 1000) == 0:
						print(f"Handled {i:6d} elements")

			gc.enable()
		print(f"Done {i} elements in {time.time() - tstart}s.")
		print("Resolving tree...")
		self.tree.solve_edges()
		self.refresh_files()
		self.refresh_anchors()


# Press the green button in the gutter to run the script.
if __name__ == '__main__' :
	#run()
	pass

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
