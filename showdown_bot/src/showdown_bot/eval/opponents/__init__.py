"""Eval-only opponent policies (T3c).

These are used ONLY by the gauntlet eval dispatch (`client/gauntlet.agent_choose`), never
by the live bot's decision path (`battle/decision.heuristic_choose_for_request`). They are
deterministic request→choice functions for reproducible paired eval.
"""
