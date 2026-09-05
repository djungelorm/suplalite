from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from suplalite import proto
from suplalite.server.events import EventQueue

if TYPE_CHECKING:  # pragma: no cover
    from suplalite.server import Connection, Server


logger = logging.getLogger("suplalite.server")


class BaseContext:
    server: Server
    events: EventQueue
    name: str

    def __init__(self, server: Server, events: EventQueue, name: str) -> None:
        self.server = server
        self.events = events
        self.name = name

    def log(self, msg: str, level: int = logging.INFO) -> None:
        if not logger.isEnabledFor(level):  # pragma: no cover
            return
        logger.log(level, "%s %s", self.name, msg)


class ServerContext(BaseContext):
    pass


class ConnectionContext(BaseContext):
    conn: Connection
    activity_timeout: int
    # indicates whether an error occured in a handler
    error: bool

    def __init__(
        self,
        server: Server,
        events: EventQueue,
        name: str,
        conn: Connection,
        activity_timeout: int | None = None,
        error: bool = False,
    ) -> None:
        super().__init__(server, events, name)
        self.conn = conn
        # Note: read the default here rather than as a parameter default, which
        # would bind proto.ACTIVITY_TIMEOUT_DEFAULT at import time
        if activity_timeout is None:
            activity_timeout = proto.ACTIVITY_TIMEOUT_DEFAULT
        self.activity_timeout = activity_timeout
        self.error = error

        self._replacement: ClientContext | DeviceContext | None = None

    def replace(self, context: ClientContext | DeviceContext) -> None:
        self._replacement = context

    @property
    def should_replace(self) -> bool:
        return self._replacement is not None

    @property
    def replacement(self) -> ClientContext | DeviceContext:
        assert self._replacement is not None
        return self._replacement


class ClientContext(ConnectionContext):
    guid: bytes
    client_id: int
    authorized: bool

    def __init__(self, context: ConnectionContext, guid: bytes, client_id: int) -> None:
        super().__init__(
            context.server,
            context.events,
            context.name,
            context.conn,
            context.activity_timeout,
            context.error,
        )
        self.guid = guid
        self.client_id = client_id
        self.authorized = False


class DeviceContext(ConnectionContext):
    guid: bytes
    device_id: int

    def __init__(self, context: ConnectionContext, guid: bytes, device_id: int) -> None:
        super().__init__(
            context.server,
            context.events,
            context.name,
            context.conn,
            context.activity_timeout,
            context.error,
        )
        self.guid = guid
        self.device_id = device_id
