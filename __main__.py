import argparse
from main import diplomat_server
import logging

logger = logging.getLogger("myLogger")
# Log to file handler
formatter = logging.Formatter("{levelname:8s} {asctime:s} - {message}", style="{")

log_file_handler = logging.FileHandler("run.log", "w")
log_file_handler.setFormatter(formatter)
log_file_handler.setLevel(logging.DEBUG)
logger.addHandler(log_file_handler)

log_srv_handler = logging.FileHandler("run.srv.log", "w")
log_srv_handler.setFormatter(formatter)
log_srv_handler.setLevel(logging.DEBUG)

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
	parser.add_argument(
		"--full-log", action="store_true",
		help="Enable logging of server transaction"
	)
	parser.add_argument(
		"--debug", action="store_true",
		help="Avoid catching errors to let them show up on logs"
	)

	# parser.add_argument(
	# 	"--teros", action="store_true",
	# 	help="Prepare setup for use with TerosHDL"
	# )


def main():
	parser = argparse.ArgumentParser()
	add_arguments(parser)
	args = parser.parse_args()

	if args.full_log :
		server_logger = logging.getLogger()
		server_logger.addHandler(log_srv_handler)

	if args.verbosity > 0 :
		level = max(logging.ERROR - 10*args.verbosity, logging.DEBUG)
		logging.root.setLevel(level)

	diplomat_server.debug = args.debug
	if args.tcp :
		logger.addHandler(stream_handler)
		logger.info(f"Start server on TCP port {args.port}")
		diplomat_server.start_tcp(args.host, args.port)

	else:
		logger.info("Starting server on IO mode.")
		diplomat_server.start_io()


if __name__ == "__main__" :
	main()