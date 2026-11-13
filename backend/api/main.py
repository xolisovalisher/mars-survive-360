"""FastAPI application: REST access to the computational core (same functions as the Streamlit UI).

Run:  uvicorn backend.api.main:app --port 8601      (or: python main.py api)
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import config as C
from backend.schemas.models import LinkRequest, MarsTimeRequest, OxygenRequest, RouteRequest
from backend.services import compute
from mars_survive.common import get_logger

log = get_logger("api")
app = FastAPI(title="MARS SURVIVE 360 API", version=C.VERSION,
              description="Mission planning & analysis core for Jezero crater. Results carry a data_class label; "
                          "simplified models — not flight-certified guidance.")


@app.exception_handler(ValueError)
async def _value_error(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"error": "invalid_input", "detail": str(exc)[:300]})


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.error("API error: %s", exc.__class__.__name__, exc_info=exc)       # no request bodies / secrets logged
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": exc.__class__.__name__})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": C.VERSION, "dem": compute.grid_info()}


@app.get("/api/terrain/stats")
def terrain_stats():
    return compute.terrain_stats()


@app.post("/api/route")
def route(req: RouteRequest):
    return compute.route(req)


@app.post("/api/link-budget")
def link_budget(req: LinkRequest):
    return compute.link(req)


@app.post("/api/oxygen")
def oxygen(req: OxygenRequest):
    return compute.oxygen(req)


@app.post("/api/mars-time")
def mars_time(req: MarsTimeRequest):
    return compute.mars_clock(req)


