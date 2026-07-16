"""I7b-B Task 4 (Rev. 6): three-phase foe-Mega scoring integration."""
from __future__ import annotations

import pytest

from showdown_bot.battle.candidate_identity import joint_action_key_v2
from showdown_bot.battle.mega_scoring import MegaScoreRecord, score_evaluated_variants

# [REV.5] `mega_form_for` is deliberately NOT imported here any more: every test in
# this file now derives its hypothesis through the real foe_mega_eligibility() via
# _real_eligibility(), so a hand-built MegaForm has no remaining call site (it would
# be an unused import, and re-introducing one would reopen the incoherent-hypothesis
# defect Rev. 5 closes).


def _real_eligibility(kw):
    """[REV.5] Derive eligibility through the REAL limited-view path, never by
    hand-injecting a MegaForm. Rev. 4 injected an Aerodactyl-Mega form onto an
    Incineroar -- a hypothesis foe_mega_eligibility() can never produce (it resolves
    species-bound via mega_form_for(mon.species, mon.item)) and which Task 2's Rev. 5
    coherence check now rejects outright."""
    from showdown_bot.battle.opponent import foe_mega_eligibility

    elig = foe_mega_eligibility(kw["state"], "p2", opp_sets=kw.get("opp_sets"))
    assert elig, "fixture must yield a real foe-Mega hypothesis for this test to mean anything"
    return elig


def _pre_mega_speeds(kw):
    st, so = kw["state"], kw["speed_oracle"]
    own_mon, foe_mon = st.sides["p1"]["a"], st.sides["p2"]["a"]
    own = so.speed_for_species(
        species_name=own_mon.species, base_species_id=own_mon.base_species_id or own_mon.species,
        side="p1", mon=own_mon, field=st.field, our_spreads=kw["our_spreads"],
        opp_sets=None, book=kw["book"], is_ours=True,
    )
    foe = so.speed_for_species(
        species_name=foe_mon.species, base_species_id=foe_mon.base_species_id or foe_mon.species,
        side="p2", mon=foe_mon, field=st.field, our_spreads=None,
        opp_sets=kw.get("opp_sets"), book=kw["book"], is_ours=False,
    )
    return own, foe


def _assert_pre_mega_speeds_tie(kw):
    """[REV.5] Explicit real-backend precondition for every test that asserts two
    0.5-weight branches. Rev. 4's defect was asserting a tie nobody ever computed
    (Aerodactyl 200 vs Incineroar 123); this makes the tie a checked fact, and makes
    a fixture/backend drift fail HERE with a readable message instead of surfacing as
    a confusing `assert tied_groups` failure downstream. The absolute value is pinned
    too, not just the equality, so a drift that moves BOTH sides is caught as well."""
    own, foe = _pre_mega_speeds(kw)
    assert own == foe == 200, f"tie fixture must tie at 200: p1.a={own} p2.a={foe}"


def _score(kw, req, *, eligibility=None, sink=None, mode=None):
    from showdown_bot.engine.species_meta import species_meta_table

    return score_evaluated_variants(
        kw["evaluated_variants"], kw["contexts"], req=req, state=kw["state"], book=kw["book"],
        our_side="p1", opp_side="p2", calc=kw["calc"], oracle=kw["oracle"],
        speed_oracle=kw["speed_oracle"], dex=kw["dex"], priors=None, weights=kw["weights"],
        mode=mode or kw["mode"], risk_lambda=0.5, rollout_horizon=0, our_spreads=kw.get("our_spreads"),
        opp_sets=None, calc_profile=kw["calc_profile"], accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False,
        foe_mega_eligibility=eligibility, species_meta=species_meta_table() if eligibility else None,
        opp_mega_evidence_sink=sink,
    )


def test_must_react_min_is_weight_blind_which_is_why_zero_weight_samples_are_excluded():
    """[P1 rationale, pinned] The reason the two counterexamples below exist.

    aggregate_scores' MUST_REACT operator is `avg - lambda*(avg - min(scores))`,
    and that `min(scores)` is computed WITHOUT weights (policy.py). So a
    zero-weight sample cannot move the weighted mean, but DOES move the aggregate:

        [10]        w=[1]    -> 10.0
        [10, -100]  w=[1, 0] -> -56.0     (lambda 0.6: 10 - 0.6*(10 - -100))

    A zero-weight response is therefore NOT harmless, and must never reach
    score_vector/score_weights. NEUTRAL/AHEAD are unaffected (both weight their
    mean and variance), so this is MUST_REACT-specific. If policy.py ever starts
    weighting the min, this test fails and the exclusion rule can be revisited --
    that is exactly what it is here to tell you."""
    from showdown_bot.battle.policy import aggregate_scores
    from showdown_bot.engine.belief.game_mode import GameMode

    lone = aggregate_scores([10.0], GameMode.MUST_REACT, weights=[1.0])
    with_zero = aggregate_scores([10.0, -100.0], GameMode.MUST_REACT, weights=[1.0, 0.0])
    assert lone == pytest.approx(10.0)
    assert with_zero != pytest.approx(lone)  # <-- the whole point
    assert with_zero == pytest.approx(-56.0)
    # ...and the contrast: NEUTRAL genuinely ignores a zero-weight sample.
    assert aggregate_scores([10.0, -100.0], GameMode.NEUTRAL, weights=[1.0, 0.0], risk_lambda=0.5) \
        == pytest.approx(aggregate_scores([10.0], GameMode.NEUTRAL, weights=[1.0], risk_lambda=0.5))


def test_click_rate_zero_makes_the_foe_mega_hypothesis_completely_inert(
    mega_decision_tie_fixture, monkeypatch,
):
    """[P1 counterexample 1 of 2] At click rate 0.0 every foe-Mega twin carries
    weight 0, so the hypothesis must be COMPLETELY inert: no branch composed (no
    wasted calc), no evidence row, no score sample. I7b-A still emits the twin for
    identity/cap coverage -- that is upstream of this path and unchanged.

    RED before the fix: zero-weight mega rows are scored, and score_weights
    contains 0.0 -- which under MUST_REACT's weight-blind min() silently moves the
    decision (see the rationale test above)."""
    from showdown_bot.engine.belief.game_mode import GameMode

    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0")
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence, mode=GameMode.MUST_REACT)

    assert not [e for e in evidence if e.foe_mega_slot is not None], (
        "click rate 0.0: zero-weight foe-Mega twins must not be enqueued, scored, or evidenced"
    )
    assert [e for e in evidence if e.foe_mega_slot is None], "the no-mega twins must still be scored"
    for r in records:
        assert r.score_weights
        assert all(w > 0 for w in r.score_weights), (
            f"zero-weight sample reached score_weights: {r.score_weights}"
        )


def test_click_rate_one_makes_the_no_mega_twin_completely_inert(
    mega_decision_tie_fixture, monkeypatch,
):
    """[P1 counterexample 2 of 2] Mirror image: at click rate 1.0 the no-mega twin
    carries weight 0 and must not be scored either -- same weight-blind-min reason.

    RED before the fix: zero-weight no-mega rows are scored, and score_weights
    contains 0.0."""
    from showdown_bot.engine.belief.game_mode import GameMode

    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "1")
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence, mode=GameMode.MUST_REACT)

    assert not [e for e in evidence if e.foe_mega_slot is None], (
        "click rate 1.0: zero-weight no-mega twins must not be enqueued, scored, or evidenced"
    )
    assert [e for e in evidence if e.foe_mega_slot is not None], "the mega twins must still be scored"
    for r in records:
        assert r.score_weights
        assert all(w > 0 for w in r.score_weights), (
            f"zero-weight sample reached score_weights: {r.score_weights}"
        )


def test_return_type_is_unchanged_records_only(mega_decision_fixture):
    """Finding 4e: the return type stays `list[MegaScoreRecord]` -- NOT a
    tuple -- so every existing real call site (`decision.py` and 7 in
    `tests/i7a/test_i7a_decision.py`, none of which unpack a tuple today)
    keeps working unmodified. Evidence is opt-in via `opp_mega_evidence_sink`."""
    req, kw = mega_decision_fixture
    records = _score(kw, req)
    assert isinstance(records, list)
    assert all(isinstance(r, MegaScoreRecord) for r in records)


def test_foe_mega_evidence_is_weighted_by_world_times_response_times_branch(mega_decision_tie_fixture):
    """T19/T26 weighting: sibling evidence rows for the SAME (candidate,
    response) tie must have equal, sub-1.0 branch_weight values summing to
    1.0 -- a regression that drops branch.weight from the branch-building or
    evaluation path would either collapse the tie to one branch (failing the
    `tied_groups` non-empty check) or leave both siblings at weight 1.0
    (failing the sum-to-1.0 check).

    [REV.5] Uses mega_decision_tie_fixture (real Aerodactyl foe, 200 vs 200), NOT
    the default Incineroar board (200 vs 123) whose single weight-1.0 branch made
    Rev. 4's `assert tied_groups` unsatisfiable. Real-backend integration test --
    Task 3's monkeypatched tie test covers branch ENUMERATION in isolation; this
    one must earn its tie from the real backend, so it never monkeypatches speed."""
    req, kw = mega_decision_tie_fixture
    _assert_pre_mega_speeds_tie(kw)  # REV.5: checked precondition, not an assumption
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)

    foe_evidence = [e for e in evidence if e.foe_mega_slot is not None]
    assert foe_evidence
    by_response: dict[tuple[str, str], list] = {}
    for e in foe_evidence:
        by_response.setdefault((e.candidate_key, e.response_id), []).append(e)
    tied_groups = [g for g in by_response.values() if len(g) > 1]
    assert tied_groups  # this fixture's speed values must exercise a genuine tie
    for group in tied_groups:
        branch_weights = {round(e.branch_weight, 9) for e in group}
        assert len(branch_weights) == 1
        assert next(iter(branch_weights)) < 1.0
        assert sum(e.branch_weight for e in group) == pytest.approx(1.0)


def test_no_mega_responses_also_produce_evidence_rows(mega_decision_tie_fixture):
    """Finding 4a: the future smoke's evidence gate requires BOTH a no-mega
    and a mega twin for the same decision -- Rev. 2 only ever appended
    inside the foe-mega branch loop."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    assert any(e.foe_mega_slot is None for e in evidence)
    assert any(e.foe_mega_slot is not None for e in evidence)


def test_evidence_candidate_key_matches_joint_action_key_v2(mega_decision_tie_fixture):
    """Finding 4d: `candidate_key` must come from the real module-level
    `joint_action_key_v2`, not a nonexistent `.joint_action_key()` method."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence)
    valid_keys = {joint_action_key_v2(r.variant.joint) for r in records}
    assert evidence
    assert all(e.candidate_key in valid_keys for e in evidence)


def test_evidence_carries_raw_unmultiplied_components(mega_decision_tie_fixture):
    """Finding 4b/4c: evidence exposes world_index/world_weight/response_weight
    as separate fields, and `raw_score` is the per-response detail score
    alone -- never pre-multiplied into a single "contribution", since
    aggregate_scores (policy.py) is non-linear (MUST_REACT/NEUTRAL) and no
    single per-response product is correct under both operators."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    assert evidence
    for e in evidence:
        assert isinstance(e.world_index, int)
        assert isinstance(e.world_weight, float)
        assert isinstance(e.response_weight, float)
        assert isinstance(e.raw_score, float)


def test_i7b_active_path_weights_no_mega_and_mega_responses_consistently(mega_decision_tie_fixture):
    """Finding 3: when foe_mega_eligibility is non-empty, EVERY response
    (no-mega included) must use its real r.weight -- not the legacy
    `1.0`-under-priors=None default, which would otherwise make no-mega and
    mega responses incomparable within the same decision."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    no_mega = [e for e in evidence if e.foe_mega_slot is None]
    assert no_mega
    assert any(e.response_weight != 1.0 for e in no_mega)


def test_branch_replan_preserves_original_mega_identity_and_weight(
    mega_decision_tie_fixture, monkeypatch,
):
    """A branch replan may replace actions, never the original Mega hypothesis's
    identity or its click-rate/cap/renormalised weight -- the branch-regenerated
    base response must supply ONLY actions.

    Pinned at an explicit mid click rate so the Mega twin is genuinely scored.
    (Rev. 4 pinned this at rate 0.0 and asserted the twin was scored with weight
    0.0; that is now forbidden -- a zero-weight sample moves MUST_REACT's
    weight-blind min(). The rate-0.0 case is covered by its own counterexample
    above, which asserts the twin is excluded outright.)"""
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.35")
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    mega_rows = [e for e in evidence if e.foe_mega_slot == 0]
    assert mega_rows
    assert all(e.response_id.endswith("|mega=0") for e in mega_rows)
    # The click-rate-derived weight survived the replan: neither 0 (dropped) nor
    # 1.0 (replaced by the regenerated base response's default weight).
    assert all(0.0 < e.response_weight < 1.0 for e in mega_rows)


def test_scoring_evidence_proves_required_classes_were_retained(mega_decision_tie_fixture):
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    assert evidence
    assert all(set(e.required_classes) <= set(e.retained_classes) for e in evidence)
    assert all(e.required_classes == ("0", "none") for e in evidence)


def test_no_eligibility_is_byte_identical_to_pre_i7b_scoring(mega_decision_fixture):
    """Reg-I / omitted-kwarg safety net: calling with the two new
    keyword-only parameters left at their defaults must be numerically
    identical to calling with them passed explicitly as empty/None, and must
    use the UNCHANGED legacy weighting gate (not finding 3's I7b-active
    override)."""
    req, kw = mega_decision_fixture
    records_default = _score(kw, req)
    records_explicit = _score(kw, req, eligibility=None)
    assert len(records_default) == len(records_explicit)
    for a, b in zip(records_default, records_explicit):
        assert a.score_vector == pytest.approx(b.score_vector)
        assert a.score_weights == pytest.approx(b.score_weights)


def test_legacy_path_leaves_diagnostic_contexts_structurally_empty(mega_decision_fixture):
    """Parity is STRUCTURAL, not just numeric. Task 6's depth-2 binding is specified
    as `rec.diagnostic_contexts[i] if rec.diagnostic_contexts else
    ctx_by_slot[rec.variant.own_mega_slot]` -- i.e. an EMPTY list means "pre-I7b-B,
    use the legacy blanket context". Populating the field on the legacy path would
    make that fallback dead code and quietly falsify the byte-identity claim, even
    though the bound context happens to be numerically the same one."""
    req, kw = mega_decision_fixture
    records = _score(kw, req)  # no eligibility => legacy path
    assert records
    assert all(r.diagnostic_contexts == [] for r in records)


def test_active_path_binds_one_diagnostic_context_per_diagnostic_index(mega_decision_tie_fixture):
    """...and when I7b IS active the parallel-array contract must hold, so Task 6
    can index diagnostic_contexts[i] directly against diagnostic_details[i]. A
    record's top-M may span a no-mega response AND foe-mega branch responses, which
    is exactly why the per-index binding exists."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    records = _score(kw, req, eligibility=eligibility)
    assert records
    for r in records:
        assert r.diagnostic_contexts
        assert len(r.diagnostic_contexts) == len(r.diagnostic_details)
        assert len(r.diagnostic_contexts) == len(r.diagnostic_weights)
    # at least one record must genuinely span both kinds, or the per-index binding
    # would be untested in practice
    assert any(
        {c.foe_mega_slot is None for c in r.diagnostic_contexts} == {True, False}
        for r in records
    ), "no record's diagnostics span both a no-mega and a foe-mega branch context"


def test_flush_count_is_bounded_independent_of_candidate_count(mega_decision_tie_fixture, monkeypatch):
    """Every model shares one oracle and all enqueues precede Phase B, so the
    complete world's pending queue is resolved by exactly one flush."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    call_count = {"n": 0}
    real_flush = kw["oracle"].flush

    def counting_flush():
        call_count["n"] += 1
        return real_flush()

    monkeypatch.setattr(kw["oracle"], "flush", counting_flush)
    records = _score(kw, req, eligibility=eligibility)
    assert len(records) >= 2  # this fixture must score more than one candidate
    assert call_count["n"] == 1


def test_foe_mega_with_unsupported_ability_is_excluded_not_crashed(
    mega_decision_unsupported_ability_fixture,
):
    """Task 5. A foe eligibility entry resolving to an unsupported-ability form
    (Scovillain-Mega / 'Spicy Spray') must be silently excluded from
    evidence/scoring via the SAME UnsupportedMegaAbilityError/FAIL_CLOSED_ABILITIES
    gate I7a already uses -- never a new exception type, never an alternate gate,
    never a crash.

    Test-only proof of Task 4's existing
    `try/except (UnsupportedMegaAbilityError, MissingMegaSpreadError): branches = []`.
    No production change belongs to this task: if this fails, the gap is in Task 4's
    implementation, not a missing mechanism here.

    [REV.5 correction 3] The foe really IS a Scovillain and eligibility comes from
    the real foe_mega_eligibility(), so Task 2's coherence check passes and the
    ability gate is the thing under test. Rev. 4 injected the form onto a mismatched
    species, which post-correction-2 raises MegaProjectionSpeciesMismatchError first
    -- an error Task 4 deliberately does NOT catch."""
    req, kw = mega_decision_unsupported_ability_fixture
    eligibility = _real_eligibility(kw)
    # The gate's real target, resolved through the real limited-view path -- not a
    # hand-built MegaForm.
    assert eligibility["a"].form_species_id == "scovillainmega"
    assert eligibility["a"].base_species_id == "scovillain"

    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence)

    # Exclusion, proven off the real foe_mega_slot field -- never by parsing
    # response_id's "|mega=" suffix.
    assert all(e.foe_mega_slot != 0 for e in evidence)
    # ...and it is exclusion, not wipe-out: the no-Mega rows stay scoreable.
    assert evidence
    assert all(e.foe_mega_slot is None for e in evidence)
    assert records and all(r.score_vector for r in records)


def test_depth2_for_foe_mega_branch_uses_that_branchs_own_projected_state(
    mega_decision_tie_fixture, monkeypatch,
):
    """Task 6. Depth-2 refinement of a foe-Mega-tagged top-M response must be bound
    to THAT response's own composed branch's MegaEvaluationContext -- never a
    different branch's, and never the record's own-only ctx_by_slot entry.

    Proven by spying on the REAL depth2_value_for_mega_context and delegating to it;
    a fake return value would prove nothing about which board the refinement ran on.

    RED before the fix: depth-2 genuinely runs and seen_ctxs is non-empty, but the
    wrap binds every diagnostic index to the single blanket
    ctx_by_slot[rec.variant.own_mega_slot], so no context with
    foe_mega_slot is not None ever reaches the function -- a foe-Mega branch's
    diagnostic is refined against the own-only board instead of its own branch board.
    """
    import showdown_bot.battle.mega_scoring as mega_scoring_mod

    req, kw = mega_decision_tie_fixture
    _assert_pre_mega_speeds_tie(kw)
    eligibility = _real_eligibility(kw)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "1")
    # SHOWDOWN_SEARCH_TOPM: at the default M=2 and the default click rate 0.35 the
    # top-M frontier is all-no-mega and this code path is never reached. Measured on
    # this fixture, not guessed -- a record's diagnostic weights are
    #   [0.2453, 0.2453, 0.2453, 0.1321, 0.1321]
    #   ctx foe_mega_slot: [None, None, None, 0, 0]
    # i.e. each no-mega twin (0.65 x W) outweighs each foe-Mega branch response
    # (0.35 x W x 0.5 branch weight), so top-2 picks indices [0, 1], both no-mega.
    # Widening M to 5 makes the frontier span BOTH kinds, which is precisely the
    # condition the per-index binding exists for (a record's top-M may legitimately
    # include a foe-Mega branch response). This is an existing production knob
    # (_search_topm), not a test-only hook.
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPM", "5")

    seen_ctxs: list = []
    real_fn = mega_scoring_mod.depth2_value_for_mega_context

    def spy(ctx, outcome, **kwargs):
        seen_ctxs.append(ctx)
        return real_fn(ctx, outcome, **kwargs)  # delegate to the REAL function

    monkeypatch.setattr(mega_scoring_mod, "depth2_value_for_mega_context", spy)

    _score(kw, req, eligibility=eligibility)

    assert seen_ctxs, "depth-2 gate must actually have fired for this fixture"
    foe_mega_ctxs = [c for c in seen_ctxs if c.foe_mega_slot is not None]
    assert foe_mega_ctxs, (
        "no foe-Mega branch context reached depth-2 -- every index was bound to the "
        "blanket own-only ctx_by_slot[rec.variant.own_mega_slot]"
    )
    # The binding is genuinely PER INDEX, not "always the branch ctx": the same
    # frontier must also still bind no-mega indices to the own-only context.
    assert [c for c in seen_ctxs if c.foe_mega_slot is None], (
        "no-mega indices must still bind to their own-only ctx_by_slot entry"
    )

    own_only = {c.own_mega_slot: c for c in kw["contexts"]}
    for c in foe_mega_ctxs:
        assert c.foe_mega_slot in (0, 1)
        # genuinely a post-branch board: the foe has spent its Mega on it
        assert c.projected_state.side_mega_spent.get("p2", False)
        # ...and it is the branch-specific context, not the blanket own-only one
        assert c is not own_only[c.own_mega_slot]
        assert c.context_id.startswith("foe_mega:")


def test_branch_replan_speed_matches_final_branch_state_speed(mega_decision_tie_fixture, monkeypatch):
    """[REV.6] The own-Mega speed override fed into the branch replan -- and the
    speed actually stored on the resulting PlannedAction -- must equal the speed
    derived from the COMPLETE, FINAL branch.projected_state via the central
    resolver.

    Rev. 4/5 read `branch.projected_state.sides[our_side][...].effective_speed`,
    which does not exist on PokemonState. RED before the Rev. 6 correction with the
    real error:
        AttributeError: 'PokemonState' object has no attribute 'effective_speed'
    """
    import showdown_bot.battle.mega_scoring as ms

    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)

    real_plan = ms._plan_my_actions
    captured: list[dict] = []

    def _spy_plan(req_, ja, *, state, our_side, opp_side, speed_oracle,
                  planned_speed_overrides_by_slot=None):
        out = real_plan(
            req_, ja, state=state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
            planned_speed_overrides_by_slot=planned_speed_overrides_by_slot,
        )
        captured.append({
            "state": state, "overrides": planned_speed_overrides_by_slot, "plan": out,
        })
        return out

    monkeypatch.setattr(ms, "_plan_my_actions", _spy_plan)
    _score(kw, req, eligibility=eligibility)

    branch_calls = [
        c for c in captured
        if c["overrides"] and c["state"].side_mega_spent.get("p2", False)
    ]
    assert branch_calls, "no foe-Mega branch replan carrying an own-Mega speed override was observed"

    for call in branch_calls:
        for slot_idx, override_speed in call["overrides"].items():
            letter = "a" if slot_idx == 0 else "b"
            mon = call["state"].sides["p1"][letter]
            expected = kw["speed_oracle"].speed_for_species(
                species_name=mon.species,
                base_species_id=mon.base_species_id or mon.species,
                side="p1", mon=mon, field=call["state"].field,
                our_spreads=kw["our_spreads"], opp_sets=None, book=kw["book"], is_ours=True,
            )
            assert override_speed == expected, (
                f"override {override_speed} != final-branch-state speed {expected}"
            )
            stored = [a for a in call["plan"] if a.slot == letter and a.is_ours]
            assert stored, f"no own PlannedAction for slot {letter}"
            assert stored[0].speed == expected, (
                f"PlannedAction.speed {stored[0].speed} != final-branch-state speed {expected}"
            )
