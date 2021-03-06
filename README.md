# Pronoun Proxy
A simple SOCKS5 proxy server that changes gendered pronouns to those of another gender.
Written as a coding task for an assignment to a summer internship. I also used this as an excuse to teach myself how to use coroutines and Python's `asyncio` module.

## Requirements
* Python 3.5 or later (uses coroutines with `async / await` syntax)

## Usage
`python3 pronounproxy.py` starts a SOCKS5 server listening on 127.0.0.1 port 1080.
You can test it out using `netcat`:
```
nc -x 127.0.0.1:1080 (destination) (port)
```
tells netcat to try to connect to (destination):(port) through the proxy.

## Limitations
* Assumes the stream we're proxying uses a line-based protocol (which seems reasonable given that we're manipulating English text)
* Currently supports only CONNECT requests (and not BIND or UDP ASSOCIATE)

## Other known issues I would fix given more time
* Ctrl-C is not properly handled when there are open connections -- KeyboardInterrupts don't seem to propagate until `reader.readline()` returns.
* Connection to client is not always closed in a timely manner when the connection to the destination closes
