# Navigation measurements

Measured in this checkout on 2026-11-21 with Python's standard library. Run:

```sh
python tools/benchmark_navigation.py
```

The baseline was collected before changing `world.py` or the tutorial BFS.
The final measurement uses the shared A* planner and cached static map rows.
Both runs exercise the tutorial adapter, with the same six scenarios: a field
from spawn, Mai from spawn, an expanded field from the eastern road, forest
work from spawn, the indoor bed, and the indoor exit toward an outdoor shop.
The walking workload replans after each actual movement toward the first two
targets. Automation retains its own deque instead of doing these replans.

| Workload | Baseline wall time (ms) | Final wall time (ms) | Final CPU time (ms) |
| --- | ---: | ---: | ---: |
| 18 calls with the route cache cleared before each | 890.917 | 233.485 | 229.658 |
| 1,200 cached calls | 1.886 | 15.725 | 15.332 |
| 107 walking movements with replanning | 2,869.639 | 211.658 | 203.226 |
| 204,800 `tile_at` lookups | 728.351 | 583.805 | 567.106 |

All six route lengths remain `[50, 57, 104, 6, 8, 9]`; the map checksum remains
`11540425`. The route cache is bounded at 512 entries, actionable goal states
at 256, and static terrain at six area/field-size combinations. Cached calls
now validate the input and read the live NPC positions on every call; that
adds about 12 microseconds per call in this measurement.

The same six uncached routes under `cProfile` dropped from 579,210 function
calls / 0.699 seconds to 23,016 calls / 0.083 seconds. Baseline cumulative hot
functions were `walkable` (38,345 calls / 0.368 s), `tile_at` (38,352 / 0.338 s),
`npc_at` (30,524 / 0.110 s), and `_validate_tile` (75,099 / 0.109 s). Final
cumulative hot functions were the A* search (6 / 0.080 s), dictionary cost
lookups (4,735 / 0.013 s), and the heuristic (2,706 / 0.012 s).

Wall-clock results on this shared host varied across repetitions. These are
observations, with no timing thresholds in the tests. The benchmark also
reports CPU time for future comparisons; CPU time was added after the
baseline and is therefore unavailable for that run. Correctness is checked
separately against an independent queue-based BFS oracle, including final
facing for every plot in field sizes four, five, and six.
