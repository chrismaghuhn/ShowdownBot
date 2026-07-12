"""K-world opponent-set sampling for the +Sampling decision axis (2c).

A "world" = a dict ``{to_id(species) -> SpeciesSpreads}`` (opp_sets shape) that
DamageModel/predict_responses already consume. This builds a CRUDE placeholder
distribution from existing data (curated likely-sets vs worst-case book) and
samples K joint worlds deterministically. Pure, no I/O, no RNG globals."""
from __future__ import annotations

import hashlib
import os
import random

from showdown_bot.engine.belief.hypotheses import SpreadBook, SpeciesSpreads

_CURATED_WEIGHT = 0.6
_WORSTCASE_WEIGHT = 0.4


def world_samples() -> int:
    """Number of sampled opponent worlds K (SHOWDOWN_WORLD_SAMPLES), clamped to
    [1, 32]. Default/unparsable/<=0 -> 1 (single most-likely world = byte-identical)."""
    try:
        return max(1, min(32, int(os.environ.get("SHOWDOWN_WORLD_SAMPLES", "1"))))
    except ValueError:
        return 1


def world_seed(seed_base: str, turn: int, board_key: str) -> int:
    """Deterministic per-decision seed via the eval/seeding.py sha256 convention.
    Same (seed_base, turn, board_key) -> same seed -> same worlds."""
    h = hashlib.sha256(f"{seed_base}:{turn}:{board_key}".encode()).hexdigest()
    return int(h[:16], 16)


def build_world_dist(
    opp_mons: list[tuple[str, str]],
    book: SpreadBook,
    opp_sets: dict[str, SpeciesSpreads],
) -> dict[str, list[tuple[SpeciesSpreads, float]]]:
    """Per opponent mon (given as ``(to_id, species_name)``), a weighted candidate
    list of ``SpeciesSpreads``. CRUDE 2-point: curated (if present AND != book
    worst-case) weighted _CURATED_WEIGHT vs the book worst-case _WORSTCASE_WEIGHT,
    renormalized. Mons with a single distinct candidate are OMITTED (they never
    vary -> DamageModel uses its default, same as today)."""
    dist: dict[str, list[tuple[SpeciesSpreads, float]]] = {}
    for tid, species_name in opp_mons:
        wc = book.get(species_name)
        curated = opp_sets.get(tid)
        if curated is not None and curated != wc:
            total = _CURATED_WEIGHT + _WORSTCASE_WEIGHT
            dist[tid] = [(curated, _CURATED_WEIGHT / total), (wc, _WORSTCASE_WEIGHT / total)]
    return dist


def sample_worlds(
    dist: dict[str, list[tuple[SpeciesSpreads, float]]],
    k: int,
    *,
    seed: int,
) -> list[tuple[dict[str, SpeciesSpreads], float]]:
    """K joint worlds + normalized weights. World 0 is always the most-likely
    (each mon's highest-weight set). Worlds 1..K-1 are i.i.d. draws. Empty dist ->
    a single empty world (weight 1.0) = no variation."""
    if not dist:
        return [({}, 1.0)]
    tids = sorted(dist)
    most_likely = {tid: max(dist[tid], key=lambda sw: sw[1])[0] for tid in tids}
    raw: list[tuple[dict, float]] = [(most_likely, _world_prob(most_likely, dist))]
    rng = random.Random(seed)
    for _ in range(max(0, k - 1)):
        world = {tid: _draw(dist[tid], rng) for tid in tids}
        raw.append((world, _world_prob(world, dist)))
    total_w = sum(w for _, w in raw) or 1.0
    return [(world, w / total_w) for world, w in raw]


def _draw(candidates: list[tuple[SpeciesSpreads, float]], rng: random.Random) -> SpeciesSpreads:
    r = rng.random()
    acc = 0.0
    for spreads, w in candidates:
        acc += w
        if r <= acc:
            return spreads
    return candidates[-1][0]


def _world_prob(world: dict[str, SpeciesSpreads], dist: dict) -> float:
    p = 1.0
    for tid, spreads in world.items():
        p *= next((w for s, w in dist[tid] if s == spreads), 0.0)
    return p
