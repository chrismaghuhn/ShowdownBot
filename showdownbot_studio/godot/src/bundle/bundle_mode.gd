class_name BundleMode
extends RefCounted

const REPLAY_TRACE := "REPLAY_TRACE"
const REPLAY_ONLY := "REPLAY_ONLY"
const TRACE_ONLY := "TRACE_ONLY"

const SCHEMA_MAJOR_SUPPORTED := 1

const TRACE_VERSION_V2 := "decision-trace-v2"
const TRACE_VERSION_V3 := "decision-trace-v3"

const PHASE_TEAM_PREVIEW := "team_preview"
const PHASE_FORCED_REPLACEMENT := "forced_replacement"
const PHASE_REGULAR_TURN := "regular_turn"

const FILE_BATTLE_LOG := "battle_log"
const FILE_DECISION_TRACE := "decision_trace"
const FILE_WARNINGS := "warnings"
const FILE_CONFIG_MANIFEST := "config_manifest"

const PATH_BATTLE_LOG := "battle.jsonl"
const PATH_DECISION_TRACE := "decisions.jsonl"
const PATH_WARNINGS := "warnings.json"
const PATH_CONFIG_MANIFEST := "config-manifest.json"

const FILE_KEYS: PackedStringArray = [
	FILE_BATTLE_LOG,
	FILE_DECISION_TRACE,
	FILE_WARNINGS,
	FILE_CONFIG_MANIFEST,
]
