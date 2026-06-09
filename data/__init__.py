"""Data layer. Every fetch returns a ``DataResult`` so panels can render a
'sample data' badge whenever a live source/key was unavailable and we fell back
to bundled data — the dashboard never silently fakes state."""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any

# Backstop: bound any socket that doesn't set its own timeout (e.g. fredapi's
# urllib calls) so a stalled connection can never hang a render. requests-based
# fetches set their own (shorter) timeouts, which take precedence.
socket.setdefaulttimeout(10)


@dataclass
class DataResult:
    """Wrapper around any fetched payload.

    Attributes
    ----------
    data : Any
        The payload (pandas Series/DataFrame, dict, float, ...).
    is_sample : bool
        True when ``data`` came from the bundled fallback rather than a live source.
    note : str
        Optional human-readable reason for the fallback (shown on hover).
    """

    data: Any
    is_sample: bool = False
    note: str = ""
    meta: dict = field(default_factory=dict)
    source: str = "sample"   # provenance: which provider served this value

    @property
    def badge(self) -> str:
        return "🟡 sample" if self.is_sample else "🟢 live"
