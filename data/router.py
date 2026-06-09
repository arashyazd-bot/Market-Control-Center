"""Health-aware source router.

One failover primitive — ``chain()`` — that every orchestrated fetch routes
through. It tries candidate sources in priority order, returns the first LIVE
result, and stamps the winning provider onto the DataResult (provenance). When a
source signals exhaustion (HTTP 429 daily limit / 402 premium / 401 bad key) it
is put in a cooldown and SKIPPED on subsequent calls — so we never burn time or
quota re-hitting a dead source, and we never have to guess where data came from.
"""
from __future__ import annotations

import time

from data import DataResult

# source name -> unix timestamp until which the source is skipped
_LIMITED_UNTIL: dict[str, float] = {}
# source name -> last human status ("ok" or an error note), for the sources panel
_LAST_NOTE: dict[str, str] = {}


def mark_limited(source: str, seconds: float, note: str = "") -> None:
    _LIMITED_UNTIL[source] = time.time() + seconds
    if note:
        _LAST_NOTE[source] = note[:80]


def is_limited(source: str) -> bool:
    return time.time() < _LIMITED_UNTIL.get(source, 0.0)


def cooldown_remaining(source: str) -> int:
    return max(0, int(_LIMITED_UNTIL.get(source, 0.0) - time.time()))


def note_for(source: str) -> str:
    return _LAST_NOTE.get(source, "")


def status() -> dict[str, dict]:
    """Snapshot of every source the router has seen — for the methodology panel."""
    return {s: {"note": _LAST_NOTE.get(s, ""), "cooldown": cooldown_remaining(s)}
            for s in set(_LAST_NOTE) | set(_LIMITED_UNTIL)}


def _record_failure(source: str, note: str) -> None:
    n = (note or "").lower()
    _LAST_NOTE[source] = (note or "no data")[:80]
    # Account-wide outages cool down the whole source so we stop hammering it:
    if any(k in n for k in ("429", "limit reach", "too many")):
        mark_limited(source, 1800, note)      # daily quota exhausted: 30-min cooldown
    elif any(k in n for k in ("401", "invalid api key")):
        mark_limited(source, 3600, note)      # bad key: 1-hour cooldown
    # NOTE: 402 "premium" is endpoint-specific (that feed needs a paid tier), NOT
    # an account outage — record the note but keep the source usable for others.


def chain(candidates, sample_fn=None) -> DataResult:
    """Try each (source_name, fetch_fn) in order.

    fetch_fn() must return a DataResult (is_sample=False on success). Sources in
    cooldown are skipped. Returns the first live result with .source set. If all
    fail: sample_fn() tagged source='sample' (is_sample=True) when provided, else
    a None 'unavailable' marker so callers can render an honest empty state.
    """
    notes = []
    for source, fn in candidates:
        if is_limited(source):
            notes.append(f"{source}: cooldown {cooldown_remaining(source)}s")
            continue
        try:
            r = fn()
        except Exception as exc:  # defensive — fetchers shouldn't raise
            _record_failure(source, str(exc))
            notes.append(f"{source}: {str(exc)[:60]}")
            continue
        if r is not None and not r.is_sample and r.data is not None:
            r.source = source
            _LAST_NOTE[source] = "ok"
            _LIMITED_UNTIL.pop(source, None)
            return r
        note = (r.note if r is not None else "") or "no data"
        _record_failure(source, note)
        notes.append(f"{source}: {note[:60]}")

    agg = " | ".join(notes)[:200]
    if sample_fn is not None:
        try:
            return DataResult(sample_fn(), is_sample=True, source="sample", note=agg)
        except Exception as exc:
            agg = (agg + f" | sample:{exc}")[:200]
    return DataResult(None, is_sample=True, source="sample", note=agg)
