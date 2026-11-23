"""A deterministic, time-step driven fishing game with a controllable bar."""

import math
import random
from typing import TYPE_CHECKING

from .catalog import FISH_TYPES
from .daily import ensure_daily, record_daily

if TYPE_CHECKING:
    from .model import Farm


class FishingRound:
    """All positions are heights: 0 is bottom and 1 is top.

    ``bar`` is the bar center and ``bar_width`` its full height. Renderers
    may also use ``velocity`` and ``elapsed``; the simulation uses no clock.
    """

    bar_width = 0.26

    def __init__(self, rng=None, *, level: int = 1):
        self._rng = rng if rng is not None else random.Random()
        level = max(1, int(level))
        if level == 1:
            # Keep the original level-1 random stream and species pool.
            self.fish_key = self._rng.choice(
                ("ca_ro", "ca_chep", "ca_hoi", "ca_vang"))
        else:
            choices = [(key, info) for key, info in FISH_TYPES.items()
                       if info.level <= level]
            keys = [key for key, _ in choices]
            weights = [info.weight for _, info in choices]
            self.fish_key = self._rng.choices(keys, weights=weights, k=1)[0]
        self.bar = 0.25
        self.target = self._rng.uniform(0.42, 0.62)
        self.progress = 0.35
        self.done = False
        self.caught = False
        self.claimed = False
        self.velocity = 0.0
        self.elapsed = 0.0
        self._fish_velocity = self._rng.uniform(-0.18, 0.18)
        self._turn_in = self._rng.uniform(0.8, 1.5)

    def step(self, dt: float, holding: bool) -> None:
        """Advance at most a quarter second; terminal stalls cannot skip a round."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Khoảng thời gian phải hữu hạn và không âm.")
        if self.done or dt == 0:
            return
        remaining = min(dt, 0.25)
        # Small physics steps keep motion stable across varying terminal frame rates.
        while remaining > 1e-9 and not self.done:
            tick = min(remaining, 0.025)
            remaining -= tick
            self.elapsed += tick
            self.velocity += (0.95 if holding else -0.95) * tick
            self.velocity *= 0.12 ** tick
            half = self.bar_width / 2
            self.bar += self.velocity * tick
            if self.bar < half:
                self.bar, self.velocity = half, max(0, self.velocity)
            elif self.bar > 1 - half:
                self.bar, self.velocity = 1 - half, min(0, self.velocity)
            self._turn_in -= tick
            if self._turn_in <= 0:
                self._fish_velocity = self._rng.uniform(-0.20, 0.20)
                self._turn_in = self._rng.uniform(0.8, 1.5)
            self.target += self._fish_velocity * tick
            if self.target < 0.08:
                self.target = 0.08
                self._fish_velocity = abs(self._fish_velocity)
            elif self.target > 0.92:
                self.target = 0.92
                self._fish_velocity = -abs(self._fish_velocity)
            inside = abs(self.target - self.bar) <= half
            self.progress = max(0.0, min(1.0, self.progress + (0.24 if inside else -0.16) * tick))
            if self.progress >= 1:
                self.done = self.caught = True
            elif self.progress <= 0 or self.elapsed >= 45:
                self.done = True


def start_fishing(farm: "Farm", rng=None) -> FishingRound:
    from .model import GameError
    from .world import is_near
    from .progression import action_cost

    if not is_near(farm, "water"):
        raise GameError("Hãy đứng cạnh hồ để câu cá.")
    cost = action_cost(farm, 'fish')
    if farm.energy < cost:
        raise GameError(f"Cần {cost} năng lượng để quăng cần.")
    round_ = FishingRound(rng, level=farm.level)
    round_.bar_width += 0.025 * farm.skills['fishing']
    farm._spend_energy(cost)
    return round_


def finish_fishing(farm: "Farm", round: FishingRound) -> str:
    from .catalog import ITEMS
    from .model import GameError

    if not round.done:
        raise GameError("Lượt câu chưa kết thúc.")
    if round.claimed:
        raise GameError("Lượt câu này đã được nhận kết quả.")
    round.claimed = True
    if not round.caught:
        return "Cá đã tuột mất. Hãy thử lại nhé!"
    ensure_daily(farm)
    first = farm.fish_collection.get(round.fish_key, 0) == 0
    farm.items[round.fish_key] += 1
    farm.fish_collection[round.fish_key] = (
        farm.fish_collection.get(round.fish_key, 0) + 1)
    farm.fish_caught += 1
    xp_message = farm.award_xp(5)
    record_daily(farm, 'fish')
    if first:
        record_daily(farm, 'catch_new')
    fish = FISH_TYPES[round.fish_key]
    extra = (f" Loài mới! +{fish.points} điểm sưu tầm." if first else
             f" Sưu tầm: {farm.fish_collection[round.fish_key]} lần.")
    return f"Câu được {fish.name}! {xp_message}{extra}"
