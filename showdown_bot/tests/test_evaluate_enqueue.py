# Enqueue must NOT flush; prefetch must enqueue THEN flush. Fake oracle counts flushes.
from showdown_bot.battle.evaluate import DamageModel


class _FakeOracle:
    def __init__(self): self.requests = 0; self.flushes = 0
    def request(self, req): self.requests += 1
    def flush(self): self.flushes += 1
    def get(self, req): return 0.0


def _model():
    m = DamageModel.__new__(DamageModel)   # bypass __init__ (no state/calc needed)
    m.oracle = _FakeOracle()
    m.hyps = {}
    return m


def test_enqueue_does_not_flush():
    m = _model()
    m.enqueue([])          # empty groups -> no requests, MUST NOT flush
    assert m.oracle.flushes == 0


def test_prefetch_flushes_once():
    m = _model()
    m.prefetch([])
    assert m.oracle.flushes == 1
