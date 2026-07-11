"""VGC-Bench external-replay ingestion (2b-5a Part A).

Snapshots + parses + format-gates human replay logs from the external
VGC-Bench dataset (`cameronangliss/vgc-battle-logs-sv`, MIT) for offline
research / dataset-prototype purposes only.

**Isolation invariant (INV-1): this package is external-replay ingestion and
MUST NOT be imported by the live decision path (`battle.decision`), the
teacher, or the reranker (`learning.*`, `client.gauntlet`).** It re-derives
winner/turns from the raw log itself (via `eval.battle_parse`) and never
trusts external fields. See `research/vgc_bench_ingest/README.md` for the
full invariant and current scope (Part A: snapshot/parse/gate only —
perspective reconstruction, legality, and leakage audit are Part B; real
data + downstream uses are Part C).
"""
