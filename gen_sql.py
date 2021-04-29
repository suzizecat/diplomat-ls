from frontend import VeribleIndexer
import argparse

def process_args():
	parser = argparse.ArgumentParser()
	parser.add_argument("--input",type=str, help="json file to process")
	parser.add_argument("--output",type=str, help="path to sql output", default=":memory:")
	return parser.parse_args()


def run():
	args = process_args()
	indexer = VeribleIndexer(args.output)
	indexer.tree.sql_clear()
	indexer.read_index_file(args.input)

if __name__ == "__main__":
	run()
