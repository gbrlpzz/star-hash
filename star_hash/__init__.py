"""
starhash
~~~~~~~~
Compact analytical celestial model and label-free SVG seal.
Zero runtime dependencies.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

from star_hash.ephemeris import (
    RAD,
    date_to_jd,
    datetime_to_jd,
    jd_to_centuries,
    sun_geocentric,
    planet_geocentric,
    moon_geocentric,
)
from star_hash.stars import load_stars_for_epoch
from star_hash.astrometry import (
    local_sidereal_time,
    apply_topocentric_parallax,
    equatorial_to_horizontal,
    atmospheric_refraction,
)
from star_hash.projection import stereographic_project
from star_hash.render import generate_svg_seal
from star_hash.invert import solve_spacetime, evaluate_forward_model
from star_hash.read import Reading, SealReadError, read_seal
from star_hash.seal import SignedSeal, read_claim, sign, verify

__version__ = "1.1.0"

# Base58 alphabet for the compact digest
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def encode_base58(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    chars = []
    while num > 0:
        num, rem = divmod(num, 58)
        chars.append(BASE58_ALPHABET[rem])
    return "".join(reversed(chars)) or "1"

@dataclass
class CelestialSeal:
    hash: str
    svg: str
    latitude: float
    longitude: float
    elevation_m: float
    julian_day: float
    stars: List[Dict[str, Any]]
    planets: List[Dict[str, Any]]
    moon: Dict[str, Any]
    sun: Dict[str, Any]
    points: Dict[str, Tuple[float, float]]

    def save(self, path: str) -> None:
        """Save the vector seal to an SVG file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.svg)

def starhash(
    latitude: float,
    longitude: float,
    date: datetime | str | float | None = None,
    elevation_m: float = 0.0,
    size: int = 512,
    horizon_cutoff: bool = True,
    apply_refraction: bool = True,
    document_digest: bytes | None = None,
) -> CelestialSeal:
    """
    Compute a deterministic local sky view and its compact digest.

    Parameters:
        latitude: Observer latitude in degrees [-90..+90].
        longitude: Observer longitude in degrees [-180..+180].
        date: Datetime object, ISO 8601 string, Julian Day number (float), or None (current UTC).
        elevation_m: Height above sea level in meters.
        size: Width and height of the rendered SVG seal in pixels.
        horizon_cutoff: Omit bodies below the horizon from the SVG and points.
        apply_refraction: Apply Bennett atmospheric refraction to altitudes.
        document_digest: Bytes to draw as a ring of ticks around the horizon
            (see :func:`star_hash.sign`); None draws the bare sky.
    """
    if not math.isfinite(latitude) or not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be a finite value in [-90, 90] degrees")
    if not math.isfinite(longitude) or not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must be a finite value in [-180, 180] degrees")
    if not math.isfinite(elevation_m):
        raise ValueError("elevation_m must be finite")
    if not isinstance(size, int) or isinstance(size, bool) or size < 32:
        raise ValueError("size must be an integer of at least 32 pixels")

    # 1. Parse Date to Julian Day Number
    if date is None:
        dt = datetime.now(timezone.utc)
        jd = datetime_to_jd(dt)
    elif isinstance(date, str):
        # Support ISO 8601 strings
        iso = date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        jd = datetime_to_jd(dt)
    elif isinstance(date, datetime):
        jd = datetime_to_jd(date)
    elif isinstance(date, (int, float)):
        jd = float(date)
    else:
        raise ValueError(f"Unsupported date format: {type(date)}")
    if not math.isfinite(jd):
        raise ValueError("date must resolve to a finite Julian day")

    T = jd_to_centuries(jd)
    lat_rad = latitude * RAD
    lon_rad = longitude * RAD
    last_rad = local_sidereal_time(jd, lon_rad)

    # 2. Ephemeris Reductions
    sun = sun_geocentric(T)
    sun_alt, sun_az = equatorial_to_horizontal(sun["ra_rad"], sun["dec_rad"], lat_rad, last_rad)
    if apply_refraction:
        sun_alt = atmospheric_refraction(sun_alt)
    sun["alt_rad"] = sun_alt
    sun["az_rad"] = sun_az
    # Moon (with topocentric parallax)
    moon = moon_geocentric(T)
    top_moon_ra, top_moon_dec = apply_topocentric_parallax(
        moon["ra_rad"], moon["dec_rad"], moon["dist_km"], lat_rad, elevation_m, last_rad
    )
    moon_alt, moon_az = equatorial_to_horizontal(top_moon_ra, top_moon_dec, lat_rad, last_rad)
    if apply_refraction:
        moon_alt = atmospheric_refraction(moon_alt)
    moon["alt_rad"] = moon_alt
    moon["az_rad"] = moon_az
    moon_x, moon_y, _ = stereographic_project(moon_alt, moon_az)

    # Major Planets
    planets: List[Dict[str, Any]] = []
    points: Dict[str, Tuple[float, float]] = {}
    if not horizon_cutoff or moon_alt >= -0.01:
        points["Moon"] = (moon_x, moon_y)

    for p_name in ["mercury", "venus", "mars", "jupiter", "saturn"]:
        p = planet_geocentric(p_name, T)
        top_p_ra, top_p_dec = apply_topocentric_parallax(
            p["ra_rad"], p["dec_rad"], p["dist_km"], lat_rad, elevation_m, last_rad
        )
        p_alt, p_az = equatorial_to_horizontal(top_p_ra, top_p_dec, lat_rad, last_rad)
        if apply_refraction:
            p_alt = atmospheric_refraction(p_alt)
        p["alt_rad"] = p_alt
        p["az_rad"] = p_az
        px, py, _ = stereographic_project(p_alt, p_az)
        planets.append(p)
        if not horizon_cutoff or p_alt >= -0.01:
            points[p["name"]] = (px, py)

    # Stars (Precession + Proper Motion)
    stars: List[Dict[str, Any]] = []
    for s in load_stars_for_epoch(T):
        s_alt, s_az = equatorial_to_horizontal(s["ra_rad"], s["dec_rad"], lat_rad, last_rad)
        if apply_refraction:
            s_alt = atmospheric_refraction(s_alt)
        s["alt_rad"] = s_alt
        s["az_rad"] = s_az
        sx, sy, _ = stereographic_project(s_alt, s_az)
        stars.append(s)
        if not horizon_cutoff or s_alt >= -0.01:
            points[s["name"]] = (sx, sy)

    # 3. Deterministic compact digest
    # Hash raw physical configuration (independent of string formatting)
    hash_payload = bytearray()
    hash_payload.extend(f"{latitude:.5f}:{longitude:.5f}:{jd:.6f}".encode("utf-8"))
    hash_payload.extend(f":moon:{moon_alt:.5f}:{moon_az:.5f}:{moon['phase']:.4f}".encode("utf-8"))
    raw_digest = hashlib.blake2b(hash_payload, digest_size=8).digest()
    b58_token = encode_base58(raw_digest)
    seal_hash = f"STARS-{b58_token[:4]}-{b58_token[4:8]}-{b58_token[8:]}".rstrip("-")

    # 4. Generate Vector Seal SVG
    svg_string = generate_svg_seal(
        stars=stars,
        planets=planets,
        moon=moon,
        sun=sun,
        last_rad=last_rad,
        lat_rad=lat_rad,
        size=size,
        horizon_cutoff=horizon_cutoff,
        document_digest=document_digest,
    )

    return CelestialSeal(
        hash=seal_hash,
        svg=svg_string,
        latitude=latitude,
        longitude=longitude,
        elevation_m=elevation_m,
        julian_day=jd,
        stars=stars,
        planets=planets,
        moon=moon,
        sun=sun,
        points=points,
    )

def invert(
    points: Dict[str, Tuple[float, float]],
    initial_guess: Tuple[float, float, float] | None = None,
    max_iterations: int = 50,
    elevation_m: float = 0.0,
    apply_refraction: bool = True,
) -> Dict[str, Any]:
    """Fit a labeled set of projected points to latitude, longitude, and time.

    This is an experimental local fit. It does not decode an unlabeled SVG.
    """
    return solve_spacetime(
        points,
        initial_guess=initial_guess,
        max_iterations=max_iterations,
        elevation_m=elevation_m,
        apply_refraction=apply_refraction,
    )
