# 10 — Acceptance criteria matrix

Status key: **Tested** = verified by automated tests in this repository · **Built** = implemented, must be
demonstrated with the real data / deployment · **Owner** = needs a decision or input from the project owner.

| ID | Requirement | Implementation | How to demonstrate | Status |
|---|---|---|---|---|
| AC-01 | Only the Jezero Delta boundary | `boundary` in config → clipped COGs, tile matrix = boundary, OL view extent, server-side boundary checks for inspect/route/waypoints | pan to edges; request outside → 422 | Built · boundary **Owner** to confirm |
| AC-02 | CTX orthomosaic renders | default visible layer `ctx_ortho` | open site | Built |
| AC-03 | All five datasets represented | 5 authoritative layers in catalog | layer panel shows 5 `SOURCE` layers | Built |
| AC-04 | Independent layer toggles | per-layer visibility/opacity/order | toggle each | Built |
| AC-05 | Alignment in canonical CRS | explicit PROJ pipelines, grid-aligned COGs, step 07 offsets | `07-alignment.md`, `07-alignment.md` hillshade offsets (QA only; hillshade is not a map layer) | Built |
| AC-06 | NoData & coverage correct | masks → transparent tiles; "No Data" in inspector; coverage outlines + % | click outside HiRISE/THEMIS footprints | Tested (API smoke test) · Built |
| AC-07 | Derivatives reproducible & documented | `terrain.py`, step 04, doc 04, gdaldem cross-check | `pytest`, `04-derivatives.md` | Tested |
| AC-08 | Select two points and route | A/B tools, inspector & waypoint shortcuts, route bar | UI | Built |
| AC-09 | Terrain-dependent A\* | cost model in doc 05 | `pytest tests/test_routing.py` | Tested |
| AC-10 | Steep terrain penalised | slope + grade terms; blocking above limit | detour tests | Tested |
| AC-11 | Unsupported terrain / NoData handled | NoData impassable, explicit 409/422 | NoData tests, API smoke test | Tested |
| AC-12 | Route statistics shown | `stats.py`, Route tab | UI | Tested (stats) · Built (UI) |
| AC-13 | Click retrieves actual values | native-pixel sampler | API smoke test, UI | Tested · Built |
| AC-14 | Source & resolution shown | every sample carries source, resolution, kind, coverage | inspector | Built |
| AC-15 | Waypoint CRUD | API + UI | UI | Built |
| AC-16 | Persistence across restarts/devices | SQLite, workspace-key scoped (no accounts) | paste the workspace key on a second device | Built — accounts removed at owner's request; cross-device sync is by key |
| AC-17 | Public domain over HTTPS | Pages + Tunnel | `https://astro-mars.wiki` | Built — deploy pending |
| AC-18 | No local dev server needed | VPS + Pages; build refuses localhost API | production URL | Built — deploy pending |
| AC-19 | Transformations documented | docs 01–05 + generated reports | review | Built (reports generated on real data) |
| AC-20 | Hand-over | this repository + reports + deployment | owner sign-off | Owner |

## Open items requiring the project owner

1. Boundary set to the whole Jezero crater (77.10–78.06° E, 17.90–18.86° N); confirm.
2. Exact product IDs and files for HiRISE DTM 1 and 2; CTX orthomosaic file name.
3. Clarify the "5 m" CTX orthomosaic: the USGS Mars 2020 TRN mosaic is documented at ~6 m/pixel.
4. VPS, Cloudflare account access, and the `astro-mars.wiki` zone.
5. Review routing profile weights against mission-planning expectations.

## Additions after the first hand-over

| Feature | Implementation | Status |
|---|---|---|
| NASA Perseverance raw-image gallery | `backend/jezero/nasa_raw.py` (validated, cached proxy), `frontend/src/components/RawImages.tsx` | Tested (proxy logic) · Built (UI) |
| Mars Survival Hub (proof of concept) | `frontend/src/components/SurvivalHub.tsx`; procedures are placeholders by design | Built |
| Account removal | workspace keys (no user table) | Built |
