"""Request/response models with strict validation (brief §13)."""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Point(BaseModel):
    """A location given EITHER as projected x/y (m) OR as lon_e/lat (degrees)."""

    model_config = ConfigDict(extra="forbid")
    x: float | None = None
    y: float | None = None
    lon_e: float | None = Field(default=None, description="East-positive longitude, degrees")
    lat: float | None = Field(default=None, ge=-90, le=90, description="Planetocentric latitude, degrees")

    @model_validator(mode="after")
    def exactly_one_form(self) -> "Point":
        xy = self.x is not None and self.y is not None
        ll = self.lon_e is not None and self.lat is not None
        if xy == ll:
            raise ValueError("Provide either x and y, or lon_e and lat")
        for v in (self.x, self.y, self.lon_e, self.lat):
            if v is not None and not math.isfinite(v):
                raise ValueError("Coordinates must be finite")
        return self


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: Point
    end: Point
    profile: str | None = Field(default=None, max_length=40, pattern=r"^[a-z0-9_]+$")
    terrain_source: Literal["auto", "ctx", "hirise_1", "hirise_2"] = "auto"


class WaypointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    location: Point

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank")
        return v


class WaypointPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    location: Point | None = None


class WaypointOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str
    x: float
    y: float
    lon_e: float
    lat: float
    crs_id: str
    crs_version: int
    created_at: datetime
    updated_at: datetime
