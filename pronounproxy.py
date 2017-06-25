import asyncio, re
from os import getpid
import s5

"""
Pronoun Proxy: A simple SOCKS5 proxy server that changes gendered pronouns to those of another gender. Listens on port 1080.

Current limitations / bugs:
* Assumes the stream we're proxying uses a line-based protocol (which seems reasonable given that we're manipulating English text)
* Ctrl-C is not properly handled if there is an open connection -- server must be killed manually by PID
* Currently supports only CONNECT requests (and not BIND or UDP ASSOCIATE)
* Connection to client is not always closed immediately when the connection to the destination closes
"""


pronoun_map = {
	b"he": b"she",
	b"him": b"her",
	b"his": b"hers",
	b"she": b"he",
	b"her": b"him",
	b"hers": b"his",
} 
# We also want to change them if they're uppercase or title case
pronoun_map.update(
	[(a.upper(), b.upper()) for a,b in pronoun_map.items()] + 
	[(a.title(), b.title()) for a,b in pronoun_map.items()]
)
# Make a regex that looks like "\b(he|him|...)\b"
pronoun_regex = b"\\b(" + b"|".join(pronoun_map.keys()) + b")\\b"
def swap_pronouns(line):
	return re.sub(
		pronoun_regex,
		lambda match : pronoun_map.get(match.group(0), match.group(0)),
		line
	)

async def handle_socks_client(client_reader, client_writer):
	"""
	Deal with a SOCKS5 client that has connected to us.
	First we have s5.handle_socks5 handle the initial SOCKS5 negotiation and connect to the requested destination.
	Then we set up proxying between the client and the destination, copying everything one sends and passing it along to the other (after changing the text a bit).
	"""
	try:
		reader_writer_pair = await s5.handle_socks5(client_reader, client_writer) # Returns a reader writer pair or False on error
		if not reader_writer_pair:
			print("Error in socks5 negotiation, closing")
			return
		dest_reader, dest_writer = reader_writer_pair
		try:
			print("Proxying data")	
			await asyncio.gather(
				copy_stream(client_reader, dest_writer),
				copy_stream(dest_reader, client_writer, line_filter=swap_pronouns)
			)
		finally:
			dest_writer.close()
	finally:
		client_writer.close()

async def copy_stream(reader, writer, line_filter=(lambda x: x)):
	"""Copy every line the reader reads to the writer (after passing it through line_filter)"""
	"""As a simplifying assumption I'm assuming that whatever protocol we're proxying is line based, which seems reasonable given that we're working with english text."""
	while True:
		line = await reader.readline()
		if not line:
			writer.write_eof()
			break
		writer.write(line_filter(line))

if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	loop.set_debug(True)
	server = loop.run_until_complete(asyncio.start_server(handle_socks_client, '127.0.0.1', 1080, loop=loop))
	print("Server listening on port 1080. (pid %d)" % getpid())
	try:
		loop.run_forever()
	except:
		pass
	server.close()
	loop.close()
