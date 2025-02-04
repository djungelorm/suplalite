from __future__ import annotations

import functools
from typing import TYPE_CHECKING

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
        ids = tuple(int(x) for x in request.query_params["ids"].split(","))
        for icon_id in ids:
            icon = server.state.get_icon(icon_id)
            response.append(
                {
                    "id": icon_id,
                    "images": icon.data,
                    "imagesDark": icon.data,
                }
            )
        return JSONResponse(content=jsonable_encoder(response))
