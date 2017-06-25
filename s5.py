import asyncio, socket, struct

async def read_pstring(reader):
	"""Read a Pascal-style string (one-byte length followed by that many bytes) from the stream."""
	length = ord(await reader.readexactly(1))
	assert(0 <= length < 256)
	return await reader.readexactly(length)

async def read_atyp_addr(reader):
	"""
	Read an (atyp, addr) pair from the stream.
	Return the address as a string suitable for passing into asyncio.open_connection() (e.g., "1.2.3.4" or "example.com")
	Raise ValueError if atyp is an invalid address type
	"""
	atyp = ord(await reader.readexactly(1))
	if atyp == 0x01: # IPv4
		return socket.inet_ntop(socket.AF_INET, await reader.readexactly(4))
	elif atyp == 0x03: # Domain name
		return (await read_pstring(reader)).decode('utf-8')
	elif atyp == 0x04: # IPv6
		return socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
	else:
		raise ValueError("Unrecognized ATYP: 0x%02X" % atyp)

async def handle_version_method(reader, writer):
	"""
	Read in the client's version identifier/authentication method selection message and send our reply. Only supports the "No authentication required" method.
	Return True if negotiation succeeds, False otherwise

	Client message format:
	+----+----------+----------+
	|VER | NMETHODS | METHODS  |
	+----+----------+----------+
	| 1  |    1     | 1 to 255 |
	+----+----------+----------+

	Reply format:
	+----+--------+
	|VER | METHOD |
	+----+--------+
	| 1  |    1   |
	+----+--------+

	(diagrams from RFC 1928)
	"""
	version = ord(await reader.readexactly(1))
	if version != 5:
		print("Bad version: %d" % version)
		return False
	methods = await read_pstring(reader)
	if 0x00 in methods:
		writer.write(b"\x05\x00") # 0x00 is the "No authentication required" method
		await writer.drain()
		return True
	else:
		writer.write("\x05\xFF") # 0xFF means "No acceptable methods"
		await writer.drain()
		print("No acceptable methods")
		return False

async def handle_connection_request(reader, writer):
	"""
	Read in a SOCKS connection request, make the requested connection, and send our reply to the client.
	Return a connection to the destination as a (reader, writer) pair, or False in case of error.

	Currently only allows the CONNECT request type (and not BIND or UDP ASSOCIATE)

	SOCKS request format:
	+----+-----+-------+------+----------+----------+
	|VER | CMD |  RSV  | ATYP | DST.ADDR | DST.PORT |
	+----+-----+-------+------+----------+----------+
	| 1  |  1  | X'00' |  1   | Variable |    2     |
	+----+-----+-------+------+----------+----------+

	Reply format:
	+----+-----+-------+------+----------+----------+
	|VER | REP |  RSV  | ATYP | BND.ADDR | BND.PORT |
	+----+-----+-------+------+----------+----------+
	| 1  |  1  | X'00' |  1   | Variable |    2     |
	+----+-----+-------+------+----------+----------+
	(diagrams from RFC 1928)
	"""
	version, command, reserved = await reader.readexactly(3)
	if version != 5 or reserved != 0:
		raise ValueError("Malformed SOCKS request")
	dst_addr = await read_atyp_addr(reader)
	dst_port = struct.unpack(">H", await reader.readexactly(2))[0]

	if command == 0x01: # CONNECT
		print("Requested to connect to {}:{}".format(dst_addr, dst_port))
		try:
			dest_reader, dest_writer = await asyncio.open_connection(dst_addr, dst_port)
		except:
			print("Error connecting to destination")
			writer.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00") # General failure
			await writer.drain()
			return False

		# BND.ADDR and BND.PORT are the address and port of our end of the connection to the destination
		#(i.e., the address and port the destination sees the connection as coming from)
		my_addr = dest_writer.get_extra_info('sockname',default=('0.0.0.0',0))
		# my_addr is (IP, port) for IPv4 and (IP, port, flowinfo, scopeid) for IPv6
		my_ip = my_addr[0]
		my_port = my_addr[1]
		ipv6 = (len(my_addr) == 4)
		reply = b"\x05\x00\x00" + \
			(b"\x04" if ipv6 else b"\x01") + \
			socket.inet_pton(socket.AF_INET6 if ipv6 else socket.AF_INET, my_ip) + \
			struct.pack(">H", my_port)
		writer.write(reply)
		await writer.drain()
		return dest_reader, dest_writer
	else:
		writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00") # Command not supported
		await writer.drain()
		return False


async def handle_socks5(reader, writer):
	"""
	Deal with the SOCKS5 negotiation (as the server),
	i.e., do everything up to (but not including) the point that we begin proxying actual data between client and destination.
	Returns an open connection to the destination as a (reader, writer) pair, or returns False in the case of any protocol error.
	Caller is responsible for closing the streams in case of error. According to RFC 1928 this must happen within 10 seconds of the failure.
	"""
	try:
		if not await handle_version_method(reader, writer): return False
		return await handle_connection_request(reader, writer)
	except ValueError as e:
		print("Protocol error: %s" % e)
		return False

if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	reader, writer = loop.run_until_complete(asyncio.open_connection("localhost","12345"))
	#print(loop.run_until_complete(read_pstring(reader)))
	destr_destw = loop.run_until_complete(handle_socks5(reader, writer))
	if not destr_destw:
		writer.close()
		exit()
	
