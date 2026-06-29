from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from showdown_bot.engine.calc.models import DamageRequest, DamageResult

DEFAULT_CALC_DIR = Path(__file__).resolve().parents[4] / "tools" / "calc"


class CalcError(RuntimeError):
    """Raised when the calc backend fails to produce results."""


@runtime_checkable
class CalcBackend(Protocol):
    """Transport-agnostic damage backend.

    Phase 1 uses a one-shot subprocess; Phase 2 can drop in a persistent Node
    process (line protocol / JSON-RPC) without any change to ``CalcClient`` or
    its callers. Batching is part of the contract so a future backend can
    answer many requests in a single round trip.
    """

    def calc_batch(self, requests: list[DamageRequest]) -> list[DamageResult]: ...


class SubprocessCalcBackend:
    """One-shot ``node calc.mjs`` per batch. Bundles all requests into a single
    stdin array so a batch never pays N x Node startup (~50-100ms each)."""

    def __init__(
        self,
        calc_dir: Path | None = None,
        *,
        node: str = "node",
        script: str = "calc.mjs",
        timeout: float = 20.0,
    ) -> None:
        self.calc_dir = calc_dir or DEFAULT_CALC_DIR
        self.node = node
        self.script = script
        self.timeout = timeout

    def calc_batch(self, requests: list[DamageRequest]) -> list[DamageResult]:
        if not requests:
            return []
        payload = json.dumps([r.to_payload() for r in requests])
        try:
            proc = subprocess.run(
                [self.node, self.script],
                input=payload,
                capture_output=True,
                text=True,
                cwd=str(self.calc_dir),
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise CalcError(f"node executable not found: {self.node}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CalcError(f"calc subprocess timed out after {self.timeout}s") from exc

        if proc.returncode != 0:
            raise CalcError(
                f"calc subprocess failed (rc={proc.returncode}): {proc.stderr.strip()}"
            )

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise CalcError(f"calc returned invalid JSON: {proc.stdout[:200]!r}") from exc

        if isinstance(data, dict) and data.get("error"):
            raise CalcError(f"calc error: {data['error']}")

        return [DamageResult.from_json(item) for item in data]


class CalcClient:
    """Caller-facing API. Does not know whether the backend is a one-shot
    subprocess or a persistent process."""

    def __init__(self, backend: CalcBackend | None = None) -> None:
        self.backend: CalcBackend = backend or SubprocessCalcBackend()

    def damage(self, request: DamageRequest) -> DamageResult:
        return self.damage_batch([request])[0]

    def damage_batch(self, requests: list[DamageRequest]) -> list[DamageResult]:
        prepared: list[DamageRequest] = []
        for idx, req in enumerate(requests):
            if req.id is None:
                req.id = f"req{idx}"
            prepared.append(req)

        results = self.backend.calc_batch(prepared)

        by_id = {res.id: res for res in results if res.id is not None}
        if len(by_id) == len(prepared):
            ordered = [by_id[req.id] for req in prepared]
        else:
            # Backend did not echo ids reliably; fall back to positional order.
            ordered = results

        errors = [r for r in ordered if r.error]
        if errors:
            raise CalcError("; ".join(str(e.error) for e in errors))
        return ordered
