"""Team catalog, coverage and out-of-distribution auditing (Phase 3,
dataset-reranker-audit slice, Task 6). Validates an optional team catalog
(team_hash -> team_id/archetype/declared_split), reports per-split coverage
(games/decisions/rows, candidate-count distribution, action classes,
game_mode/turn buckets, decision-flag shares, team/archetype counts), and
fits a per-decision out-of-distribution score on the train split that scores
validation/test (and optional external reference datasets). Offline/pure: no
network, no live battle imports.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditCorpus, AuditError, Finding, Severity, canonical_json, make_finding, quantile,
)
from showdown_bot.learning.audit.features import feature_rows, is_sentinel
from showdown_bot.learning.audit.integrity import load_and_audit_integrity
from showdown_bot.learning.dataset import action_class


@dataclass(frozen=True)
class TeamInfo:
    team_hash: str
    team_id: str
    archetype: str
    declared_split: str


def load_team_catalog(path) -> dict[str, TeamInfo]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise AuditError("team catalog must be a list")
    allowed = {"team_hash", "team_id", "archetype", "declared_split"}
    out = {}
    for index, item in enumerate(data):
        if set(item) != allowed:
            raise AuditError(f"team catalog row {index} fields mismatch")
        info = TeamInfo(**{key: str(item[key]) for key in allowed})
        if info.team_hash in out and out[info.team_hash] != info:
            raise AuditError(f"conflicting team hash {info.team_hash}")
        out[info.team_hash] = info
    return {key: out[key] for key in sorted(out)}


def row_action_class(row) -> str:
    return action_class(row)


def audit_team_coverage(corpus, team_catalog) -> list[Finding]:
    if team_catalog is None:
        return [make_finding(
            code="TEAM_CATALOG_UNAVAILABLE", severity=Severity.INFO, scope="team",
            message="team and archetype coverage is unavailable", remediation="provide --team-catalog",
        )]
    game_team = {}
    for decision in corpus.decisions:
        team_hash = str(decision.rows[0]["metadata"].get("team_hash", ""))
        game_team.setdefault(decision.game_id, team_hash)
        if game_team[decision.game_id] != team_hash:
            raise AuditError(f"game {decision.game_id} has conflicting team hashes")
    unknown = sorted(game for game, team_hash in game_team.items() if team_hash not in team_catalog)
    findings = []
    if unknown:
        findings.append(make_finding(
            code="UNKNOWN_TEAM_HASH", severity=Severity.WARN, scope="team",
            message="games reference hashes absent from the team catalog", count=len(unknown),
            denominator=len(game_team), examples=unknown,
            remediation="extend the catalog or document intentionally unknown teams",
        ))
    return findings


def train_reference(train_decisions) -> dict:
    rows = feature_rows(train_decisions)
    numeric, categorical = {}, {}
    for feature in sorted({name for row in rows for name in row}):
        values = [row.get(feature) for row in rows]
        present = [value for value in values if not is_sentinel(value)]
        if present and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
            xs = [float(v) for v in present]
            median = quantile(sorted(xs), 0.5)
            q1, q3 = quantile(sorted(xs), 0.25), quantile(sorted(xs), 0.75)
            numeric[feature] = {"min": min(xs), "max": max(xs), "median": median,
                                "scale": q3 - q1 if q3 > q1 else max(abs(median), 1.0)}
        else:
            categorical[feature] = {canonical_json(v) for v in present}
    return {"numeric": numeric, "categorical": categorical}


def decision_ood_score(decision, reference) -> tuple[float, dict]:
    row_components, row_feature_contributions = [], []
    for row in decision.rows:
        unseen, out_range, distance, missing = [], [], [], []
        feature_contributions = defaultdict(float)
        for feature in sorted(set(reference["numeric"]) | set(reference["categorical"])):
            value = row["features"].get(feature)
            if is_sentinel(value):
                is_missing = 1.0
                missing.append(is_missing)
                feature_contributions[feature] += is_missing / 4.0
                continue
            if feature in reference["numeric"] and isinstance(value, (int, float)):
                ref = reference["numeric"][feature]
                outside = float(value < ref["min"] or value > ref["max"])
                numeric_distance = min(abs(float(value) - ref["median"]) / ref["scale"], 10.0) / 10.0
                out_range.append(outside)
                distance.append(numeric_distance)
                feature_contributions[feature] += (outside + numeric_distance) / 4.0
            elif feature in reference["categorical"]:
                is_unseen = float(canonical_json(value) not in reference["categorical"][feature])
                unseen.append(is_unseen)
                feature_contributions[feature] += is_unseen / 4.0
            missing.append(0.0)
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        components = {"unseen": mean(unseen), "out_of_range": mean(out_range),
                      "numeric_distance": mean(distance), "missing": mean(missing)}
        row_components.append(components)
        row_feature_contributions.append(feature_contributions)
    merged = {key: sum(row[key] for row in row_components) / len(row_components)
              for key in ("unseen", "out_of_range", "numeric_distance", "missing")}
    feature_totals = {
        feature: sum(row.get(feature, 0.0) for row in row_feature_contributions)
                 / len(row_feature_contributions)
        for feature in sorted({key for row in row_feature_contributions for key in row})
    }
    top_features = sorted(feature_totals.items(), key=lambda item: (-item[1], item[0]))[:20]
    return sum(merged.values()) / 4.0, {
        "components": merged,
        "top_features": [{"feature": feature, "contribution": value}
                         for feature, value in top_features],
    }


def coverage_metrics(corpus, team_catalog) -> dict:
    result = {}
    for split in ("train", "validation", "test"):
        decisions = corpus.decisions_by_split[split]
        games = sorted({decision.game_id for decision in decisions})
        rows = [row for decision in decisions for row in decision.rows]
        action_games, mode_games, turn_games = defaultdict(set), defaultdict(set), defaultdict(set)
        format_games, config_games, teacher_games = defaultdict(set), defaultdict(set), defaultdict(set)
        for decision in decisions:
            for row in decision.rows:
                action_games[row_action_class(row)].add(decision.game_id)
                mode_games[str(row["features"].get("game_mode", "unknown"))].add(decision.game_id)
                turn = int(row["metadata"].get("turn", 0) or 0)
                turn_games["1-3" if turn <= 3 else "4-6" if turn <= 6 else "7+"].add(decision.game_id)
                format_games[str(row["metadata"].get("format_id", "unknown"))].add(decision.game_id)
                config_games[str(row["metadata"].get("config_hash", "unknown"))].add(decision.game_id)
                teacher_games[str(row["metadata"].get("teacher_version", "unknown"))].add(decision.game_id)
        teams = Counter()
        archetypes = Counter()
        for game_id in games:
            decision = next(d for d in decisions if d.game_id == game_id)
            team_hash = str(decision.rows[0]["metadata"].get("team_hash", ""))
            teams[team_hash] += 1
            if team_catalog and team_hash in team_catalog:
                archetypes[team_catalog[team_hash].archetype] += 1
        result[split] = {
            "games": len(games), "decisions": len(decisions), "rows": len(rows),
            "candidate_count": dict(sorted(Counter(len(d.rows) for d in decisions).items())),
            "action_classes": {key: len(value) for key, value in sorted(action_games.items())},
            "game_modes": {key: len(value) for key, value in sorted(mode_games.items())},
            "turn_buckets": {key: len(value) for key, value in sorted(turn_games.items())},
            "formats": {key: len(value) for key, value in sorted(format_games.items())},
            "config_hashes": {key: len(value) for key, value in sorted(config_games.items())},
            "teacher_versions": {key: len(value) for key, value in sorted(teacher_games.items())},
            "decision_flags": {
                "trainable": sum(bool(d.rows[0]["metadata"]["teacher_config"]["trainable_label"])
                                 for d in decisions),
                "non_trainable": sum(not bool(d.rows[0]["metadata"]["teacher_config"]["trainable_label"])
                                     for d in decisions),
                "strict_unique": sum(
                    len(d.rows) > 1
                    and sum(bool(r["label"]["teacher_best"]) for r in d.rows) == 1
                    and sum(bool(r["label"]["chosen_by_current_heuristic"]) for r in d.rows) == 1
                    for d in decisions),
                "tie": sum(sum(bool(r["label"]["teacher_best"]) for r in d.rows) > 1
                           for d in decisions),
                "forced": sum(len(d.rows) == 1 for d in decisions),
                "multi_candidate": sum(len(d.rows) > 1 for d in decisions),
            },
            "teams": dict(sorted(teams.items())) if team_catalog else "unavailable",
            "archetypes": dict(sorted(archetypes.items())) if team_catalog else "unavailable",
        }
    return result


def audit_ood(corpus, config: AuditConfig):
    train = corpus.decisions_by_split["train"]
    if not train:
        finding = make_finding(
            code="OOD_TRAIN_SPLIT_EMPTY", severity=Severity.FAIL, scope="ood",
            message="OOD reference cannot be fit without train decisions",
            remediation="provide a non-empty gamewise train split",
        )
        return {}, [finding], {"status": "unavailable"}
    reference = train_reference(train)
    scores, findings, metrics = {}, [], {}
    for split in ("validation", "test"):
        split_scores, components = {}, {}
        for decision in corpus.decisions_by_split[split]:
            score, detail = decision_ood_score(decision, reference)
            split_scores[decision.decision_id] = score
            components[decision.decision_id] = detail
        scores[split] = dict(sorted(split_scores.items()))
        ordered = sorted(split_scores.values())
        ood_ids = sorted(key for key, score in split_scores.items()
                         if score >= config.ood_threshold)
        metrics[split] = {
            "n": len(ordered),
            "ood_rate": len(ood_ids) / len(ordered) if ordered else 0.0,
            "quantiles": ({str(q): quantile(ordered, q) for q in (0.5, 0.9, 0.95, 1.0)}
                          if ordered else {}),
            "components": components,
        }
        if ood_ids:
            findings.append(make_finding(
                code="OOD_DECISIONS", severity=Severity.WARN, scope="ood",
                message="decision OOD score meets or exceeds the configured threshold",
                count=len(ood_ids), denominator=len(ordered), split=split, examples=ood_ids,
                evidence={"threshold": config.ood_threshold},
                remediation="inspect the highest component contributions before trusting metrics",
            ))
    return scores, findings, metrics


def audit_distribution(corpus, config, *, team_catalog=None, reference_paths=()):
    findings = audit_team_coverage(corpus, team_catalog)
    coverage = coverage_metrics(corpus, team_catalog)
    scores, ood_findings, ood_metrics = audit_ood(corpus, config)
    findings.extend(ood_findings)
    for split, values in coverage.items():
        if len(values["action_classes"]) < 2 and values["decisions"]:
            findings.append(make_finding(
                code="SINGLE_ACTION_CLASS", severity=Severity.WARN, scope="split",
                message="split contains fewer than two action classes", split=split,
                count=values["decisions"], remediation="expand the game panel",
            ))
        dimensions = {"ACTION": values["action_classes"]}
        if team_catalog:
            dimensions.update({"TEAM": values["teams"], "ARCHETYPE": values["archetypes"]})
        for dimension, buckets in dimensions.items():
            for bucket, games in sorted(buckets.items()):
                if games < config.small_bucket_games:
                    findings.append(make_finding(
                        code=f"SMALL_{dimension}_BUCKET", severity=Severity.WARN, scope="split",
                        message=f"{dimension.lower()} bucket is underpowered", split=split,
                        count=games, examples=[bucket],
                        evidence={"minimum_games": config.small_bucket_games},
                        remediation="add independent games for this bucket",
                    ))
    train_games = max(coverage["train"]["games"], 1)
    for split in ("validation", "test"):
        split_games = max(coverage[split]["games"], 1)
        dimensions = {"action_classes": coverage[split]["action_classes"]}
        if team_catalog:
            dimensions["archetypes"] = coverage[split]["archetypes"]
        for dimension, observed in dimensions.items():
            reference = coverage["train"][dimension]
            for bucket in sorted(set(reference) | set(observed)):
                delta = observed.get(bucket, 0) / split_games - reference.get(bucket, 0) / train_games
                if abs(delta) >= config.share_shift_warn:
                    findings.append(make_finding(
                        code="BUCKET_SHARE_SHIFT", severity=Severity.WARN, scope="split",
                        message="bucket share differs from train by at least the threshold",
                        split=split, examples=[f"{dimension}:{bucket}"],
                        evidence={"delta": delta, "threshold": config.share_shift_warn},
                        remediation="inspect whether the split represents the intended population",
                    ))
    reference_metrics = {}
    for path in sorted(map(Path, reference_paths), key=str):
        external, external_findings = load_and_audit_integrity(path, config)
        findings.extend(external_findings)
        external_scores = []
        reference = train_reference(corpus.decisions_by_split["train"])
        for decision in external.decisions:
            score, _detail = decision_ood_score(decision, reference)
            external_scores.append(score)
        reference_metrics[path.name] = {
            "n": len(external_scores),
            "ood_rate": (sum(score >= config.ood_threshold for score in external_scores)
                         / len(external_scores) if external_scores else 0.0),
        }
    return findings, {"coverage": coverage, "ood": ood_metrics,
                      "references": reference_metrics}, scores
