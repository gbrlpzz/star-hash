"""
star_hash.astrometry
~~~~~~~~~~~~~~~~~~~~
Topocentric reductions, diurnal parallax, atmospheric refraction,
and horizontal coordinate transformations.
"""
from __future__ import annotations

import math
from typing import Tuple, Dict, Any

from star_hash.ephemeris import (
    RAD,
    DEG,
    TWO_PI,
    normalize_rad,
    earth_rotation_angle,
    mean_obliquity,
)

def local_sidereal_time(jd_ut: float, lon_rad: float) -> float:
    """Computes Local Apparent Sidereal Time (LAST) at given observer longitude."""
    # Using IAU 2000 Earth Rotation Angle as precise sidereal proxy
    theta_era = earth_rotation_angle(jd_ut)
    return normalize_rad(theta_era + lon_rad)

def apply_topocentric_parallax(
    ra_rad: float,
    dec_rad: float,
    dist_km: float,
    lat_rad: float,
    elevation_m: float,
    last_rad: float,
) -> Tuple[float, float]:
    """
    Transforms geocentric equatorial coordinates to topocentric equatorial coordinates
    accounting for diurnal parallax on the WGS84 Earth ellipsoid.
    """
    # WGS84 parameters
    a = 6378.137  # Earth equatorial radius in km
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)

    # Geocentric observer position
    u = math.atan((b / a) * math.tan(lat_rad))
    rho_sin_phi = (b / a) * math.sin(u) + (elevation_m / 1000.0 / a) * math.sin(lat_rad)
    rho_cos_phi = math.cos(u) + (elevation_m / 1000.0 / a) * math.cos(lat_rad)

    # Local Hour Angle
    H = last_rad - ra_rad
    sin_pi = a / dist_km

    delta_ra = math.atan2(
        -rho_cos_phi * sin_pi * math.sin(H),
        math.cos(dec_rad) - rho_cos_phi * sin_pi * math.cos(H),
    )

    topocentric_ra = normalize_rad(ra_rad + delta_ra)
    topocentric_dec = math.atan2(
        (math.sin(dec_rad) - rho_sin_phi * sin_pi) * math.cos(delta_ra),
        math.cos(dec_rad) - rho_cos_phi * sin_pi * math.cos(H),
    )

    return topocentric_ra, topocentric_dec

def equatorial_to_horizontal(
    ra_rad: float,
    dec_rad: float,
    lat_rad: float,
    last_rad: float,
) -> Tuple[float, float]:
    """
    Converts equatorial coordinates (RA, Dec) to local horizontal coordinates
    (Altitude a, Azimuth A).
    Azimuth is measured North (0) -> East (pi/2) -> South (pi) -> West (3pi/2).
    """
    H = last_rad - ra_rad
    sin_alt = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(H)
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt_rad = math.asin(sin_alt)

    cos_az = (math.sin(dec_rad) - math.sin(lat_rad) * math.sin(alt_rad)) / (
        math.cos(lat_rad) * math.cos(alt_rad) + 1e-12
    )
    cos_az = max(-1.0, min(1.0, cos_az))
    az_rad = math.acos(cos_az)

    # If hour angle is west of meridian (sin(H) > 0), az is > 180 deg
    if math.sin(H) > 0:
        az_rad = TWO_PI - az_rad

    return alt_rad, az_rad

def atmospheric_refraction(alt_rad: float, pressure_mbar: float = 1013.25, temp_c: float = 15.0) -> float:
    """
    Computes atmospheric refraction using Bennett's formula.
    Returns the apparent altitude in radians.
    """
    alt_deg = alt_rad * DEG
    if alt_deg < -1.0:
        return alt_rad

    # Bennett's formula for apparent altitude
    # R (arcminutes) = 1 / tan(h + 7.31 / (h + 4.4))
    r_arcmin = 1.0 / math.tan((alt_deg + 7.31 / (alt_deg + 4.4)) * RAD)
    # Temperature and pressure correction
    r_arcmin *= (pressure_mbar / 1010.0) * (283.0 / (273.0 + temp_c))

    return alt_rad + (r_arcmin * (RAD / 60.0))
