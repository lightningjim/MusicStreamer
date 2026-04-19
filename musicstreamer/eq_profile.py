"""AutoEQ ParametricEQ.txt parser/serializer (Phase 47.2 D-21/D-22/D-23 revised).

Public API:
  parse_autoeq(text: str) -> EqProfile       # raises ValueError on malformed
  serialize_autoeq(profile: EqProfile) -> str
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

FilterType = Literal["PK", "LSC", "HSC"]   # C-1 correction to D-22 (LSC/HSC, not LS/HS)

_PREAMP_RE = re.compile(
    r"^\s*Preamp\s*:\s*(-?\d+(?:\.\d+)?)\s*dB\s*$",
    re.IGNORECASE,
)

_FILTER_RE = re.compile(
    r"""^\s*Filter\s+\d+\s*:\s*
         (?P<state>ON|OFF)\s+
         (?P<type>PK|LSC|HSC)\s+
         Fc\s+(?P<freq>-?\d+(?:\.\d+)?)\s*Hz\s+
         Gain\s+(?P<gain>-?\d+(?:\.\d+)?)\s*dB\s+
         Q\s+(?P<q>-?\d+(?:\.\d+)?)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class EqBand:
    filter_type: FilterType
    freq_hz: float
    gain_db: float
    q: float


@dataclass
class EqProfile:
    preamp_db: float = 0.0
    bands: list = field(default_factory=list)


def parse_autoeq(text: str) -> EqProfile:
    profile = EqProfile()
    any_on = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _PREAMP_RE.match(line)
        if m:
            profile.preamp_db = float(m.group(1))
            continue
        m = _FILTER_RE.match(line)
        if m:
            if m.group("state").upper() == "OFF":
                continue
            any_on = True
            profile.bands.append(EqBand(
                filter_type=m.group("type").upper(),  # type: ignore[arg-type]
                freq_hz=float(m.group("freq")),
                gain_db=float(m.group("gain")),
                q=float(m.group("q")),
            ))
            continue
        # unknown non-empty lines silently skipped
    if not any_on:
        raise ValueError("AutoEQ file contains no ON filters")
    return profile


def serialize_autoeq(profile: EqProfile) -> str:
    lines = [f"Preamp: {profile.preamp_db:.1f} dB"]
    for i, b in enumerate(profile.bands, start=1):
        lines.append(
            f"Filter {i}: ON {b.filter_type} "
            f"Fc {b.freq_hz:g} Hz Gain {b.gain_db:.1f} dB Q {b.q:.2f}"
        )
    return "\n".join(lines) + "\n"
