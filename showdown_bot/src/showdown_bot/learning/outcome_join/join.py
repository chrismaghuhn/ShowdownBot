from __future__ import annotations

import gzip
import json
from pathlib import Path

from showdown_bot.learning.outcome_join.contracts import (
    OutcomeLabel, encode_game_outcome, canonical_json,
)


def build_labels(group, mapping, results_by_seed) -> list[OutcomeLabel]:
    labels = []
    for game_id, seed in sorted(mapping.game_to_seed.items()):
        row = results_by_seed[seed]
        winner = str(row["winner"])
        labels.append(OutcomeLabel(
            game_id=game_id, battle_id=str(row["battle_id"]),
            team_hash=group.team_hash, seed_index=int(seed),
            winner=winner, game_outcome=encode_game_outcome(winner),
            final_turn=int(row["turns"]),
        ).validate())
    return labels


def apply_labels(rows: list[dict], labels: list[OutcomeLabel], out_path) -> int:
    """Write a NEW dataset copy with the three sentinels filled for labelled
    battles; untouched rows keep their placeholders. Returns filled-row count."""
    by_game = {lab.game_id: lab for lab in labels}
    filled = 0
    out_path = Path(out_path)
    opener = gzip.open if out_path.suffix == ".gz" else open
    with opener(out_path, "wt", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            gid = str(row["metadata"]["game_id"])
            lab = by_game.get(gid)
            if lab is not None:
                md = dict(row["metadata"])
                md.update(winner=lab.winner, game_outcome=lab.game_outcome,
                          final_turn=lab.final_turn)
                row = {**row, "metadata": md}
                filled += 1
            fh.write(canonical_json(row) + "\n")
    return filled
