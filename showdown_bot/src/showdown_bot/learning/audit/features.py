"""Feature health, correlation and split-drift auditing (Phase 3,
dataset-reranker-audit slice, Task 5). Checks per-feature type/uniqueness/
sentinel-domination on the train split, flags highly correlated numeric
feature pairs, and measures train-vs-validation/test drift (PSI for numeric
features, Jensen-Shannon + unseen-category rate for categorical features).
Offline/pure: no network, no live battle imports.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditCorpus, Finding, Severity, canonical_json, make_finding, quantile,
)
from showdown_bot.learning.reranker_features import LABEL_DENYLIST, METADATA_DENYLIST
from showdown_bot.learning.schema import FEATURE_COLUMNS

SENTINEL_STRINGS = frozenset({"__none__", "__untracked__", "__unk__"})


def is_sentinel(value) -> bool:
    return value is None or (isinstance(value, str) and value in SENTINEL_STRINGS)


def feature_rows(decisions):
    return [row["features"] for decision in decisions for row in decision.rows]


def feature_stats(rows: list[dict], feature: str) -> dict:
    values = [row.get(feature) for row in rows]
    counts = Counter(canonical_json(value) for value in values)
    dominant = max(counts.values()) / len(values) if values else 0.0
    sentinel = sum(is_sentinel(value) for value in values)
    numeric = [float(value) for value in values
               if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return {
        "n": len(values), "unique": len(counts), "dominant_rate": dominant,
        "sentinel_rate": sentinel / len(values) if values else 0.0,
        "numeric": bool(numeric) and len(numeric) == len(values),
        "min": min(numeric) if numeric else None, "max": max(numeric) if numeric else None,
    }


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + end - 1) / 2.0
        for position in range(start, end):
            ranks[order[position]] = rank
        start = end
    return ranks


def spearman(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        raise ValueError("spearman requires equal-length inputs")
    a, b = average_ranks(left), average_ranks(right)
    am, bm = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - am) * (y - bm) for x, y in zip(a, b))
    denom = math.sqrt(sum((x - am) ** 2 for x in a) * sum((y - bm) ** 2 for y in b))
    return 0.0 if denom == 0 else numerator / denom


def train_quantile_edges(values: list[float], n_bins: int = 10) -> list[float]:
    ordered = sorted(values)
    return sorted(set(quantile(ordered, i / n_bins) for i in range(1, n_bins)))


def histogram(values: list[float], edges: list[float]) -> list[int]:
    counts = [0] * (len(edges) + 1)
    for value in values:
        index = 0
        while index < len(edges) and value > edges[index]:
            index += 1
        counts[index] += 1
    return counts


def psi(reference: list[float], observed: list[float], *, epsilon=1e-6) -> float:
    edges = train_quantile_edges(reference)
    ref = histogram(reference, edges)
    obs = histogram(observed, edges)
    total_ref, total_obs = sum(ref), sum(obs)
    return sum(
        ((r / total_ref + epsilon) - (o / total_obs + epsilon))
        * math.log((r / total_ref + epsilon) / (o / total_obs + epsilon))
        for r, o in zip(ref, obs)
    )


def jensen_shannon(reference, observed, *, epsilon=1e-6) -> float:
    keys = sorted(set(reference) | set(observed), key=str)
    rc, oc = Counter(reference), Counter(observed)
    rp = [(rc[key] + epsilon) / (len(reference) + epsilon * len(keys)) for key in keys]
    op = [(oc[key] + epsilon) / (len(observed) + epsilon * len(keys)) for key in keys]
    mid = [(a + b) / 2 for a, b in zip(rp, op)]
    kl = lambda p, q: sum(a * math.log(a / b, 2) for a, b in zip(p, q))
    return 0.5 * kl(rp, mid) + 0.5 * kl(op, mid)


def feature_warn(code, feature, *, count=1, denominator=None, split=None, evidence=None):
    return make_finding(
        code=code, severity=Severity.WARN, scope="feature", message=code,
        count=count, denominator=denominator, split=split, feature=feature,
        evidence=evidence or {}, remediation="inspect the feature extractor and split distribution",
    )


def audit_features(corpus: AuditCorpus, config: AuditConfig) -> tuple[list[Finding], dict]:
    train_rows = feature_rows(corpus.decisions_by_split["train"])
    features = sorted({name for row in corpus.rows for name in row["features"]})
    findings, metrics = [], {"train": {}, "correlations": [], "drift": {}}
    # format_id is intentionally in BOTH FEATURE_COLUMNS and METADATA_KEYS (schema: the only
    # allowed feature/metadata overlap); a canonical feature column is never a denylist leak.
    effective_denylist = (LABEL_DENYLIST | METADATA_DENYLIST) - set(FEATURE_COLUMNS)
    denied = sorted(set(features) & effective_denylist)
    if denied or not set(features) <= set(FEATURE_COLUMNS):
        findings.append(make_finding(
            code="FEATURE_ALLOWLIST_VIOLATION", severity=Severity.FAIL, scope="feature",
            message="feature payload violates the canonical allowlist", count=len(denied),
            examples=denied, remediation="remove denied or unknown columns before training",
        ))
    numeric_train = {}
    categorical_train = {}
    for feature in features:
        stats = feature_stats(train_rows, feature)
        metrics["train"][feature] = stats
        values = [row.get(feature) for row in train_rows]
        kinds = {"numeric" if isinstance(v, (int, float)) and not isinstance(v, bool)
                 else "categorical" for v in values if not is_sentinel(v)}
        if len(kinds) > 1:
            findings.append(make_finding(
                code="FEATURE_TYPE_MISMATCH", severity=Severity.FAIL, scope="feature",
                message="feature mixes numeric and categorical values", count=len(values),
                feature=feature, remediation="emit one stable type for this feature",
            ))
            continue
        nonfinite = sum(isinstance(v, (int, float)) and not isinstance(v, bool)
                        and not math.isfinite(float(v)) for v in values)
        if nonfinite:
            findings.append(make_finding(
                code="NONFINITE_FEATURE", severity=Severity.FAIL, scope="feature",
                message="feature contains NaN or infinity", count=nonfinite,
                denominator=len(values), feature=feature,
                remediation="fix or reject non-finite extractor output",
            ))
            continue
        if stats["unique"] == 1:
            findings.append(feature_warn("CONSTANT_FEATURE", feature, count=len(values),
                                         denominator=len(values)))
        elif stats["dominant_rate"] >= config.near_constant_rate:
            dominant_count = max(Counter(canonical_json(v) for v in values).values())
            findings.append(feature_warn("NEAR_CONSTANT_FEATURE", feature,
                                         count=dominant_count, denominator=len(values)))
        if stats["sentinel_rate"] >= config.sentinel_warn_rate:
            findings.append(feature_warn("SENTINEL_DOMINATED_FEATURE", feature,
                                         count=sum(is_sentinel(v) for v in values),
                                         denominator=len(values)))
        if kinds == {"numeric"}:
            numeric_train[feature] = [float(v) for v in values
                                      if not is_sentinel(v) and math.isfinite(float(v))]
        else:
            categorical_train[feature] = [canonical_json(v) for v in values]
    for left, right in combinations(sorted(numeric_train), 2):
        pairs = [(float(row[left]), float(row[right])) for row in train_rows
                 if left in row and right in row
                 and not is_sentinel(row[left]) and not is_sentinel(row[right])]
        if len(pairs) < 2:
            continue
        rho = spearman([pair[0] for pair in pairs], [pair[1] for pair in pairs])
        if abs(rho) >= config.spearman_warn_abs:
            findings.append(feature_warn(
                "HIGH_SPEARMAN_CORRELATION", left,
                evidence={"other_feature": right, "rho": rho,
                          "threshold": config.spearman_warn_abs}))
            metrics["correlations"].append({"left": left, "right": right, "rho": rho})
    for split in ("validation", "test"):
        observed_rows = feature_rows(corpus.decisions_by_split[split])
        split_metrics = {}
        metrics["drift"][split] = split_metrics
        if not observed_rows:
            continue
        for feature, reference in sorted(numeric_train.items()):
            observed = [float(row.get(feature)) for row in observed_rows
                        if isinstance(row.get(feature), (int, float))
                        and not isinstance(row.get(feature), bool)
                        and math.isfinite(float(row.get(feature)))]
            if not observed:
                continue
            value_psi = psi(reference, observed, epsilon=config.near_epsilon)
            out_count = sum(v < min(reference) or v > max(reference) for v in observed)
            split_metrics[feature] = {"psi": value_psi,
                                      "out_of_range_rate": out_count / len(observed)}
            if value_psi >= config.psi_warn:
                findings.append(feature_warn("PSI_DRIFT", feature, split=split,
                                             evidence={"psi": value_psi}))
            if out_count / len(observed) > config.out_of_range_warn_rate:
                findings.append(feature_warn("OUT_OF_RANGE_FEATURE", feature, split=split,
                                             count=out_count, denominator=len(observed)))
        for feature, reference in sorted(categorical_train.items()):
            observed = [canonical_json(row.get(feature)) for row in observed_rows]
            value_js = jensen_shannon(reference, observed, epsilon=config.near_epsilon)
            known = set(reference)
            unseen = sum(value not in known for value in observed)
            split_metrics[feature] = {"js": value_js, "unseen_rate": unseen / len(observed)}
            if value_js >= config.js_warn:
                findings.append(feature_warn("JS_DRIFT", feature, split=split,
                                             evidence={"js": value_js}))
            if unseen / len(observed) > config.unseen_warn_rate:
                findings.append(feature_warn("UNSEEN_CATEGORY", feature, split=split,
                                             count=unseen, denominator=len(observed)))
    return findings, metrics
