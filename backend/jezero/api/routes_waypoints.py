"""Persistent waypoints scoped to an anonymous workspace key (no accounts).

The browser generates a random workspace key (≥ 32 URL-safe characters,
~190+ bits) and sends it in the `X-Workspace-Key` header. The server stores
only its SHA-256 hash. Anyone holding the key can read and edit that
workspace's waypoints, so the key works like a private link: copy it to another
device to see the same waypoints there. Waypoints live on the server,
never only in the browser (a single SQLite file, see jezero.db).
"""
from __future__ import annotations

import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from .. import db
from ..ratelimit import client_ip
from .routes_map import to_xy
from .schemas import WaypointIn, WaypointOut, WaypointPatch
from .state import AppState, get_state

router = APIRouter(prefix="/api/v1", tags=["waypoints"])

WP_COLS = "id, workspace_id, name, description, x, y, lon_e, lat, crs_id, crs_version, created_at, updated_at"
KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
MAX_WAYPOINTS = 5000


def workspace_key(x_workspace_key: str | None = Header(default=None)) -> str:
    if not x_workspace_key or not KEY_RE.fullmatch(x_workspace_key):
        raise HTTPException(400, "Missing or malformed X-Workspace-Key header (32–128 URL-safe characters)")
    return x_workspace_key


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def _find_workspace(conn, key: str) -> str | None:
    row = conn.execute("SELECT id FROM workspaces WHERE key_hash = ?", (key_hash(key),)).fetchone()
    return row["id"] if row else None


def _get_or_create_workspace(conn, key: str) -> str:
    return conn.execute(
        f"""INSERT INTO workspaces(id, key_hash) VALUES (?, ?)
            ON CONFLICT (key_hash) DO UPDATE SET last_seen_at = {db.NOW} RETURNING id""",
        (str(uuid.uuid4()), key_hash(key))).fetchone()["id"]


def _location(st: AppState, p) -> tuple[float, float, float, float]:
    x, y = to_xy(st, p)
    if not st.boundary.contains(x, y):
        raise HTTPException(422, "Waypoint is outside the Jezero project boundary")
    lon, lat = st.crs.inverse(x, y)
    return x, y, lon, lat


def _owned(conn, wp_id: uuid.UUID, ws: str | None) -> dict:
    row = None
    if ws is not None:
        row = conn.execute(f"SELECT {WP_COLS} FROM waypoints WHERE id = ? AND workspace_id = ?",
                           (str(wp_id), ws)).fetchone()
    if row is None:  # same answer for "missing" and "other workspace"
        raise HTTPException(404, "Waypoint not found")
    return row


@router.get("/waypoints", response_model=list[WaypointOut])
def list_waypoints(key: str = Depends(workspace_key)) -> list[dict]:
    with db.connection() as conn:
        ws = _find_workspace(conn, key)
        if ws is None:
            return []
        return conn.execute(f"SELECT {WP_COLS} FROM waypoints WHERE workspace_id = ? ORDER BY created_at, rowid",
                            (ws,)).fetchall()


@router.post("/waypoints", response_model=WaypointOut, status_code=201)
def create_waypoint(body: WaypointIn, request: Request, key: str = Depends(workspace_key),
                    st: AppState = Depends(get_state)) -> dict:
    st.write_limiter.check("write:" + client_ip(request))
    x, y, lon, lat = _location(st, body.location)
    with db.connection() as conn, db.transaction(conn):
        ws = _get_or_create_workspace(conn, key)
        n = conn.execute("SELECT count(*) AS n FROM waypoints WHERE workspace_id = ?", (ws,)).fetchone()["n"]
        if n >= MAX_WAYPOINTS:
            raise HTTPException(409, f"Waypoint limit ({MAX_WAYPOINTS}) reached for this workspace")
        return conn.execute(
            f"""INSERT INTO waypoints(id, workspace_id, name, description, x, y, lon_e, lat, crs_id, crs_version)
                VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING {WP_COLS}""",
            (str(uuid.uuid4()), ws, body.name, body.description, x, y, lon, lat, st.crs.crs_id, st.crs.version)).fetchone()


@router.get("/waypoints/{wp_id}", response_model=WaypointOut)
def get_waypoint(wp_id: uuid.UUID, key: str = Depends(workspace_key)) -> dict:
    with db.connection() as conn:
        return _owned(conn, wp_id, _find_workspace(conn, key))


@router.patch("/waypoints/{wp_id}", response_model=WaypointOut)
def update_waypoint(wp_id: uuid.UUID, body: WaypointPatch, request: Request, key: str = Depends(workspace_key),
                    st: AppState = Depends(get_state)) -> dict:
    st.write_limiter.check("write:" + client_ip(request))
    with db.connection() as conn, db.transaction(conn):
        ws = _find_workspace(conn, key)
        cur = _owned(conn, wp_id, ws)
        name = body.name.strip() if body.name is not None else cur["name"]
        if not name:
            raise HTTPException(422, "Name must not be blank")
        desc = body.description if body.description is not None else cur["description"]
        if body.location is not None:
            x, y, lon, lat = _location(st, body.location)
            crs_id, crs_v = st.crs.crs_id, st.crs.version
        else:
            x, y, lon, lat, crs_id, crs_v = cur["x"], cur["y"], cur["lon_e"], cur["lat"], cur["crs_id"], cur["crs_version"]
        return conn.execute(
            f"""UPDATE waypoints SET name=?, description=?, x=?, y=?, lon_e=?, lat=?, crs_id=?, crs_version=?,
                       updated_at={db.NOW}
                 WHERE id=? AND workspace_id=? RETURNING {WP_COLS}""",
            (name, desc, x, y, lon, lat, crs_id, crs_v, str(wp_id), ws)).fetchone()


@router.delete("/waypoints/{wp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_waypoint(wp_id: uuid.UUID, request: Request, key: str = Depends(workspace_key),
                    st: AppState = Depends(get_state)) -> Response:
    st.write_limiter.check("write:" + client_ip(request))
    with db.connection() as conn, db.transaction(conn):
        ws = _find_workspace(conn, key)
        res = conn.execute("DELETE FROM waypoints WHERE id = ? AND workspace_id = ?", (str(wp_id), ws)) \
            if ws is not None else None
        if res is None or res.rowcount == 0:
            raise HTTPException(404, "Waypoint not found")
    return Response(status_code=204)
