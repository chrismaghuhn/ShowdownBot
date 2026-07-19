# Documentation

Start with [ROADMAP](ROADMAP.md) for priorities and
[PROJECT_INDEX](PROJECT_INDEX.md) for the complete project status.

## Projects

| Project | Scope |
|---|---|
| [Champions](projects/champions/) | Champions format, panel, Mega, and latency work |
| [Accuracy](projects/accuracy/) | Hit probability and accuracy gates |
| [Evaluation](projects/evaluation/) | Harnesses, schedules, reports, heldout gates, and provenance |
| [Learning](projects/learning/) | Reranker, datagen, sampling, teacher, and calibration work |
| [Core bot](projects/core-bot/) | Client, engine, heuristic, opponent knowledge, speed, and calc |
| [Operations](projects/operations/) | Repository and agent-operation documentation |

Cross-project architecture lives in [architecture](architecture/). User-facing
material lives in [guides](guides/). Historical old paths are resolved through
[PATH_MIGRATION](PATH_MIGRATION.md).

Within a project, use `specs/`, `plans/`, `audits/`, and `reviews/` only when that
kind exists. Do not recreate `docs/superpowers/`.
