"""
star_hash.cli
~~~~~~~~~~~~~
Command line interface for Starhash.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from star_hash import __version__, starhash
from star_hash.read import SealReadError, read_seal
from star_hash.seal import ring_matches, sign, verify


def _env_float(name: str) -> Optional[float]:
    value = os.environ.get(name)
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        raise SystemExit(f"starhash: {name}={value!r} is not a number")


def _add_place(parser: argparse.ArgumentParser) -> None:
    lat, lon = _env_float("STARHASH_LAT"), _env_float("STARHASH_LON")
    parser.add_argument("--lat", type=float, default=lat, required=lat is None,
                        help="latitude in degrees, north positive (or set STARHASH_LAT)")
    parser.add_argument("--lon", type=float, default=lon, required=lon is None,
                        help="longitude in degrees, east positive (or set STARHASH_LON)")
    parser.add_argument("--elevation", type=float, default=_env_float("STARHASH_ELEVATION") or 0.0,
                        help="height above sea level in metres (default 0)")
    parser.add_argument("--date", default=None,
                        help="ISO 8601 time, UTC unless an offset is given (default: now)")
    parser.add_argument("--size", type=int, default=512, help="SVG width and height in px (default 512)")


def _place(lat: float, lon: float) -> str:
    return f"{abs(lat):.5f}°{'N' if lat >= 0 else 'S'} {abs(lon):.5f}°{'E' if lon >= 0 else 'W'}"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _cmd_sign(args: argparse.Namespace) -> int:
    seal = sign(args.document, args.lat, args.lon, date=args.date,
                elevation_m=args.elevation, size=args.size)
    out = args.out or args.document + ".seal.svg"
    seal.save(out)
    if args.json:
        print(json.dumps({"seal": out, **seal.claim}, indent=2, ensure_ascii=False))
    else:
        claim = seal.claim
        print(f"Sealed  {args.document}")
        print(f"  at    {_place(claim['latitude'], claim['longitude'])}, {claim['elevation_m']:.0f} m")
        print(f"  on    {claim['time']}")
        print(f"  seal  {out}")
        print(f"  id    {seal.digest}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    stated = [args.lat, args.lon, args.date]
    if any(v is not None for v in stated) and any(v is None for v in stated):
        raise ValueError("to check an exact claim give all of --lat, --lon and --date")
    result = verify(
        _read_text(args.seal), args.document,
        latitude=args.lat, longitude=args.lon, date=args.date, elevation_m=args.elevation,
        year_from=args.year_from, year_to=args.year_to,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    reading = result["reading"]
    if reading and reading["longitude"] is not None:
        print(f"Seal shows {_place(reading['latitude'], reading['longitude'])} on {reading['time']}")
        if reading["sigma_time_s"] is not None:
            print(f"  ±    {reading['sigma_latitude_deg']:.5f}° lat, "
                  f"{reading['sigma_longitude_deg']:.3f}° lon, {reading['sigma_time_s']:.0f} s")
    for other in (reading or {}).get("alternatives", []):
        print(f"  or   {other[:10]} fits the drawing equally well")
    marks = {True: "pass", False: "FAIL", None: "skip"}
    for check in result["checks"]:
        print(f"  [{marks[check['ok']]}] {check['detail']}")
    if result["ok"]:
        print("Consistent. This confirms what the seal shows, not that it is true.")
    else:
        print("NOT VALID.")
    return 0 if result["ok"] else 1


def _cmd_read(args: argparse.Namespace) -> int:
    reading = read_seal(_read_text(args.seal), year_from=args.year_from, year_to=args.year_to)
    match = ring_matches(reading.document_ring, args.document) if args.document else None
    status = 1 if args.document and not match else 0
    if args.json:
        record = reading.as_dict()
        if args.document:
            record["document_matches"] = bool(match)
        print(json.dumps(record, indent=2))
        return status
    print(f"Read from the drawing alone ({reading.stars_matched} of {reading.stars_drawn} stars identified)")
    if reading.time is None or reading.longitude is None:
        print(f"  latitude       {reading.latitude:+.3f}°")
        print(f"  sidereal time  {reading.sidereal_time_deg / 15.0:.3f} h")
    else:
        print(f"  place  {_place(reading.latitude, reading.longitude)}")
        print(f"  time   {reading.time}")
        if reading.sigma_time_s is not None:
            print(f"  ±      {reading.sigma_latitude_deg:.5f}° lat, "
                  f"{reading.sigma_longitude_deg:.3f}° lon, {reading.sigma_time_s:.0f} s")
        print(f"  from   {', '.join(reading.bodies)}")
        for other in reading.alternatives:
            print(f"  or     {other[:10]} fits the drawing equally well")
        if not reading.converged:
            print("  warning: the fit did not converge; treat this reading with care")
    if reading.note:
        print(f"  note   {reading.note}")
    if reading.document_ring:
        print(f"  ring   sha256 {reading.document_ring}…")
    if args.document:
        if reading.document_ring is None:
            print("  [FAIL] the drawing has no document ring to compare with")
        elif match:
            print(f"  [pass] {args.document} is the document in the ring")
        else:
            print(f"  [FAIL] {args.document} is not the document in the ring")
    return status


def _cmd_seal(args: argparse.Namespace) -> int:
    seal = starhash(latitude=args.lat, longitude=args.lon, date=args.date,
                    elevation_m=args.elevation, size=args.size)
    visible_stars = len([s for s in seal.stars if s["alt_rad"] >= 0])
    if args.out:
        seal.save(args.out)
        print(f"Seal saved: {args.out} (Hash: {seal.hash})")
    elif args.json:
        print(json.dumps({
            "hash": seal.hash,
            "latitude": seal.latitude,
            "longitude": seal.longitude,
            "julian_day": seal.julian_day,
            "moon_phase": seal.moon["phase"],
            "moon_elongation_deg": seal.moon["elongation_deg"],
            "visible_planets": [p["name"] for p in seal.planets if p["alt_rad"] >= 0],
            "visible_stars_count": visible_stars,
        }, indent=2))
    else:
        print(f"Starhash: {seal.hash}")
        print(f"Spacetime: ({seal.latitude:.4f}°, {seal.longitude:.4f}°) | JD: {seal.julian_day:.5f}")
        print(f"Moon Phase: {int(seal.moon['phase'] * 100)}% | Visible Stars: {visible_stars}")
        print("Use -o seal.svg to write the vector seal file.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starhash",
        description="Seal a document with the sky of a place and time, and read seals back.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")

    p = commands.add_parser("sign", help="cast a seal for a document")
    p.add_argument("document", help="file to seal")
    _add_place(p)
    p.add_argument("--out", "-o", default=None, help="where to write the seal (default: DOCUMENT.seal.svg)")
    p.add_argument("--json", action="store_true", help="print the seal's record as JSON")
    p.set_defaults(run=_cmd_sign)

    p = commands.add_parser("verify", help="check a seal, and the document it was cast for")
    p.add_argument("seal", help="seal SVG written by `starhash sign`")
    p.add_argument("document", nargs="?", default=None, help="the document to compare with the tick ring (optional)")
    p.add_argument("--lat", type=float, default=None, help="stated latitude, to check the exact claim")
    p.add_argument("--lon", type=float, default=None, help="stated longitude")
    p.add_argument("--date", default=None, help="stated ISO 8601 time")
    p.add_argument("--elevation", type=float, default=0.0, help="stated height in metres (default 0)")
    p.add_argument("--from", dest="year_from", type=int, default=1800, help="earliest year to consider (default 1800)")
    p.add_argument("--to", dest="year_to", type=int, default=2200, help="latest year to consider (default 2200)")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(run=_cmd_verify)

    p = commands.add_parser("read", help="recover place and time from a seal's drawing alone")
    p.add_argument("seal", help="any Starhash seal SVG")
    p.add_argument("document", nargs="?", default=None, help="a document to compare with the tick ring (optional)")
    p.add_argument("--from", dest="year_from", type=int, default=1800, help="earliest year to consider (default 1800)")
    p.add_argument("--to", dest="year_to", type=int, default=2200, help="latest year to consider (default 2200)")
    p.add_argument("--json", action="store_true", help="print the reading as JSON")
    p.set_defaults(run=_cmd_read)

    p = commands.add_parser("seal", help="draw the sky of a place and time, with no document")
    _add_place(p)
    p.add_argument("--out", "-o", default=None, help="output path for the SVG")
    p.add_argument("--json", action="store_true", help="print a summary as JSON")
    p.set_defaults(run=_cmd_seal)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        return args.run(args)
    except (OSError, ValueError, SealReadError) as error:
        print(f"starhash: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
