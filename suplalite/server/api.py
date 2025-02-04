from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:  # pragma: no cover
    from suplalite.server import Server


def create(server: Server) -> FastAPI:
    router = APIRouter()
    router.add_route(
        "/api/{api_version}/user-icons",
        functools.partial(get_user_icons, server),
        ["GET"],
    )

    api = FastAPI()
    api.include_router(router)
    return api


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

        return JSONResponse(content=jsonable_encoder(response))
