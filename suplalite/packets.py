import asyncio
import ssl
from dataclasses import dataclass

import tlslite

from suplalite import encoding, network, proto

MINIMUM_PACKET_SIZE = len(
    encoding.encode(proto.DataPacket(0, 0, proto.Call.DCS_PING_SERVER, b""))
)

MAX_RR_ID = 2**31 - 1  # max value for c_int32


@dataclass
class Packet:
    call_id: proto.Call
    data: bytes = b""


class PacketStream:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        proto_version: int = proto.PROTO_VERSION,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._proto_version = proto_version

        self._recv_buffer = b""
        self._next_send_rr_id = 1

    @property
    def writer(self) -> asyncio.StreamWriter:
        return self._writer

    @property
    def proto_version(self) -> int:
        return self._proto_version

    async def recv(self) -> Packet:
        while True:
            if self._have_packet():
                return self._next_packet()
            try:
                data = await self._reader.read(proto.MAX_DATA_SIZE)
            except ConnectionResetError as exc:  # pragma: no cover
                raise network.NetworkError(str(exc)) from exc
            except tlslite.errors.TLSAbruptCloseError as exc:  # pragma: no cover
                raise network.NetworkError(str(exc)) from exc
            if len(data) == 0:
                raise network.NetworkError("eof")
            self._recv_buffer += data

    def _next_packet(self) -> Packet:
        msg, size = encoding.decode(proto.DataPacket, self._recv_buffer)
        # Note: we switch to the client's protocol version, capped by the
        # server's
        self._proto_version = min(msg.version, proto.PROTO_VERSION)
        packet = Packet(msg.call_id, msg.data)
        self._recv_buffer = self._recv_buffer[size:]
        return packet

    def _have_packet(self) -> bool:
        # Returns whether the buffer starts with a complete packet.
        # Note: raises NetworkError if the buffer holds invalid data.
        size = len(self._recv_buffer)

        # Check we have enough bytes for a minimally sized packet
        if size < MINIMUM_PACKET_SIZE:
            return False

        # Check the start tag
        if self._recv_buffer[: len(proto.TAG)] != proto.TAG:
            raise network.NetworkError("Invalid data received; incorrect start tag")

        # Decode the packet header
        try:
            fields, _ = encoding.partial_decode(
                proto.DataPacket, self._recv_buffer, num_fields=5
            )
        except Exception as exc:
            raise network.NetworkError(
                "Invalid data received; failed to decode header"
            ) from exc

        # Check the protocol version
        if fields[1] < proto.PROTO_VERSION_MIN:
            raise network.NetworkError(
                "Invalid data received; proto version not supported"
            )

        # Check the size field matches the data size
        expected_size = MINIMUM_PACKET_SIZE + fields[4]
        if size < expected_size:
            return False

        # Check the end tag
        if (
            self._recv_buffer[expected_size - len(proto.TAG) : expected_size]
            != proto.TAG
        ):
            raise network.NetworkError("Invalid data received; incorrect end tag")

        # A complete packet, possibly with more data after it
        return True

    async def send(self, packet: Packet) -> None:
        data = encoding.encode(
            proto.DataPacket(
                self._proto_version,
                self._next_send_rr_id,
                packet.call_id,
                packet.data,
            )
        )
        self._advance_send_rr_id()
        try:
            self._writer.write(data)
            await self._writer.drain()
        except ConnectionResetError as exc:  # pragma: no cover
            raise network.NetworkError(str(exc)) from exc
        except tlslite.errors.TLSAbruptCloseError as exc:  # pragma: no cover
            raise network.NetworkError(str(exc)) from exc

    def _advance_send_rr_id(self) -> None:
        # Increment rr_id, wrapping to one before it overflows
        if self._next_send_rr_id < MAX_RR_ID:
            self._next_send_rr_id += 1
        else:
            self._next_send_rr_id = 1

    async def close(self) -> None:
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except ssl.SSLError:  # pragma: no cover
            # Ignore ssl errors while closing the connection
            pass
