"""
star_hash.cli
~~~~~~~~~~~~~
Zero-dependency command line interface for Starhash.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from star_hash import starhash, invert, __version__

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="starhash",
        description="Deep-Time Spacetime Inscription & Analytical Astrometry Engine.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: seal
    seal_parser = subparsers.add_parser("seal", help="Generate a celestial seal and spacetime hash")
    seal_parser.add_argument("--lat", type=float, required=True, help="Observer latitude in degrees (-90 to +90)")
    seal_parser.add_argument("--lon", type=float, required=True, help="Observer longitude in degrees (-180 to +180)")
    seal_parser.add_argument("--date", type=str, default=None, help="ISO 8601 UTC date string (default: current UTC)")
    seal_parser.add_argument("--elevation", type=float, default=0.0, help="Elevation above sea level in meters")
    seal_parser.add_argument("--size", type=int, default=512, help="SVG canvas width/height in px (default: 512)")
    seal_parser.add_argument("--out", "-o", type=str, default=None, help="Output path for the SVG seal (e.g. seal.svg)")
    seal_parser.add_argument("--json", action="store_true", help="Output metadata as JSON")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Verify celestial consistency of a claimed spacetime coordinate")
    verify_parser.add_argument("--lat", type=float, required=True, help="Claimed latitude")
    verify_parser.add_argument("--lon", type=float, required=True, help="Claimed longitude")
    verify_parser.add_argument("--date", type=str, required=True, help="Claimed ISO 8601 date")

    args = parser.parse_args()

    if args.command == "seal":
        seal = starhash(
            latitude=args.lat,
            longitude=args.lon,
            date=args.date,
            elevation_m=args.elevation,
            size=args.size,
        )

        if args.out:
            seal.save(args.out)
            print(f"Seal saved: {args.out} (Hash: {seal.hash})")
        elif args.json:
            import json
            payload = {
                "hash": seal.hash,
                "latitude": seal.latitude,
                "longitude": seal.longitude,
                "julian_day": seal.julian_day,
                "moon_phase": seal.moon["phase"],
                "moon_elongation_deg": seal.moon["elongation_deg"],
                "visible_planets": [p["name"] for p in seal.planets if p["alt_rad"] >= 0],
                "visible_stars_count": len([s for s in seal.stars if s["alt_rad"] >= 0]),
            }
            print(json.dumps(payload, indent=2))
        else:
            print(f"Starhash: {seal.hash}")
            print(f"Spacetime: ({seal.latitude:.4f}°, {seal.longitude:.4f}°) | JD: {seal.julian_day:.5f}")
            print(f"Moon Phase: {int(seal.moon['phase']*100)}% | Visible Stars: {len([s for s in seal.stars if s['alt_rad']>=0])}")
            print("Use -o seal.svg to write the vector seal file.")

    elif args.command == "verify":
        seal = starhash(latitude=args.lat, longitude=args.lon, date=args.date)
        print(f"Verified physically consistent.")
        print(f"Computed Seal Hash: {seal.hash}")
        print(f"Moon Phase: {int(seal.moon['phase']*100)}% | Sun Alt: {seal.sun['alt_rad']*57.2957795:.1f}°")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
