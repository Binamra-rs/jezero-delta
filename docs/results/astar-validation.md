# A* validation report

Generated 2026-11-14T14:35:16+00:00 on Python 3.14.9 / NumPy 2.5.4.

A* (backend/jezero/routing/astar.py) is compared against SciPy's compiled Dijkstra (backend/jezero/routing/reference.py) on the **same directed edge weights**. A case passes when both report no route, or the costs agree to 1e-9 relative.

| Terrain | Profile | Pairs | Passed | Unreachable | Mean A* expansions | Mean A* time | Mean Dijkstra time |
|---|---|---:|---:|---:|---:|---:|---:|
| smooth 60×80, 150 m relief | cautious | 20 | 20 | 0 | 940 | 3.5 ms | 3.0 ms |
| smooth 60×80, 150 m relief | balanced | 20 | 20 | 0 | 1066 | 4.1 ms | 3.4 ms |
| smooth 60×80, 150 m relief | direct | 20 | 20 | 0 | 359 | 1.9 ms | 4.2 ms |
| rough 60×80, 300 m relief | cautious | 20 | 20 | 14 | 118 | 1.5 ms | 1.4 ms |
| rough 60×80, 300 m relief | balanced | 20 | 20 | 3 | 623 | 3.0 ms | 1.6 ms |
| rough 60×80, 300 m relief | direct | 20 | 20 | 1 | 507 | 2.2 ms | 2.4 ms |
| 60×80 with 10 % NoData | cautious | 20 | 20 | 0 | 1160 | 4.4 ms | 3.4 ms |
| 60×80 with 10 % NoData | balanced | 20 | 20 | 0 | 1258 | 4.9 ms | 3.4 ms |
| 60×80 with 10 % NoData | direct | 20 | 20 | 0 | 530 | 2.6 ms | 3.5 ms |
| 120×120 with 5 % NoData | cautious | 20 | 20 | 19 | 22 | 1.4 ms | 3.7 ms |
| 120×120 with 5 % NoData | balanced | 20 | 20 | 1 | 3642 | 18.4 ms | 11.6 ms |
| 120×120 with 5 % NoData | direct | 20 | 20 | 3 | 1232 | 18.9 ms | 14.1 ms |

**Result: 240/240 cases agree with Dijkstra.**

Behavioural tests (detours around steep terrain, NoData handling, blocked cells, corner cutting, endpoints, boundary mask, directional costs) are in `backend/tests/test_routing.py`; run `pytest -q backend/tests`.
