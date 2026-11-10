"""
star_hash.seal
~~~~~~~~~~~~~~
Sign a document with a seal, and check a seal against a document.

A seal is a drawing and nothing else. The sky inside the horizon carries the
place and time; a ring of ticks around it spells the first 128 bits of the
document's SHA-256. There is no hidden record: whatever a seal says, it says
in its geometry.

A seal records a claim. It shows that a drawing, a place and time, and a
document belong together; it cannot show that anyone was actually there then.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

SCHEMA = "starhash/2"
RING_BYTES = 16  # leading bytes of the document's SHA-256 drawn around the horizon
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

Document = Union[str, "os.PathLike[str]", bytes]
Date = Union[datetime, str, float, None]


@dataclass
class SignedSeal:
    digest: str
    svg: str
    claim: Dict[str, Any]

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.svg)


def document_sha256(document: Document) -> str:
    """SHA-256 of a file (given by path) or of raw bytes."""
    digest = hashlib.sha256()
    if isinstance(document, (bytes, bytearray)):
        digest.update(document)
    else:
        with open(document, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _base58(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    chars = []
    while number:
        number, rem = divmod(number, 58)
        chars.append(_BASE58[rem])
    return "".join(reversed(chars)).rjust(22, _BASE58[0])


def claim_digest(latitude: float, longitude: float, elevation_m: float, time: str, sha256: str) -> str:
    """Short id for an exact place, time and document.

    It is not drawn in the seal. Keep it beside the seal if you want to be
    able to state the exact claim later; anyone given the same place, time
    and document can recompute it.
    """
    payload = "\n".join(
        [SCHEMA, f"{latitude:.5f}", f"{longitude:.5f}", f"{elevation_m:.1f}", time, sha256]
    )
    token = _base58(hashlib.blake2b(payload.encode("utf-8"), digest_size=16).digest())
    return "STARS-" + "-".join(token[i:i + 4] for i in range(0, len(token), 4))


def _whole_second(date: Date) -> datetime:
    if date is None:
        moment = datetime.now(timezone.utc)
    elif isinstance(date, datetime):
        moment = date
    elif isinstance(date, str):
        moment = datetime.fromisoformat(date.replace("Z", "+00:00"))
    elif isinstance(date, (int, float)) and not isinstance(date, bool):
        moment = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=date - 2451545.0)
        moment += timedelta(microseconds=500000)
    else:
        raise ValueError(f"Unsupported date format: {type(date)}")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def _canonical(latitude: float, longitude: float, elevation_m: float, date: Date):
    for label, value in (("latitude", latitude), ("longitude", longitude), ("elevation_m", elevation_m)):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
    return (
        round(latitude, 5) + 0.0,
        round(longitude, 5) + 0.0,
        round(elevation_m, 1) + 0.0,
        _whole_second(date),
    )


def sign(
    document: Document,
    latitude: float,
    longitude: float,
    date: Date = None,
    elevation_m: float = 0.0,
    size: int = 512,
    name: Optional[str] = None,
) -> SignedSeal:
    """Cast a seal for ``document`` at a place and time.

    ``document`` is a path or raw bytes. Coordinates are kept to five decimal
    places (about a metre) and the time to the whole second, so the same
    inputs always give the same drawing. ``date`` defaults to now; a string
    or datetime without a zone is taken as UTC.

    The returned ``svg`` is the drawing alone. ``claim`` and ``digest``
    describe what was sealed but are not stored in it.
    """
    from star_hash import starhash

    latitude, longitude, elevation_m, moment = _canonical(latitude, longitude, elevation_m, date)
    time = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    sha256 = document_sha256(document)
    seal = starhash(
        latitude, longitude, moment, elevation_m=elevation_m, size=size,
        document_digest=bytes.fromhex(sha256)[:RING_BYTES],
    )
    record: Dict[str, Any] = {"sha256": sha256}
    if not isinstance(document, (bytes, bytearray)):
        record["name"] = name or os.path.basename(os.fspath(document))
        record["bytes"] = os.path.getsize(document)
    else:
        if name:
            record["name"] = name
        record["bytes"] = len(document)

    digest = claim_digest(latitude, longitude, elevation_m, time, sha256)
    claim = {
        "digest": digest,
        "latitude": latitude,
        "longitude": longitude,
        "elevation_m": elevation_m,
        "time": time,
        "julian_day": seal.julian_day,
        "document": record,
    }
    return SignedSeal(digest=digest, svg=seal.svg, claim=claim)


def ring_matches(ring: Optional[str], document: Document) -> Optional[bool]:
    """Whether a drawing's tick ring is the hash of ``document`` (None: no ring)."""
    if not ring:
        return None
    return len(ring) >= 2 * RING_BYTES and document_sha256(document).startswith(ring)


def _without_record(svg: str) -> str:
    """Drop the hidden record that version 1.1 seals carried."""
    return re.sub(r'\n?\s*<metadata id="starhash">.*?</metadata>', "", svg, count=1, flags=re.S)


def _check(name: str, ok: Optional[bool], detail: str) -> Dict[str, Any]:
    return {"check": name, "ok": ok, "detail": detail}


def verify(
    svg: str,
    document: Optional[Document] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    date: Date = None,
    elevation_m: float = 0.0,
    year_from: int = 1800,
    year_to: int = 2200,
) -> Dict[str, Any]:
    """Check a seal from its drawing, against a document and a stated claim.

    * ``sky``: the drawing is a real sky; the place and time it shows are
      read back and returned as ``reading``.
    * ``document``: the tick ring is the hash of ``document`` (skipped if no
      document is given).
    * ``claim``: the drawing is the seal of ``latitude``, ``longitude`` and
      ``date``, to the resolution of the drawing: about a hundred metres and
      a second at the default size (skipped unless all three are given).

    ``ok`` is True when no check that ran has failed.
    """
    from star_hash import starhash
    from star_hash.read import SealReadError, parse_drawing, read_seal

    svg = _without_record(svg)
    checks: List[Dict[str, Any]] = []
    reading = None
    try:
        reading = read_seal(svg, year_from=year_from, year_to=year_to)
        whole = reading.stars_matched >= 0.97 * reading.stars_drawn
        if reading.time is None:
            sky_ok = whole
            detail = (
                f"drawing is a real sky at latitude {reading.latitude:+.2f}°; "
                "its date cannot be read (no Moon, Sun or planet is up)"
            )
        else:
            # Redraw the sky that was read and require every mark to be there.
            drawn = parse_drawing(svg)
            redrawn = parse_drawing(starhash(
                reading.latitude, reading.longitude, reading.julian_day, size=int(drawn.size),
            ).svg)
            reach = max(0.05, 0.4 * drawn.size / 512.0)
            in_place = all(
                any(abs(x - u) <= reach and abs(y - v) <= reach for u, v in redrawn.pixels)
                for x, y in drawn.pixels
            )
            sky_ok = in_place and reading.converged and (reading.residual_px or 0.0) <= 0.02
            detail = f"drawing is a real sky, read as {reading.time}"
        if not sky_ok:
            detail = "drawing is not a consistent sky: stars or planets are out of place"
    except SealReadError as error:
        sky_ok, detail = False, f"drawing could not be read: {error}"
    checks.append(_check("sky", sky_ok, detail))

    ring = reading.document_ring if reading else None
    if document is None:
        checks.append(_check("document", None, "no document given, so not compared"))
    elif ring is None:
        checks.append(_check("document", False, "drawing has no document ring"))
    else:
        match = bool(ring_matches(ring, document))
        checks.append(_check(
            "document", match,
            "document is the one in the tick ring" if match
            else "document is not the one in the tick ring",
        ))

    claim: Optional[Dict[str, Any]] = None
    if latitude is None or longitude is None or date is None:
        checks.append(_check("claim", None, "no place and time stated, so not compared exactly"))
    else:
        lat, lon, elev, moment = _canonical(latitude, longitude, elevation_m, date)
        time = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        claim = {"latitude": lat, "longitude": lon, "elevation_m": elev, "time": time}
        try:
            drawn = parse_drawing(svg)
            fresh_svg = starhash(
                lat, lon, moment, elevation_m=elev, size=int(drawn.size),
                document_digest=bytes.fromhex(drawn.document_ring) if drawn.document_ring else None,
            ).svg
            exact = svg.strip() == fresh_svg.strip()
            if not exact:
                fresh = parse_drawing(fresh_svg)
                exact = (
                    len(drawn.pixels) == len(fresh.pixels)
                    and sorted(drawn.bodies) == sorted(fresh.bodies)
                    and all(
                        abs(a[0] - b[0]) <= 0.015 and abs(a[1] - b[1]) <= 0.015
                        for a, b in zip(drawn.pixels, fresh.pixels)
                    )
                )
        except (SealReadError, ValueError):
            exact = False
        checks.append(_check(
            "claim", exact,
            "drawing is the sky of the stated place and time, as finely as it can show" if exact
            else "drawing is not the sky of the stated place and time",
        ))

    return {
        "ok": all(c["ok"] is not False for c in checks),
        "checks": checks,
        "reading": reading.as_dict() if reading else None,
        "claim": claim,
    }
