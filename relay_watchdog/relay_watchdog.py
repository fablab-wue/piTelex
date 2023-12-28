#!/usr/bin/env python3

import argparse
#import socket
import threading
import socketserver
import pigpio
import time

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

	def handle(self):
		response = ""
		timeleft = self.server.data["next_off"] - time.time()
		if timeleft < 0:
			timeleft = 0
			response = "PIN turned on for {} seconds".format(self.server.data["duration"])
		else:
			response = "PIN on time extended for {:.1f} seconds".format(self.server.data["duration"]-timeleft)
		self.server.data["next_off"] = time.time() + self.server.data["duration"]
		if verbose > 2 :
			print(response)
		response = bytes("{}\n".format(response), 'ascii')
		self.request.sendall(response)

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
	pass

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description='Listen on a socket for connections and toggle a GPIO pin high for a certain amount of time', 
		allow_abbrev=True
	)
	parser.add_argument('--host', type=str, metavar="localhost", default="localhost", help="IP address to listen on")
	parser.add_argument('-p', '--port', type=int, metavar=22000, default=22000, help="Port to listen on")
	parser.add_argument('-d', '--duration', type=int, metavar=300, default=300, help="Default time to keep the GPIO pin high for")
	parser.add_argument('-g', '--gpio', type=int, metavar=27, default=27, help="GPIO pin to toggle")
	parser.add_argument('--pigpio', type=str, metavar="hostname", default="", help="Hostname of ip address of pigpiod")
	
	parser.add_argument('-v', '--verbose', action="count", default=1, help="Be (more) verbose" )
	parser.add_argument('-q', '--quiet', action="store_true", default=False, help="Be quiet, only output errors")

	args = parser.parse_args()

	if args.quiet :
		verbose = 0
	else:
		verbose = args.verbose

	state = {}
	state["next_off"] = time.time()
	state["duration"] = args.duration

	server = ThreadedTCPServer((args.host, args.port), ThreadedTCPRequestHandler)
	server.data = state
	with server:
		ip, port = server.server_address
		if verbose :
			print("Listening on {}:{}".format(ip,port))
		# Start a thread with the server -- that thread will then start one
		# more thread for each request
		server_thread = threading.Thread(target=server.serve_forever)
		# Exit the server thread when the main thread terminates
		server_thread.daemon = True
		server_thread.start()
		if verbose > 1:
			print("Server loop running in thread:", server_thread.name)

		# Setup pigpio
		pi = pigpio.pi(args.pigpio)
		if not pi.connected:
			raise Exception('no connection to remote RPi: {}'.format(args.pigpio))
		pi.set_mode(args.gpio, pigpio.OUTPUT)
		pi.write(args.gpio,0)
		pinstate = False
		if verbose > 1:
			print("OFF")

		old_remaining=-1
		while True:
			try:
				if pinstate and state["next_off"] <= time.time():
					pi.write(args.gpio,0)
					pinstate = False
					if verbose > 1:
						print("OFF")
				if (not pinstate) and state["next_off"] > time.time():
					pi.write(args.gpio,1)
					pinstate = True
					if verbose > 1:
						print("ON")
				if pinstate and verbose > 2 :
					remaining = state["next_off"]-time.time()
					if remaining < 0 :
						remaining = 0
					if remaining != old_remaining :
						print("{:10.1f} seconds left.".format(remaining), end="\r")
						old_remaining = remaining
			except KeyboardInterrupt:
				print('Interrupted')
				break

			except Exception as e:
				print("ERROR: {}".format(str(e)))
				break

		pi.write(args.gpio,0)
		pinstate = False
		if verbose > 1:
			print("OFF")
		pi.stop()
		server.shutdown()
		if verbose:
			print("Server stopped")