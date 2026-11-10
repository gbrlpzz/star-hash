"""
star_hash.seal
~~~~~~~~~~~~~~
Sign a document with a seal, and check a seal against a document.

A signed seal is the sky drawing, a ring of ticks around the horizon that
spells the first 128 bits of the document's SHA-256, and an invisible
``<metadata>`` record: the claimed place and time, the full SHA-256, and a
short digest over all of them.

A seal records a claim. It shows that the drawing, the stated place and time,
and the document belong together; it cannot show that anyone was actually
there then.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from xml.sax.saxutils import escape, unescape

SCHEMA = "starhash/1"
RING_BYTES = 16  # leading bytes of the document's SHA-256 drawn around the horizon
_METADATA = re.compile(r'<metadata id="starhash">(.*?)</metadata>', re.S)
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

Document = Union[str, "os.PathLike[str]", bytes]


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
    """Short digest binding a place, a time and a document together."""
    payload = "\n".join(
        [SCHEMA, f"{latitude:.5f}", f"{longitude:.5f}", f"{elevation_m:.1f}", time, sha256]
    )
    token = _base58(hashlib.blake2b(payload.encode("utf-8"), digest_size=16).digest())
    return "STARS-" + "-".join(token[i:i + 4] for i in range(0, len(token), 4))


def _whole_second(date: Union[datetime, str, float, None]) -> datetime:
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


def sign(
    document: Document,
    latitude: float,
    longitude: float,
    date: Union[datetime, str, float, None] = None,
    elevation_m: float = 0.0,
    size: int = 512,
    name: Optional[str] = None,
) -> SignedSeal:
    """Cast a seal for ``document`` at a place and time.

    ``document`` is a path or raw bytes. Coordinates are kept to five decimal
    places (about a metre) and the time to the whole second, so that the seal
    can be recomputed exactly from its own record. ``date`` defaults to now;
    a string or datetime without a zone is taken as UTC.
    """
    from star_hash import starhash

    for label, value in (("latitude", latitude), ("longitude", longitude), ("elevation_m", elevation_m)):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
    latitude = round(latitude, 5) + 0.0
    longitude = round(longitude, 5) + 0.0
    elevation_m = round(elevation_m, 1) + 0.0
    moment = _whole_second(date)
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
        "schema": SCHEMA,
        "digest": digest,
        "latitude": latitude,
        "longitude": longitude,
        "elevation_m": elevation_m,
        "time": time,
        "julian_day": seal.julian_day,
        "document": record,
    }
    return SignedSeal(digest=digest, svg=_embed(seal.svg, claim), claim=claim)


def ring_matches(ring: Optional[str], document: Document) -> Optional[bool]:
    """Whether a drawing's tick ring is the hash of ``document`` (None: no ring)."""
    if not ring:
        return None
    return len(ring) >= 2 * RING_BYTES and document_sha256(document).startswith(ring)


def _embed(svg: str, claim: Dict[str, Any]) -> str:
    head, sep, tail = svg.partition(">")
    body = escape(json.dumps(claim, ensure_ascii=False, sort_keys=True))
    return f'{head}{sep}\n  <metadata id="starhash">{body}</metadata>{tail}'


def read_claim(svg: str) -> Optional[Dict[str, Any]]:
    """The claim embedded in a signed seal, or None if there is none."""
    match = _METADATA.search(svg)
    if not match:
        return None
    try:
        claim = json.loads(unescape(match.group(1)))
    except ValueError:
        return None
    return claim if isinstance(claim, dict) else None


def _strip_claim(svg: str) -> str:
    return re.sub(r'\n?\s*<metadata id="starhash">.*?</metadata>', "", svg, count=1, flags=re.S)


def _check(name: str, ok: Optional[bool], detail: str) -> Dict[str, Any]:
    return {"check": name, "ok": ok, "detail": detail}


def verify(svg: str, document: Optional[Document] = None) -> Dict[str, Any]:
    """Check a signed seal, and optionally the document it was cast for.

    Three things are checked: that the embedded record is intact, that the
    drawing is the sky of the recorded place and time, and that the document
    is the one recorded. The result has ``ok`` (every check that could be run
    passed), ``checks`` (``ok`` is None for a check that was skipped) and the
    ``claim``.
    """
    from star_hash import starhash
    from star_hash.read import SealReadError, parse_drawing

    checks: List[Dict[str, Any]] = []
    ring: Optional[str] = None
    claim = read_claim(svg)
    if claim is None:
        checks.append(_check("record", False, "no Starhash record in this file; "
                             "use `starhash read` to decode the drawing itself"))
        return {"ok": False, "checks": checks, "claim": None}

    try:
        if claim.get("schema") != SCHEMA:
            raise ValueError(f"unknown schema {claim.get('schema')!r}")
        latitude = float(claim["latitude"])
        longitude = float(claim["longitude"])
        elevation_m = float(claim["elevation_m"])
        time = str(claim["time"])
        sha256 = str(claim["document"]["sha256"])
        moment = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        expected = claim_digest(latitude, longitude, elevation_m, time, sha256)
    except (KeyError, TypeError, ValueError) as error:
        checks.append(_check("record", False, f"record is malformed: {error}"))
        return {"ok": False, "checks": checks, "claim": claim}

    intact = expected == claim.get("digest")
    checks.append(_check(
        "record", intact,
        "place, time and document hash agree with the digest" if intact
        else f"record was altered: digest should be {expected}",
    ))

    # The drawing must be the sky of the recorded place and time.
    try:
        drawn = parse_drawing(svg)
        size = int(drawn.size)
        ring = drawn.document_ring
        fresh_svg = starhash(
            latitude, longitude, moment, elevation_m=elevation_m, size=size,
            document_digest=bytes.fromhex(ring) if ring else None,
        ).svg
        if _strip_claim(svg).strip() == fresh_svg.strip():
            sky_ok, detail = True, "drawing is exactly the sky of the recorded place and time"
        else:
            fresh = parse_drawing(fresh_svg)
            same = (
                len(drawn.pixels) == len(fresh.pixels)
                and sorted(drawn.bodies) == sorted(fresh.bodies)
                and all(
                    abs(a[0] - b[0]) <= 0.015 and abs(a[1] - b[1]) <= 0.015
                    for a, b in zip(drawn.pixels, fresh.pixels)
                )
            )
            sky_ok = same
            detail = (
                "every star and planet is where the recorded place and time put it"
                if same else "drawing does not show the sky of the recorded place and time"
            )
    except (SealReadError, ValueError) as error:
        sky_ok, detail = False, f"drawing could not be read: {error}"
    checks.append(_check("sky", sky_ok, detail))

    if ring is None:
        checks.append(_check("ring", None, "drawing has no document ring"))
    else:
        ring_ok = sha256.startswith(ring) and len(ring) >= 2 * RING_BYTES
        checks.append(_check(
            "ring", ring_ok,
            "tick ring carries the recorded document hash" if ring_ok
            else "tick ring does not carry the recorded document hash",
        ))

    if document is None:
        checks.append(_check("document", None, "no document given, so not compared"))
    else:
        actual = document_sha256(document)
        match = actual == sha256
        checks.append(_check(
            "document", match,
            "document is the one this seal was cast for" if match
            else "document differs from the one this seal was cast for",
        ))

    return {
        "ok": all(c["ok"] is not False for c in checks),
        "checks": checks,
        "claim": claim,
    }
