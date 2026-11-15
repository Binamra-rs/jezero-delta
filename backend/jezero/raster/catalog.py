"""Layer catalog: the only rasters the API will ever open.

Clients refer to layers by id. Paths are resolved here from
processed/catalog.json and confined to the processed directory, so no
user-supplied path can reach the filesystem (brief §13).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rasterio


class UnknownLayerError(KeyError):
    pass


@dataclass(frozen=True)
class Layer:
    id: str
    title: str
    style: str
    unit: str
    path: Path
    resolution_m: float
    bounds: tuple[float, float, float, float]
    range: tuple[float, float] | None
    kind: str
    source_dataset: str
    meta: dict[str, Any] = field(hash=False, compare=False)

    def contains(self, x: float, y: float) -> bool:
        b = self.bounds
        return b[0] <= x <= b[2] and b[1] <= y <= b[3]

    def public(self) -> dict[str, Any]:
        m = dict(self.meta)
        m.pop("file", None)
        m.pop("tags", None)
        return m


class Catalog:
    def __init__(self, processed_dir: Path, layer_ids: set[str] | None = None):
        self.root = processed_dir.resolve()
        path = self.root / "catalog.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run the pipeline (pipeline/run_all.sh)")
        raw = json.loads(path.read_text())
        self.version = str(raw.get("generated", "0"))
        self.crs = raw["crs"]
        self.boundary = tuple(raw["boundary"])
        self._layers: dict[str, Layer] = {}
        for e in raw["layers"]:
            if layer_ids is not None and e["id"] not in layer_ids:
                continue  # in an older catalog.json but no longer declared in project.yaml
            p = (self.root / e["file"]).resolve()
            if self.root not in p.parents:
                raise ValueError(f"catalog entry {e['id']} escapes the processed directory")
            rng = tuple(e["range"]) if e.get("range") and None not in e["range"] else None
            self._layers[e["id"]] = Layer(
                id=e["id"], title=e["title"], style=e["style"], unit=e.get("unit", ""), path=p,
                resolution_m=float(e["resolution_m"]), bounds=tuple(e["bounds"]), range=rng,
                kind=e.get("kind", "authoritative"), source_dataset=e.get("source_dataset", e["id"]), meta=e)
        self._local = threading.local()

    def __contains__(self, lid: str) -> bool:
        return lid in self._layers

    def get(self, lid: str) -> Layer:
        try:
            return self._layers[lid]
        except KeyError:
            raise UnknownLayerError(lid) from None

    def layers(self) -> list[Layer]:
        return list(self._layers.values())

    def on_demand(self, lid: str) -> bool:
        """True when a derived layer's file is absent but can be recomputed from its DEM.

        Slim deployments (e.g. a free-tier API host) may omit the large HiRISE
        slope/TRI rasters; their point values are then recomputed from the DTM
        with the same Horn / Riley code the pipeline used (identical results).
        """
        layer = self.get(lid)
        if layer.path.exists():
            return False
        deriv = layer.meta.get("derivative")
        src = layer.source_dataset
        return deriv in ("slope", "tri") and src in self._layers and self._layers[src].path.exists()

    def available(self, lid: str) -> bool:
        return self.get(lid).path.exists() or self.on_demand(lid)

    def coverage_path(self, lid: str) -> Path | None:
        rel = self.get(lid).meta.get("coverage_geojson")
        if not rel:
            return None
        p = (self.root / rel).resolve()
        return p if self.root in p.parents and p.exists() else None

    def open(self, lid: str) -> rasterio.io.DatasetReader:
        """Per-thread cached read-only dataset handle (rasterio handles are not thread-safe)."""
        cache = getattr(self._local, "handles", None)
        if cache is None:
            cache = self._local.handles = {}
        ds = cache.get(lid)
        if ds is None or ds.closed:
            ds = cache[lid] = rasterio.open(self.get(lid).path, "r")
        return ds
