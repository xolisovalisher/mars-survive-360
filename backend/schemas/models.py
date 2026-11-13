"""Pydantic request/response schemas for the MARS SURVIVE 360 REST API (input validation lives here)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LatLon(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="planetocentric latitude, deg N")
    lon: float = Field(..., ge=-180, le=360, description="east longitude, deg E")


class RouteRequest(BaseModel):
    start: LatLon
    goal: LatLon
    strategy: Literal["shortest", "lowest_slope", "lowest_hazard", "balanced", "all"] = "all"
    algorithm: Literal["astar", "weighted_astar", "dijkstra"] = "astar"
    slope_limit_deg: float = Field(20.0, gt=1, le=45)
    scenario: Literal["astronaut", "rover"] = "astronaut"
    include_path: bool = False


class LinkRequest(BaseModel):
    preset: Literal["uhf_orbiter", "base_vhf_local", "x_band_dte"] = "uhf_orbiter"
    freq_hz: float | None = Field(None, gt=1e6, lt=1e11)
    p_tx_w: float | None = Field(None, gt=0, le=1e4)
    g_tx_dbi: float | None = Field(None, ge=-20, le=90)
    g_rx_dbi: float | None = Field(None, ge=-20, le=90)
    distance_m: float | None = Field(None, gt=0, le=1e12)
    bitrate_bps: float | None = Field(None, gt=0, le=1e9)
    t_sys_k: float | None = Field(None, gt=0, le=1e5)
    ebn0_req_db: float | None = Field(None, ge=-5, le=30)


class OxygenRequest(BaseModel):
    distance_m: float = Field(..., gt=0, le=100_000, description="one-way horizontal distance")
    elev_gain_m: float = Field(0.0, ge=-5000, le=5000)
    capacity_l: float = Field(1400.0, gt=0, le=100_000)
    reserve_frac: float = Field(0.25, ge=0, lt=1)
    body_mass_kg: float = Field(75.0, gt=20, le=200)
    suit_mass_kg: float = Field(50.0, ge=0, le=200)
    payload_kg: float = Field(10.0, ge=0, le=200)
    suit_factor: float = Field(1.6, ge=1, le=5)
    round_trip: bool = True


class MarsTimeRequest(BaseModel):
    utc: datetime
    lon_east: float = Field(77.4508, ge=-180, le=360)


class ErrorOut(BaseModel):
    error: str
    detail: str = ""
