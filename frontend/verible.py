import base64
import json
import typing as T

from .indexer import IndexItems,SimpleIndexer
from subprocess import Popen, PIPE
import tempfile


class VeribleIndexer(SimpleIndexer) :
	def __init__(self):
		super().__init__()
		self.command_path = "verible-verilog-kythe-extractor"
		self.filelist : T.List[str] = list()
		self.source_root = "/home/julien/Projets/HDL/MPU_KATSV/rtl/sv"


	def dump_file_list(self, path):
		with open(path,"w") as file_handler :
			file_handler.write("\n".join(self.filelist))

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
			data = json.loads("[" + output.decode("ascii").replace("}\n{", "},\n{") + "]")

		self.clear()

		raw_dict : T.Dict[str,T.Dict[str,str]] =dict()
		files : T.Dict[str,str] = dict()

		i = 0
		for elt in data :
			i += 1
			raw_symbul = elt["source"]["signature"]
			symbol = str(raw_symbul) +" - "+ raw_symbul

			fpath =  elt["source"]["path"]
			if symbol not in raw_dict :
				raw_dict[symbol] = dict()
				raw_dict[symbol]["file"] = fpath

			fact_name =  elt["fact_name"]
			value = elt["fact_value"] if "fact_value" in elt else ""
			if fact_name == "/kythe/text":
				files[fpath] = value

			if fact_name == "/" and "edge_kind" in elt :
				fact_name = f"{elt['edge_kind']}"


			target = ""
			if "target" in elt :
				target = elt["target"]["path"]
				target += ":"+ elt["target"]["signature"]

			regfactname = fact_name
			append = 0
			while f"{regfactname}" in raw_dict[symbol] :
				append += 1
				regfactname = f"{fact_name}{append}"

			raw_dict[symbol][regfactname] = value if value != "" else target

			print(f"{i:>4d} {fact_name:32s} - {symbol:50s} = {value} [{target}]")

		for name, symb in raw_dict.items() :
			print(name)
			for k in symb:
				print(f"\t{k:30s} : {symb[k]}")
			if "/kythe/node/kind" in symb and symb["/kythe/node/kind"] == "anchor" :
				beg = int(symb["/kythe/loc/start"])
				end = int(symb["/kythe/loc/end"])
				content = files[symb["file"]][beg:end]
				print(f"\t{'text':30s} : {content}")



# Press the green button in the gutter to run the script.
if __name__ == '__main__' :
	#run()
	pass

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
