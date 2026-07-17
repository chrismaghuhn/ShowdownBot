"""The I8 microprofile's arm matrix (I8-C, C2): design §4, declared once.

Pure declaration, in a module rather than inside a driver script, following the convention
``scripts/run_cap_latency_sweep.py`` states for itself: pure logic lives in a module,
"unit-tested there, imported here … rather than as a private helper in this driver script".

Completeness, not coverage theatre
----------------------------------
§4 audits fifteen arm rows and finds six unconstructible today. An arm that is simply
absent from a matrix reads as "covered" to anyone counting it, so every §4 arm here is
either RUNNABLE (``PROFILE_ARMS``) or BLOCKED with its blocker named (``BLOCKED_ARMS``),
and the partition is asserted by test. The design's §5 forbids the alternative outright:
"None is silently skipped -- the design's §5 forbids a bounded coverage claim that reads as
complete."

Which knobs land where, and why it is not arbitrary
--------------------------------------------------
An arm's ``behavior_env`` is ``config_env.behavior_env()`` of its declared env -- derived by
the shared function, never hand-filtered, because a second classification of the same vars
would be free to disagree with the one ``config_hash`` actually uses, and the arm's
``effective_config_hash`` is computed FROM that mapping.

  * ``SHOWDOWN_OPP_MEGA_CLICK_RATE`` and ``SHOWDOWN_SEARCH_DEPTH`` are BEHAVIOR_AFFECTING,
    so arms varying them have DIFFERENT effective config hashes -- which is the whole reason
    §2.7 puts the hash per arm rather than at the manifest's top level.
  * ``SHOWDOWN_SEARCH_TOPM``/``TOPN`` are EXCLUDED_BY_REASON and ``SHOWDOWN_CALC_BACKEND``
    is NON_BEHAVIORAL, so neither moves ``config_hash``. That is exactly what makes the
    backend arms comparable -- and exactly why they are recorded in ``arm_params``, so the
    difference between two arms is never invisible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from showdown_bot.eval.profile_manifest import ArmSpec

# Design §4's row ids, in the design's own order. The manifest's `arms` is a LIST, so this
# order is part of the artifact and of its hash: anchoring it to §4 keeps the manifest
# diffable against the design by eye and keeps the hash from moving when a literal is
# re-sorted.
_DESIGN_ARM_ORDER: tuple[str, ...] = (
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13a", "13b", "14",
)


def design_arm_ids() -> tuple[str, ...]:
    """Every arm row design §4 audits -- runnable or not."""
    return _DESIGN_ARM_ORDER


# Arms §4 audits as NOT constructible today, each with the plan input that blocks it (§4.1).
# Recorded rather than omitted: a bounded coverage claim that reads as complete is the
# defect the design forbids. Unblocking these is C3's work, not C2's.
_BLOCKED_ARMS: dict[str, str] = {
    "5": "P-1 -- no fixture places a Mega-capable mon in p2.b; _mega_state() takes only "
         "foe_a and never populates p2.b. Production supports it; only predict_responses-"
         "level coverage exists, via a hand-built eligibility dict that bypasses "
         "foe_mega_eligibility().",
    "7": "P-2 -- no board where our side lacks a Mega option: every mega request fixture "
         "hard-codes canMegaEvo: True. The branch is reachable inside the tie fixture's "
         "own_mega_slot=None context; the BOARD is not.",
    "8": "P-3 -- no decision-level board with dual-Mega at UNEQUAL pre-Mega speed. The only "
         "board with both a real foe hypothesis and a projectable own Mega is the tie "
         "fixture (200/200). This is the configuration the one live active decision "
         "actually used, so its absence at decision level is a real gap.",
    "10": "P-4 -- no Trick-Room board at decision level. mega_activation_order_key exists "
          "and is tested against a hand-built state, but a post-hoc kw['state'] swap is "
          "forbidden because contexts are pre-bound.",
    "13b": "P-5 -- persistent COLD cannot be cleanly isolated in a fixture-based "
           "microprofile: fixtures' SpeedOracle does not share the calc backend while "
           "production does, and sharing it makes context construction spawn the backend "
           "BEFORE score_evaluated_variants is entered. Needs P-5 and the "
           "timer_scope=contexts_and_score decision taken together.",
    "14": "P-5 -- persistent WARM is SPLIT in fixtures for the same reason: the fixtures' "
          "two backends make 'warm' mean something different than it does in production, "
          "where one backend is shared across damage and speed.",
}

# Read-only. This records which arms the design audited as unconstructible; a caller able
# to add or drop an entry could make an arm "covered" or "excused" at runtime without
# anyone amending the design.
BLOCKED_ARMS = MappingProxyType(_BLOCKED_ARMS)


@dataclass(frozen=True)
class ArmDecl:
    """One arm of the matrix, immutable all the way down.

    ``frozen=True`` alone was not enough, and the gap was not theoretical: it blocks
    rebinding a field but not mutating the dict a field points AT -- and the lifecycle
    dicts were SHARED, every cold arm pointing at one ``_COLD`` literal. So
    ``arm.lifecycle["damage_oracle"] = ...`` silently rewrote the lifecycle of every other
    cold arm at once, and each one's manifest entry with it. Each mapping is therefore
    wrapped read-only here, which also breaks the aliasing: the proxy is per-arm even when
    it wraps a shared literal.

    ``reps`` is deliberately absent -- it is a run parameter (see ``arm_specs``).
    """

    arm_id: str
    design_arm: str
    fixture: str
    env: dict = field(default_factory=dict)
    scoring_params: dict = field(default_factory=dict)
    lifecycle: dict = field(default_factory=dict)
    warmup: int = 0
    note: str = ""

    def __post_init__(self) -> None:
        for name in ("env", "scoring_params", "lifecycle"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


# Cold-cache lifecycle: everything per_rep. §2.8's first coherent configuration -- the full
# cost of a decision that resolves nothing from cache. warmup MUST be 0: a cold-cache arm
# that "warms up" is a contradiction, since its caches are discarded anyway.
_COLD = {
    "calc_backend": "per_rep",
    "damage_oracle": "per_rep",
    "speed_oracle": "per_rep",
    "species_dex": "per_rep",
    "contexts_and_variants": "per_rep",
}

# The two fixtures §4 actually names at decision level.
_F_NO_FOE = "mega_decision_fixture"       # p2.a Incineroar -> eligibility {}
_F_TIE = "mega_decision_tie_fixture"      # own == foe == 200, real backend

PROFILE_ARMS: tuple[ArmDecl, ...] = (
    ArmDecl(
        arm_id="A01_no_foe_mega",
        design_arm="1",
        fixture=_F_NO_FOE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Champions, no foe-Mega hypothesis: eligibility {} -> the pre-I7b path.",
    ),
    ArmDecl(
        arm_id="A02_click_rate_zero",
        design_arm="2",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.0"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Inertness control. Twins are emitted at weight 0, but the weight > 0 filter "
             "composes ZERO branches, so this arm's cost is the no-mega path BY "
             "CONSTRUCTION -- which is what makes it the control rather than a measurement.",
    ),
    ArmDecl(
        arm_id="A03_click_rate_default",
        design_arm="3",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="The default rate: the configuration a real run actually uses.",
    ),
    ArmDecl(
        arm_id="A04_foe_mega_slot0",
        design_arm="4",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Foe-Mega on opponent slot 0 -- the only slot a fixture can place today (P-1 "
             "blocks slot 1, arm 5).",
    ),
    ArmDecl(
        arm_id="A06_own_mega_no_foe_mega",
        design_arm="6",
        fixture=_F_NO_FOE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Own-Mega projected, no foe hypothesis: isolates the I7a cost from I7b's.",
    ),
    ArmDecl(
        arm_id="A09_dual_mega_tie",
        design_arm="9",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Dual-Mega at an exact speed tie -> TWO branches @ 0.5. The expensive half of "
             "the foe-Mega path, and the fixture pins the tie at 200/200 against a real "
             "backend rather than assuming it.",
    ),
    ArmDecl(
        arm_id="A11_depth1",
        design_arm="11",
        fixture=_F_TIE,
        env={
            "SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35",
            "SHOWDOWN_SEARCH_DEPTH": "1",
            # TOPM=4 matches A12, so the A11<->A12 contrast moves EXACTLY ONE knob: depth.
            # A12 needs TOPM>=4 to reach the frontier at all, so leaving A11 at the default
            # 2 made the pair a two-variable contrast for no reason. §2.7 records that
            # TOPM cannot affect output at depth 1 -- it is EXCLUDED_BY_REASON precisely
            # because of that -- so this changes nothing A11 measures.
            "SHOWDOWN_SEARCH_TOPM": "4",
        },
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Depth-1. The explicit CONTROL for A12 and nothing else: behaviourally "
             "identical to A03, and not to be read as an independent contrast against it.",
    ),
    ArmDecl(
        arm_id="A12_depth2_frontier_reached",
        design_arm="12",
        fixture=_F_TIE,
        env={
            "SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35",
            "SHOWDOWN_SEARCH_DEPTH": "2",
            # TOPM >= 4 is REQUIRED, not a preference. §4's measured fact: at the default
            # TOPM=2 and rate 0.35 the top-M frontier is all-no-mega, so the foe-Mega
            # depth-2 path is NEVER reached. An arm 12 at TOPM=2 would measure depth-1
            # wearing a depth-2 label.
            "SHOWDOWN_SEARCH_TOPM": "4",
        },
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Depth-2 with the foe-Mega frontier ACTUALLY reached -- see TOPM above.",
    ),
    ArmDecl(
        arm_id="A13a_oneshot",
        design_arm="13a",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35", "SHOWDOWN_CALC_BACKEND": "oneshot"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="oneshot: a fresh Node process per batch. NON_BEHAVIORAL, so it shares arm 3's "
             "effective_config_hash -- which is what makes the two comparable at all. Its "
             "persistent counterparts (13b cold, 14 warm) are blocked by P-5.",
    ),
)


def arm_specs(fixture_hashes: dict[str, str], *, reps: int) -> list[ArmSpec]:
    """The matrix, resolved into ``ArmSpec``s -- the ONE road to the manifest producer.

    ``fixture_hashes`` maps a fixture name to its ``fixture_input_hash``, computed by the
    caller with the shared ``decision_profile.fixture_input_hash`` over the fixture's real
    inputs. A missing entry raises: an arm whose fixture hash were ``None`` would sail
    through the producer as "a hash" while binding nothing -- precisely the failure §2.7's
    hash exists to prevent.

    ``reps`` is REQUIRED, uniform, and has no default. An earlier cut carried ``reps=30``
    per arm: a number neither the spec nor the plan states, invented here and then readable
    back as though the design had asked for it. It is a RUN parameter -- whoever authorizes
    the run fixes it in advance and the manifest records the choice. Uniform, because a
    per-arm rep count would be an unlogged lever on which arm looks cheap.
    """
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ValueError(f"reps must be a positive int, got {reps!r}")
    from showdown_bot.eval.config_env import behavior_env

    specs: list[ArmSpec] = []
    for decl in PROFILE_ARMS:
        # KeyError by design: fail closed on an unresolved fixture.
        fixture_hash = fixture_hashes[decl.fixture]
        specs.append(
            ArmSpec(
                arm_id=decl.arm_id,
                # DERIVED by the shared classifier, never hand-filtered here: the arm's
                # effective_config_hash is computed from this mapping, and a second
                # classification would be free to disagree with the one config_hash uses.
                behavior_env=behavior_env(decl.env),
                # The knobs that define the arm but do NOT move config_hash
                # (NON_BEHAVIORAL / EXCLUDED_BY_REASON). Recorded so the difference
                # between two arms is never invisible.
                arm_params={
                    k: v for k, v in decl.env.items() if k not in behavior_env(decl.env)
                },
                scoring_params=dict(decl.scoring_params),
                fixture_input_hash=fixture_hash,
                reps=reps,
                warmup=decl.warmup,
                lifecycle=dict(decl.lifecycle),
            )
        )
    return specs
