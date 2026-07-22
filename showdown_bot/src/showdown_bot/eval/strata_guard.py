"""Windows/Kaggle hardware-stratum guard (DESIGN sec 3.5). Fail-closed: only an explicit
attestation (env_override, or Windows sniffed via platform.system()) selects a stratum. A bare
non-Windows box is NOT assumed to be the approved Kaggle environment -- it could be any
unattested machine, and DESIGN requires Kaggle to be a deliberate, separately pre-registered
stratum, not a default. An env_override may only CONFIRM what platform.system() can prove, never
CONTRADICT it (Rev. 16, §1o, P1 #1) -- it selects between platform-consistent choices, it does
not let a caller relabel whatever machine is actually running as a different stratum."""
from __future__ import annotations

import platform
from dataclasses import dataclass

WINDOWS_STRATUM = "windows"
KAGGLE_STRATUM = "kaggle"
VALID_STRATA = (WINDOWS_STRATUM, KAGGLE_STRATUM)


class StrataPoolingError(Exception):
    pass


class UnattestedStratumError(Exception):
    pass


@dataclass(frozen=True)
class StratumRecord:
    stratum: str
    platform_string: str
    output_dir: str


def detect_stratum(*, env_override: str | None = None) -> str:
    is_windows = platform.system() == "Windows"
    if env_override is not None:
        if env_override not in VALID_STRATA:
            raise ValueError(f"unknown stratum {env_override!r}, expected one of {VALID_STRATA}")
        # Rev. 16 fix (§1o, P1 #1): before this check, env_override bypassed platform.system()
        # entirely -- env_override="kaggle" on the real, fixed Windows measurement host (or the
        # reverse on a non-Windows box) succeeded silently. The override may only select between
        # platform-CONSISTENT choices, never contradict what platform.system() can already prove.
        if env_override == KAGGLE_STRATUM and is_windows:
            raise UnattestedStratumError(
                f"env_override={env_override!r} claims the Kaggle stratum, but this machine's "
                "platform.system() is Windows -- the fixed Windows measurement host must never "
                "be relabeled as Kaggle"
            )
        if env_override == WINDOWS_STRATUM and not is_windows:
            raise UnattestedStratumError(
                f"env_override={env_override!r} claims the Windows stratum, but "
                f"platform.system()={platform.system()!r} is not Windows -- the override may "
                "not contradict what the platform can already prove"
            )
        return env_override
    if is_windows:
        return WINDOWS_STRATUM
    raise UnattestedStratumError(
        f"platform.system()={platform.system()!r} is not Windows and no env_override was given "
        "-- pass env_override='kaggle' explicitly on the approved Kaggle environment; a bare "
        "non-Windows host is never assumed to be Kaggle"
    )


def assert_no_cross_stratum_pooling(records: list[StratumRecord]) -> None:
    if not records:
        raise ValueError("assert_no_cross_stratum_pooling requires at least one record")
    strata = {r.stratum for r in records}
    if len(strata) > 1:
        detail = ", ".join(f"{r.output_dir} ({r.stratum})" for r in records)
        raise StrataPoolingError(
            f"records span {len(strata)} strata ({sorted(strata)}) -- refusing to pool: {detail}"
        )


def stratum_output_root(stratum: str, base_dir: str) -> str:
    if stratum not in VALID_STRATA:
        raise ValueError(f"unknown stratum {stratum!r}, expected one of {VALID_STRATA}")
    return f"{base_dir}/{stratum}"
