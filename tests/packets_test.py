# pylint: disable=redefined-outer-name

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from suplalite import encoding, network, proto
from suplalite.packets import Packet, PacketStream


async def echo_server(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        while True:
            data = await reader.read(1024)
            writer.write(data)
            await writer.drain()
            if reader.at_eof():
                return
    except Exception as exn:  # pragma: no cover
        print(exn)
        raise
    finally:
        writer.close()
        await writer.wait_closed()


@pytest_asyncio.fixture
async def stream() -> AsyncIterator[PacketStream]:
    server = await asyncio.start_server(echo_server, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("localhost", port)
    stream = PacketStream(reader, writer)
    yield stream

    await stream.close()
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_send_then_recv(stream: PacketStream) -> None:
    await stream.send(Packet(proto.Call.DCS_PING_SERVER, b"\x01\x02\x03\x04"))
    packet = await stream.recv()
    assert packet.call_id == proto.Call.DCS_PING_SERVER
    assert packet.data == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_invalid_start_tag(stream: PacketStream) -> None:
    stream.writer.write(b"SPULA" + b"\x00" * (23 - 5))
    await stream.writer.drain()
    with pytest.raises(network.NetworkError) as exc:
        await stream.recv()
    assert str(exc.value) == "Invalid data received; incorrect start tag"


@pytest.mark.asyncio
async def test_invalid_header(stream: PacketStream) -> None:
    stream.writer.write(b"SUPLA" + b"\x00" * (23 - 5))
    await stream.writer.drain()
    with pytest.raises(network.NetworkError) as exc:
        await stream.recv()
    assert str(exc.value) == "Invalid data received; failed to decode header"


@pytest.mark.asyncio
async def test_invalid_version(stream: PacketStream) -> None:
    data = encoding.encode(
        proto.DataPacket(
            0,
            42,
            proto.Call.DCS_PING_SERVER,
            b"\x01\x02\x03\x04",
        )
    )
    stream.writer.write(data)
    await stream.writer.drain()
    with pytest.raises(network.NetworkError) as exc:
        await stream.recv()
    assert str(exc.value) == "Invalid data received; proto version not supported"


@pytest.mark.asyncio
async def test_invalid_end_tag(stream: PacketStream) -> None:
    data = encoding.encode(
        proto.DataPacket(
            proto.PROTO_VERSION,
            42,
            proto.Call.DCS_PING_SERVER,
            b"\x01\x02\x03\x04",
        )
    )
    data = data[:-5] + b"SPULA"
    stream.writer.write(data)
    await stream.writer.drain()
    with pytest.raises(network.NetworkError) as exc:
        await stream.recv()
    assert str(exc.value) == "Invalid data received; incorrect end tag"


@pytest.mark.asyncio
async def test_partial(stream: PacketStream) -> None:
    data = encoding.encode(
        proto.DataPacket(
            proto.PROTO_VERSION,
            42,
            proto.Call.DCS_PING_SERVER,
            b"\x01\x02\x03\x04",
        )
    )
    stream.writer.write(data[:-4])
    await stream.writer.drain()

    with pytest.raises(asyncio.exceptions.TimeoutError):
        await asyncio.wait_for(stream.recv(), timeout=0.5)

    stream.writer.write(data[-4:])
    await stream.writer.drain()

    await stream.recv()
