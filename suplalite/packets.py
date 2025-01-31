import asyncio
import ssl
from dataclasses import dataclass

import tlslite  # type: ignore

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
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._proto_version = proto.PROTO_VERSION

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
            if self._reader.at_eof():
                raise network.NetworkError("eof")
            try:
                self._recv_buffer += await self._reader.read(proto.MAX_DATA_SIZE)
            except ConnectionResetError as exc:  # pragma: no cover
                raise network.NetworkError(str(exc))
            except tlslite.errors.TLSAbruptCloseError as exc:  # pragma: no cover
                raise network.NetworkError(str(exc))

    def _next_packet(self) -> Packet:
        msg, size = encoding.decode(proto.DataPacket, self._recv_buffer)
        # Note: switch to protocol version that the client supports, capped by the max
        # version that the server supports
        self._proto_version = min(msg.version, proto.PROTO_VERSION)
        packet = Packet(msg.call_id, msg.data)
        self._recv_buffer = self._recv_buffer[size:]
        return packet

    def _have_packet(self) -> bool:
        # Raise NetworkError if there is invalid data in the buffer
        # If there is a valid packet at the start of the buffer return its size
        # If there is a valid partial packet at the start of the buffer return None
        size = len(self._recv_buffer)

        # check we have enough bytes for a minimally sized packet
        if size < MINIMUM_PACKET_SIZE:
            return False

        # check we have correct start tag
        if self._recv_buffer[: len(proto.TAG)] != proto.TAG:
            raise network.NetworkError("Invalid data received; incorrect start tag")

        # decode packet header
        try:
            fields, _ = encoding.partial_decode(
                proto.DataPacket, self._recv_buffer, num_fields=5
            )
        except Exception as exc:
            raise network.NetworkError(
                "Invalid data received; failed to decode header"
            ) from exc

        # check we have correct version
        if fields[1] < proto.PROTO_VERSION_MIN:
            raise network.NetworkError(
                "Invalid data received; proto version not supported"
            )

        # check size matches with data size
        expected_size = MINIMUM_PACKET_SIZE + fields[4]
        if size < expected_size:
            return False

        # check end tag
        if (
            self._recv_buffer[expected_size - len(proto.TAG) : expected_size]
            != proto.TAG
        ):
            raise network.NetworkError("Invalid data received; incorrect end tag")

        # have a complete packet, possibly with more data after
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
        self._writer.write(data)
        await self._writer.drain()

    def _advance_send_rr_id(self) -> None:
        # Increment rr_id without overflowing back to zero
        if self._next_send_rr_id < MAX_RR_ID:  # pragma: no branch
            self._next_send_rr_id += 1
        else:
            self._next_send_rr_id = 1  # pragma: no cover

    async def close(self) -> None:
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except ssl.SSLError:
            # ignore ssl errors when closing connection
            pass
