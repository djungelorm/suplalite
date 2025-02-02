import asyncio
import asyncio.selector_events
import asyncio.trsock
import socket
from collections.abc import Callable, Coroutine
from typing import Any, cast

import tlslite  # type: ignore

_DEFAULT_LIMIT = 2**16  # 64 KiB


# Note: ssl library bundled with Python does not support older TLS versions
# required by some SUPLA devices. We use tlslite as it has support for older protocols.

# Note: must manually call TLSSocket.handshakeServer on connection, as this needs
# to be done in an async function to not block the async loop


class NetworkError(Exception):
    pass


class TLSSocket:
    def __init__(
        self,
        raw_sock: socket.socket,
        cert: tlslite.api.X509CertChain,
        key: tlslite.utils.rsakey.RSAKey,
        session_cache: tlslite.api.SessionCache,
        settings: tlslite.HandshakeSettings,
    ) -> None:
        self._raw_sock = raw_sock
        self._ssl_sock = tlslite.TLSConnection(raw_sock)
        self._connected = False
        self._cert = cert
        self._key = key
        self._session_cache = session_cache
        self._settings = settings

    async def do_handshake(self) -> None:
        assert not self._connected
        # Perform initial ssl handshake
        # Note this must be done in an async function so that the
        # handshake does not block the async loop
        for _ in self._ssl_sock.handshakeServerAsync(
            certChain=self._cert,
            privateKey=self._key,
            sessionCache=self._session_cache,
            settings=self._settings,
            reqCert=False,
        ):
            await asyncio.sleep(0)
        self._connected = True

    def recv(self, bufsize: int) -> bytes:
        if not self._connected:
            raise BlockingIOError
        try:
            return cast(bytes, self._ssl_sock.recv(bufsize))
        except ConnectionResetError:  # pragma: no cover
            return b""
        except tlslite.TLSAbruptCloseError:  # pragma: no cover
            return b""

    def send(self, data: bytes) -> int:
        assert self._connected
        return cast(int, self._ssl_sock.send(data))

    def close(self) -> None:
        self._ssl_sock.close()

    def shutdown(self, how: Any) -> None:  # pragma: no cover
        self._ssl_sock.shutdown(how)


ClientConnectedCallback = Callable[
    [asyncio.StreamReader, asyncio.StreamWriter], Coroutine[Any, Any, None]
]


class TLSProtocol(asyncio.StreamReaderProtocol):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        cb: ClientConnectedCallback,
        loop: asyncio.AbstractEventLoop,
        cert: tlslite.api.X509CertChain,
        key: tlslite.utils.rsakey.RSAKey,
        session_cache: tlslite.api.SessionCache,
        settings: tlslite.HandshakeSettings,
    ) -> None:
        super().__init__(reader, cb, loop=loop)
        self._ssl_cert = cert
        self._ssl_key = key
        self._ssl_session_cache = session_cache
        self._ssl_settings = settings

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # Replace the raw socket in the transport with a TLSSocket that wraps the raw socket
        raw_sock = transport.get_extra_info("socket")
        if isinstance(raw_sock, asyncio.trsock.TransportSocket):  # pragma: no cover
            raw_sock = raw_sock._sock  # type: ignore  # pylint: disable=protected-access
        ssl_sock = TLSSocket(
            raw_sock,
            self._ssl_cert,
            self._ssl_key,
            self._ssl_session_cache,
            self._ssl_settings,
        )
        transport._sock = ssl_sock  # type: ignore  # pylint: disable=protected-access
        super().connection_made(transport)


async def start_secure_server(
    client_connected_cb: ClientConnectedCallback,
    host: str,
    port: int,
    cert: tlslite.api.X509CertChain,
    key: tlslite.utils.rsakey.RSAKey,
    settings: tlslite.HandshakeSettings,
) -> asyncio.Server:
    session_cache = tlslite.api.SessionCache()

    loop = asyncio.get_running_loop()

    def factory() -> TLSProtocol:
        reader = asyncio.StreamReader(limit=_DEFAULT_LIMIT, loop=loop)
        return TLSProtocol(
            reader,
            client_connected_cb,
            loop,
            cert=cert,
            key=key,
            session_cache=session_cache,
            settings=settings,
        )

    return await loop.create_server(factory, host, port)
