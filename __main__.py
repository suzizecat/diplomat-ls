import argparse
from main import diplomat_server
import logging

logger = logging.getLogger()
# Log to file handler
log_file_handler = logging.FileHandler("run.log", "w")
log_file_handler.setLevel(logging.DEBUG)
logger.addHandler(log_file_handler)
# Log to stdout handler
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)

def add_arguments(parser : argparse.ArgumentParser):
	parser.description = "Diplomat SV LSP"

	parser.add_argument(
		"--tcp", action="store_true",
		help="Use TCP server instead of stdio"
	)
	parser.add_argument(
		"--host", default="127.0.0.1",
		help="Bind to this address"
	)
	parser.add_argument(
		"--port", type=int, default=2087,
		help="Bind to this port"
	)
	parser.add_argument(
		"-v", dest="verbosity", default=0, action="count",
		help="Verbosity level. Add a v to increase, up to -vvv"
	)

def main():


	parser = argparse.ArgumentParser()
	add_arguments(parser)
	args = parser.parse_args()

	if args.verbosity > 0 :
		level = max(logging.ERROR - 10*args.verbosity, logging.DEBUG)
		logging.root.setLevel(level)


	if args.tcp :
		logger.addHandler(stream_handler)
		logger.info(f"Start server on TCP port {args.port}")
		diplomat_server.start_tcp(args.host, args.port)

	else:
		logger.info("Starting server on IO mode.")
		diplomat_server.start_io()


if __name__ == "__main__" :
	main()