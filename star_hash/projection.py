"""
star_hash.projection
~~~~~~~~~~~~~~~~~~~~~
Conformal zenith stereographic projection for celestial sky charting.
Preserves all local angular shapes and geometry.
"""
from __future__ import annotations

import math
from typing import Tuple, Dict, Any

from star_hash.ephemeris import RAD, DEG

def stereographic_project(alt_rad: float, az_rad: float) -> Tuple[float, float, float]:
    """
    Projects topocentric horizontal coordinates (alt, az) onto the conformal unit disc.

    Equations:
        Zenith distance z = pi/2 - altitude
        Projected radius r = tan(z / 2)  [r = 0 at Zenith, r = 1 at Horizon]
        x = r * sin(azimuth)             [East is +x]
        y = -r * cos(azimuth)            [North is +y, South is -y]

    Returns:
        (x, y, r) where horizon boundary is circle r = 1.0.
    """
    z = (math.pi / 2.0) - alt_rad
    # If altitude is below horizon, r > 1.0
    r = math.tan(z / 2.0)
    x = r * math.sin(az_rad)
    y = -r * math.cos(az_rad)
    return x, y, r

def stereographic_deproject(x: float, y: float) -> Tuple[float, float]:
    """
    Inverts stereographic (x, y) coordinates back to topocentric (altitude, azimuth).
    """
    r = math.hypot(x, y)
    z = 2.0 * math.atan(r)
    alt_rad = (math.pi / 2.0) - z
    az_rad = math.atan2(x, -y)
    if az_rad < 0:
        az_rad += 2.0 * math.pi
    return alt_rad, az_rad
