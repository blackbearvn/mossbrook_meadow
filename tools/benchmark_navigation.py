"""Reproducible navigation/render benchmark; no timing assertions or dependencies.

Run before and after changes with ``python tools/benchmark_navigation.py``.
The tutorial adapter is intentionally the entrypoint for both measurements.
"""
import argparse
import cProfile
import io
import json
from pathlib import Path
import pstats
import sys
from time import perf_counter, process_time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmgame import tutorial, world
from farmgame.model import Farm


def scenarios():
    return (
        (Farm(), 'village', (26, 42), 'plot'),
        (Farm(), 'village', (55, 20), 'npc'),
        (Farm(size=6, player_x=110, player_y=21), 'village', (31, 47), 'plot'),
        (Farm(), 'village', (9, 13), 'forest'),
        (Farm(area='home', player_x=8, player_y=7), 'home', world.BED, 'bed'),
        (Farm(area='home', player_x=3, player_y=3), 'village', world.SHOP_DOOR, 'shop'),
    )


def clear_routes():
    planner = getattr(tutorial, '_navigate', None)
    if planner is None:
        from farmgame.navigation import _navigate as planner
    planner.cache_clear()


def route_suite(repeats, *, cold=False):
    cases = scenarios()
    lengths = []
    for _ in range(repeats):
        for farm, area, target, kind in cases:
            if cold:
                clear_routes()
            _, path, _ = tutorial._route(farm, area, target, kind=kind)
            lengths.append(len(path))
    return lengths


def walking_suite():
    moves = 0
    for farm, area, target, kind in scenarios()[:2]:
        for _ in range(256):
            _, path, key = tutorial._route(farm, area, target, kind=kind)
            if not path:
                if key != 'E':
                    raise RuntimeError('Benchmark destination became unreachable')
                break
            dx, dy = path[0][0] - farm.player_x, path[0][1] - farm.player_y
            direction = {(0, -1): 'up', (0, 1): 'down', (-1, 0): 'left', (1, 0): 'right'}[(dx, dy)]
            if not world.move(farm, direction):
                raise RuntimeError('Benchmark planner returned a blocked step')
            moves += 1
        else:
            raise RuntimeError('Benchmark exceeded the movement bound')
    return moves


def render_suite(repeats):
    checksum = 0
    for _ in range(repeats):
        for y in range(world.VILLAGE_HEIGHT):
            for x in range(world.VILLAGE_WIDTH):
                checksum += ord(world.tile_at('village', x, y, 6))
    return checksum


def measured(work):
    start = perf_counter()
    cpu_start = process_time()
    value = work()
    return (round((perf_counter() - start) * 1000, 3),
            round((process_time() - cpu_start) * 1000, 3), value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cold-repeats', type=int, default=3)
    parser.add_argument('--warm-repeats', type=int, default=200)
    parser.add_argument('--render-repeats', type=int, default=25)
    args = parser.parse_args()
    clear_routes()
    cold_ms, cold_cpu_ms, lengths = measured(lambda: route_suite(args.cold_repeats, cold=True))
    route_suite(1)
    warm_ms, warm_cpu_ms, _ = measured(lambda: route_suite(args.warm_repeats))
    clear_routes()
    walk_ms, walk_cpu_ms, moves = measured(walking_suite)
    render_ms, render_cpu_ms, checksum = measured(lambda: render_suite(args.render_repeats))
    print(json.dumps({
        'cold_routes': {'count': 6 * args.cold_repeats, 'milliseconds': cold_ms, 'cpu_milliseconds': cold_cpu_ms,
                        'path_lengths': lengths[:6]},
        'warm_routes': {'count': 6 * args.warm_repeats, 'milliseconds': warm_ms, 'cpu_milliseconds': warm_cpu_ms},
        'walking_replans': {'moves': moves, 'milliseconds': walk_ms, 'cpu_milliseconds': walk_cpu_ms},
        'tile_lookups': {'count': world.VILLAGE_WIDTH * world.VILLAGE_HEIGHT * args.render_repeats,
                         'milliseconds': render_ms, 'cpu_milliseconds': render_cpu_ms, 'checksum': checksum},
    }, indent=2))
    profile = cProfile.Profile()
    profile.runcall(route_suite, 1, cold=True)
    buffer = io.StringIO()
    pstats.Stats(profile, stream=buffer).strip_dirs().sort_stats('cumulative').print_stats(12)
    print(buffer.getvalue())


if __name__ == '__main__':
    main()
