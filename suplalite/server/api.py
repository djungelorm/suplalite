from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:  # pragma: no cover
    from suplalite.server import Server

logger = logging.getLogger("suplalite.server")


def create(server: Server) -> FastAPI:
    router = APIRouter()
    router.add_route(
        "/api/{api_version}/user-icons",
        functools.partial(get_user_icons, server),
        ["GET"],
    )

    api = FastAPI()
    api.include_router(router)
    api.exception_handler(404)(handle_404)
    api.exception_handler(500)(handle_500)
    return api


def _log(request: Request, status_code: int, msg: str, level: int) -> None:
    address = "?"
    if request.client is not None:  # pragma: no branch
        address = request.client.host
    logger.log(
        level,
        "%s %s %s -- %d %s",
        address,
        request.method,
        request.url.path,
        status_code,
        msg,
    )


def handle_error(
    request: Request, status_code: int, msg: str, level: int
) -> JSONResponse:
    _log(request, status_code, msg, level)
    return JSONResponse(status_code=status_code, content={"message": msg})


async def handle_404(request: Request, _: Any) -> JSONResponse:
    return handle_error(request, 404, "Not found", logging.WARN)


async def handle_500(request: Request, _: Any) -> JSONResponse:  # pragma: no cover
    return handle_error(request, 500, "Internal server error", logging.ERROR)


async def get_user_icons(server: Server, request: Request) -> JSONResponse:
    async with server.state.lock:
        response = []

        if "ids" in request.query_params:
            ids = [int(x) for x in request.query_params["ids"].split(",")]
        else:
            ids = [icon.id for icon in server.state.get_icons()]

        include: list[str] = []
        if "include" in request.query_params:
            include = request.query_params["include"].split(",")

        for icon_id in ids:
            icon = server.state.get_icon(icon_id)
            entry: dict[str, Any] = {
                "id": icon_id,
            }
            if "images" in include:
                entry["images"] = icon.data
                entry["imagesDark"] = icon.data
            response.append(entry)

        _log(request, 200, "OK", logging.DEBUG)
        return JSONResponse(content=jsonable_encoder(response))
