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


# Arms §4 audited as NOT constructible at C2 time, each with the plan input that blocked it
# (§4.1). C3 unblocked all six by building I8-specific coherent boards and a production-
# topology session (one backend shared across damage/speed/dex), so this map is now empty.
# It is kept -- rather than deleted -- as the structural home for any FUTURE arm the design
# audits as unconstructible: §5 forbids a bounded coverage claim that reads as complete, and
# an absent-from-the-matrix arm reads as "covered". An entry here is the honest alternative.
#
# How each was unblocked (proven arm-by-arm in tests/i8/test_profile_arms_end_to_end.py):
#   5   (P-1) real Mega holder in p2.b, resolved by the REAL foe_mega_eligibility().
#   7   (P-2) a board coherent on BOTH signals -- no own stone AND canMegaEvo False.
#   8   (P-3) decision-level dual-Mega at unequal speed (own 200 vs foe 145).
#   10  (P-4) Trick Room set on the FINAL state before contexts are built.
#   13b (P-5) one shared backend (production topology) + timer_scope=contexts_and_score,
#             so the scope contains the spawn context construction does.
#   14  (P-5) same shared backend, per_arm + warmup, measured at the same wide scope.
_BLOCKED_ARMS: dict[str, str] = {}

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
    # The microprofile timer scope this arm is measured at (§2.5). Default is the narrow
    # score_evaluated_variants; the persistent backend arms (13b cold, 14 warm) override it to
    # contexts_and_score, because on a shared backend the spawn happens during context
    # construction, so only a scope that CONTAINS context construction can measure it (§2.8,
    # §4 arm 13b). It is a harness run parameter, not part of the manifest arm identity: two
    # arms measured at different scopes are already distinguished by arm_params where they
    # differ (13a oneshot vs 13b/14 persistent), and every row carries its own timer_scope.
    timer_scope: str = "score_evaluated_variants"
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

# Warm-cache lifecycle: the backend and the three semantic caches are per_arm (carry across
# reps), while contexts_and_variants stay per_rep (rebuilt each rep). §2.8's second coherent
# configuration -- the marginal cost of a decision whose calc results are already known. Only
# arm 14 uses it, paired with warmup=1 so the first timed rep already starts warm.
_WARM = {
    "calc_backend": "per_arm",
    "damage_oracle": "per_arm",
    "speed_oracle": "per_arm",
    "species_dex": "per_arm",
    "contexts_and_variants": "per_rep",
}

# The decision-level boards §4 names. The first two existed at C2; the four I8-specific
# boards (C3) unblock arms 5/7/8/10 and live in tests/i8/profile_boards.py -- production code
# cannot reach a test fixture, so these are names the test-side registry resolves to sessions.
_F_NO_FOE = "mega_decision_fixture"                       # p2.a Incineroar -> eligibility {}
_F_TIE = "mega_decision_tie_fixture"                      # own == foe == 200, real backend
_F_FOE_SLOTB = "mega_decision_foe_slotb_fixture"          # A05: Mega holder in p2.b (P-1)
_F_NO_OWN_MEGA = "mega_decision_no_own_mega_fixture"      # A07: our side has no Mega (P-2)
_F_DUAL_UNEQUAL = "mega_decision_dual_unequal_fixture"    # A08: own 200 vs foe 145 (P-3)
_F_DUAL_UNEQUAL_TR = "mega_decision_dual_unequal_tr_fixture"  # A10: + Trick Room (P-4)

_DECLARED_ARMS: tuple[ArmDecl, ...] = (
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
             "persistent counterparts are 13b (cold) and 14 (warm) below.",
    ),
    # ---- C3: the six arms §4 audited as unconstructible at C2, now built ----
    ArmDecl(
        arm_id="A05_foe_mega_slot1",
        design_arm="5",
        fixture=_F_FOE_SLOTB,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Foe-Mega on opponent slot 1 (p2.b) -- the P-1 gap. A real Mega holder placed in "
             "p2.b and resolved by the REAL foe_mega_eligibility(), never a hand-built dict.",
    ),
    ArmDecl(
        arm_id="A07_foe_mega_no_own_mega",
        design_arm="7",
        fixture=_F_NO_OWN_MEGA,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Foe-Mega with NO own-Mega option (P-2). The board is coherent on BOTH signals: "
             "p1.a holds no stone AND the request's canMegaEvo is False, so contexts=[None] "
             "and the foe-Mega branch composes against the no-own-mega context. Setting only "
             "one signal would be the incoherent board the design forbids.",
    ),
    ArmDecl(
        arm_id="A08_dual_mega_unequal",
        design_arm="8",
        fixture=_F_DUAL_UNEQUAL,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Dual-Mega at UNEQUAL pre-Mega speed (P-3): own Aerodactyl 200 vs foe Meganium "
             "145 -> one full-weight branch. This is the decision-level configuration the one "
             "live active decision actually used. Only the INEQUALITY is load-bearing; 200/145 "
             "is the real book-driven speed, not the projection fixture's opp_sets-driven 100.",
    ),
    ArmDecl(
        arm_id="A10_trick_room_activation_order",
        design_arm="10",
        fixture=_F_DUAL_UNEQUAL_TR,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        note="Trick Room reverses Mega-activation order (P-4): the dual-unequal board with "
             "field.trick_room set on the FINAL state BEFORE contexts are built -- never a "
             "post-hoc kw['state'] swap, which the pre-bound contexts forbid.",
    ),
    ArmDecl(
        arm_id="A13b_persistent_cold",
        design_arm="13b",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35", "SHOWDOWN_CALC_BACKEND": "persistent"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        timer_scope="contexts_and_score",
        note="Persistent backend, first request incl. the spawn (P-5). MEASURED AT "
             "contexts_and_score, not the narrow scope: on a shared backend (production "
             "topology) the spawn happens during context construction, so only a scope that "
             "CONTAINS context construction can measure it (§2.5/§2.8, §4 arm 13b). per_rep "
             "everything, warmup=0 -- every rep is a genuine cold start.",
    ),
    ArmDecl(
        arm_id="A14_persistent_warm",
        design_arm="14",
        fixture=_F_TIE,
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35", "SHOWDOWN_CALC_BACKEND": "persistent"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_WARM,
        warmup=1,
        timer_scope="contexts_and_score",
        note="Persistent backend, steady state (P-5). Backend and the three caches per_arm so "
             "they carry across reps; contexts_and_variants per_rep (rebuilt each rep); "
             "warmup=1 so the first timed rep starts warm -- one identical untimed repetition "
             "populating the same fixed fixture keys. contexts_and_score scope, matching 13b "
             "so cold and warm are compared at the SAME boundary.",
    ),
)

# Ordered by §4's design arm order, NOT by definition order above. The manifest's `arms` is a
# LIST whose order is part of its hash, so the canonical order is enforced here -- keyed off
# the single source design_arm_ids() -- rather than trusted to the literal, which a future
# edit could reorder (C3 appended six arms out of order, and this is what keeps that from
# moving the hash).
PROFILE_ARMS: tuple[ArmDecl, ...] = tuple(
    sorted(_DECLARED_ARMS, key=lambda a: _DESIGN_ARM_ORDER.index(a.design_arm))
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
                timer_scope=decl.timer_scope,
            )
        )
    return specs
