"""
star_hash.ephemeris
~~~~~~~~~~~~~~~~~~~
Small, zero-dependency analytical celestial model.
Uses low-order secular planetary elements and selected terms from the
ELP-2000 lunar expansion, with an ERA rotation expression.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, Any

RAD = math.pi / 180.0
DEG = 180.0 / math.pi
TWO_PI = 2.0 * math.pi

def normalize_rad(angle: float) -> float:
    a = angle % TWO_PI
    return a if a >= 0.0 else a + TWO_PI

def normalize_deg(angle: float) -> float:
    a = angle % 360.0
    return a if a >= 0.0 else a + 360.0

def date_to_jd(year: int, month: int, day: float) -> float:
    """Convert calendar date to Julian Day Number."""
    if month <= 2:
        year -= 1
        month += 12
    a = math.floor(year / 100.0)
    b = 2.0 - a + math.floor(a / 4.0)
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5

def datetime_to_jd(dt: datetime) -> float:
    """Convert Python datetime (UTC) to Julian Day."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    day_fraction = dt.day + (dt.hour + (dt.minute + (dt.second + dt.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    return date_to_jd(dt.year, dt.month, day_fraction)

def jd_to_centuries(jd: float) -> float:
    """Julian centuries from J2000.0 epoch."""
    return (jd - 2451545.0) / 36525.0

def earth_rotation_angle(jd_ut: float) -> float:
    """IAU 2000 Earth Rotation Angle (ERA) in radians."""
    d = jd_ut - 2451545.0
    return normalize_rad(TWO_PI * (0.7790572732640 + 1.00273781191135448 * d))

def mean_obliquity(T: float) -> float:
    """IAU 2006 mean obliquity of the ecliptic in radians."""
    eps_arcsec = 84381.406 - 46.836769 * T - 0.0001831 * (T**2) + 0.00200340 * (T**3)
    return eps_arcsec * (RAD / 3600.0)

def solve_kepler(M_rad: float, e: float) -> float:
    """Solve Kepler equation M = E - e*sin(E) via Newton-Raphson."""
    E = M_rad + e * math.sin(M_rad)
    for _ in range(12):
        dE = (E - e * math.sin(E) - M_rad) / (1.0 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-9:
            break
    return E

# Planet elements [J2000_value, rate_per_century]
PLANET_DATA: Dict[str, Dict[str, Any]] = {
    "mercury": {
        "a": [0.38709893, 0.00000066],
        "e": [0.20563069, 0.00002527],
        "i": [7.00487, -0.005947],
        "node": [48.33167, -0.12542],
        "peri": [77.45645, 0.160477],
        "L": [252.25085, 149472.67411],
        "H": -0.42,
    },
    "venus": {
        "a": [0.72333199, 0.00000092],
        "e": [0.00677323, -0.00004938],
        "i": [3.39471, -0.000789],
        "node": [76.68069, -0.27769],
        "peri": [131.53298, 0.002683],
        "L": [181.97980, 58517.81539],
        "H": -4.40,
    },
    "mars": {
        "a": [1.52366231, -0.00007221],
        "e": [0.09341233, 0.00011902],
        "i": [1.85061, -0.000675],
        "node": [49.57854, -0.29498],
        "peri": [336.04084, 0.444411],
        "L": [355.45332, 19140.30268],
        "H": -1.52,
    },
    "jupiter": {
        "a": [5.20336301, 0.00060737],
        "e": [0.04839266, -0.00012880],
        "i": [1.30530, -0.004156],
        "node": [100.55615, 0.12105],
        "peri": [14.75385, 0.212527],
        "L": [34.40438, 3034.90567],
        "H": -9.40,
    },
    "saturn": {
        "a": [9.53707032, -0.00301530],
        "e": [0.05415060, -0.00036762],
        "i": [2.48446, 0.006936],
        "node": [113.71504, -0.15668],
        "peri": [92.43194, 0.541794],
        "L": [49.94432, 1222.49362],
        "H": -8.88,
    },
}

def earth_heliocentric(T: float) -> Dict[str, float]:
    """Heliocentric position of Earth (J2000 ecliptic)."""
    a = 1.00000261 + 0.00000562 * T
    e = 0.01671123 - 0.00004392 * T
    peri = (102.93768193 + 0.32327364 * T) * RAD
    L = normalize_deg(100.46457166 + 35999.37244981 * T) * RAD
    M = normalize_rad(L - peri)
    E = solve_kepler(M, e)

    sin_v = (math.sqrt(1.0 - e**2) * math.sin(E)) / (1.0 - e * math.cos(E))
    cos_v = (math.cos(E) - e) / (1.0 - e * math.cos(E))
    v = math.atan2(sin_v, cos_v)
    r = a * (1.0 - e * math.cos(E))
    u = v + peri

    return {
        "x": r * math.cos(u),
        "y": r * math.sin(u),
        "z": 0.0,
        "r": r,
    }

def sun_geocentric(T: float) -> Dict[str, Any]:
    """Geocentric equatorial position of the Sun."""
    earth = earth_heliocentric(T)
    # Geocentric sun is -earth
    gx = -earth["x"]
    gy = -earth["y"]
    gz = 0.0
    r_au = earth["r"]

    eps = mean_obliquity(T)
    x_eq = gx
    y_eq = gy * math.cos(eps) - gz * math.sin(eps)
    z_eq = gy * math.sin(eps) + gz * math.cos(eps)

    ra = normalize_rad(math.atan2(y_eq, x_eq))
    dec = math.asin(z_eq / r_au)

    return {
        "name": "Sun",
        "ra_rad": ra,
        "dec_rad": dec,
        "dist_au": r_au,
        "dist_km": r_au * 149597870.7,
        "mag": -26.74,
    }

def planet_geocentric(name: str, T: float) -> Dict[str, Any]:
    """Geocentric equatorial coordinates of a major planet."""
    el = PLANET_DATA[name.lower()]
    a = el["a"][0] + el["a"][1] * T
    e = el["e"][0] + el["e"][1] * T
    i = (el["i"][0] + el["i"][1] * T) * RAD
    node = (el["node"][0] + el["node"][1] * T) * RAD
    peri = (el["peri"][0] + el["peri"][1] * T) * RAD
    L = normalize_deg(el["L"][0] + el["L"][1] * T) * RAD
    M = normalize_rad(L - peri)
    E = solve_kepler(M, e)

    sin_v = (math.sqrt(1.0 - e**2) * math.sin(E)) / (1.0 - e * math.cos(E))
    cos_v = (math.cos(E) - e) / (1.0 - e * math.cos(E))
    v = math.atan2(sin_v, cos_v)
    r = a * (1.0 - e * math.cos(E))
    u = v + peri - node

    # Heliocentric ecliptic
    px = r * (math.cos(node) * math.cos(u) - math.sin(node) * math.sin(u) * math.cos(i))
    py = r * (math.sin(node) * math.cos(u) + math.cos(node) * math.sin(u) * math.cos(i))
    pz = r * (math.sin(u) * math.sin(i))

    earth = earth_heliocentric(T)
    dx = px - earth["x"]
    dy = py - earth["y"]
    dz = pz - earth["z"]
    delta_au = math.sqrt(dx**2 + dy**2 + dz**2)

    eps = mean_obliquity(T)
    gx = dx
    gy = dy * math.cos(eps) - dz * math.sin(eps)
    gz = dy * math.sin(eps) + dz * math.cos(eps)

    ra = normalize_rad(math.atan2(gy, gx))
    dec = math.asin(gz / delta_au)

    # Visual magnitude model
    H = el["H"]
    cos_beta = (r**2 + delta_au**2 - earth["r"]**2) / (2.0 * r * delta_au)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta_deg = math.acos(cos_beta) * DEG

    mag = H + 5.0 * math.log10(r * delta_au)
    n = name.lower()
    if n == "venus":
        mag += 0.009 * (beta_deg / 100.0) + 0.239 * (beta_deg / 100.0)**2
    elif n == "mars":
        mag += 0.016 * beta_deg
    elif n == "jupiter":
        mag += 0.005 * beta_deg
    elif n == "saturn":
        mag += 0.044 * beta_deg
    elif n == "mercury":
        mag += 0.038 * beta_deg

    return {
        "name": name.capitalize(),
        "ra_rad": ra,
        "dec_rad": dec,
        "dist_km": delta_au * 149597870.7,
        "mag": mag,
    }

def moon_geocentric(T: float) -> Dict[str, Any]:
    """Evaluate a selected-term lunar expansion based on ELP-2000."""
    L_prime = normalize_deg(218.3164477 + 481267.8812854 * T - 0.0015786 * T**2 + T**3 / 538841.0)
    D = normalize_deg(297.8501921 + 445267.1114034 * T - 0.0018819 * T**2 + T**3 / 545868.0)
    M = normalize_deg(357.5291092 + 35999.0502909 * T - 0.0001536 * T**2 + T**3 / 24490000.0)
    M_prime = normalize_deg(134.9633964 + 477198.8675055 * T + 0.0087414 * T**2 + T**3 / 69699.0)
    F = normalize_deg(93.2720950 + 483202.0175233 * T - 0.0036539 * T**2 - T**3 / 3526000.0)
    A1 = normalize_deg(119.75 + 131.849 * T)
    A2 = normalize_deg(53.09 + 479264.290 * T)
    A3 = normalize_deg(313.45 + 481266.484 * T)
    E = 1.0 - 0.002516 * T - 0.0000074 * T**2
    E2 = E * E

    D_r = D * RAD
    M_r = M * RAD
    Mp_r = M_prime * RAD
    F_r = F * RAD

    # Longitude terms (micro-degrees)
    Sl = (
        6288774 * math.sin(Mp_r)
        + 1274027 * math.sin(2 * D_r - Mp_r)
        + 658314 * math.sin(2 * D_r)
        + 213618 * math.sin(2 * Mp_r)
        - 185116 * E * math.sin(M_r)
        - 114332 * math.sin(2 * F_r)
        + 58793 * math.sin(2 * D_r - 2 * Mp_r)
        + 57066 * E * math.sin(2 * D_r - M_r - Mp_r)
        + 53322 * math.sin(2 * D_r + Mp_r)
        + 45758 * E * math.sin(2 * D_r - M_r)
        - 40923 * E * math.sin(M_r - Mp_r)
        - 34720 * math.sin(D_r)
        - 30383 * E * math.sin(M_r + Mp_r)
        + 15327 * math.sin(2 * D_r - 2 * F_r)
        - 12528 * math.sin(Mp_r + 2 * F_r)
        + 10980 * math.sin(Mp_r - 2 * F_r)
        + 10675 * math.sin(4 * D_r - Mp_r)
        + 10034 * math.sin(3 * Mp_r)
        + 8548 * math.sin(4 * D_r - 2 * Mp_r)
        - 7888 * E * math.sin(2 * D_r - M_r + Mp_r)
        - 6766 * E * math.sin(2 * D_r + M_r - Mp_r)
        - 5163 * math.sin(D_r - Mp_r)
        + 4987 * E * math.sin(D_r + M_r)
        + 4036 * E * math.sin(2 * D_r - M_r - 2 * Mp_r)
        + 3994 * math.sin(2 * D_r + 2 * Mp_r)
        + 3861 * math.sin(4 * D_r)
        + 3665 * math.sin(2 * D_r - 3 * Mp_r)
        - 2689 * math.sin(D_r + Mp_r)
        - 2602 * math.sin(Mp_r - 2 * D_r + 2 * F_r)
        + 2390 * math.sin(2 * D_r - Mp_r - 2 * F_r)
        - 2348 * math.sin(D_r + 2 * F_r)
        + 2236 * E2 * math.sin(2 * D_r - 2 * M_r)
        - 2120 * math.sin(2 * Mp_r + 2 * F_r)
        - 1440 * E * math.sin(M_r + 2 * F_r)
        - 1398 * math.sin(2 * D_r - Mp_r + 2 * F_r)
        - 1249 * math.sin(D_r - 2 * F_r)
        + 1235 * math.sin(2 * D_r - 2 * Mp_r - 2 * F_r)
        + 1207 * math.sin(3 * D_r - Mp_r)
        + 1107 * math.sin(2 * D_r + 2 * F_r)
        + 3958 * math.sin(A1 * RAD)
        + 1962 * math.sin((L_prime - F) * RAD)
        + 318 * math.sin(A2 * RAD)
    )

    # Latitude terms (micro-degrees)
    Sb = (
        5128122 * math.sin(F_r)
        + 280602 * math.sin(Mp_r + F_r)
        + 277693 * math.sin(Mp_r - F_r)
        + 173237 * math.sin(2 * D_r - F_r)
        + 55413 * math.sin(2 * D_r - Mp_r + F_r)
        + 46271 * math.sin(2 * D_r - Mp_r - F_r)
        + 32573 * math.sin(2 * D_r + F_r)
        + 17198 * math.sin(2 * Mp_r + F_r)
        + 9266 * math.sin(2 * D_r + Mp_r - F_r)
        + 8822 * math.sin(2 * Mp_r - F_r)
        + 4099 * E * math.sin(2 * D_r - M_r - F_r)
        - 3087 * E * math.sin(2 * D_r - M_r + F_r)
        + 2235 * math.sin(2 * D_r + Mp_r + F_r)
        - 1803 * math.sin(D_r - F_r)
        - 1750 * math.sin(3 * F_r)
        - 1491 * E * math.sin(M_r - Mp_r + F_r)
        - 2235 * math.sin(L_prime * RAD)
        + 382 * math.sin(A3 * RAD)
        + 175 * math.sin((A1 - F) * RAD)
        + 175 * math.sin((A1 + F) * RAD)
    )

    # Distance terms in 0.001 km, as used by the tabulated expansion
    Sr = (
        -20905355 * math.cos(Mp_r)
        - 3699111 * math.cos(2 * D_r - Mp_r)
        - 2955968 * math.cos(2 * D_r)
        - 569925 * math.cos(2 * Mp_r)
        + 48888 * E * math.cos(M_r)
        - 3149 * math.cos(2 * F_r)
        + 246158 * math.cos(2 * D_r - 2 * Mp_r)
        - 152138 * math.cos(2 * D_r - Mp_r - M_r)
        - 170733 * math.cos(2 * D_r + Mp_r)
        - 204586 * E * math.cos(2 * D_r - M_r)
        - 129620 * math.cos(Mp_r - M_r)
        + 108743 * math.cos(D_r)
        + 104755 * math.cos(Mp_r + M_r)
        + 10321 * math.cos(2 * D_r - 2 * F_r)
    )

    lon_rad = normalize_deg(L_prime + Sl * 1e-6) * RAD
    lat_rad = (Sb * 1e-6) * RAD
    dist_km = 385000.56 + (Sr * 1e-3)

    eps = mean_obliquity(T)
    cos_lat = math.cos(lat_rad)
    sin_lat = math.sin(lat_rad)
    sin_lon = math.sin(lon_rad)
    cos_lon = math.cos(lon_rad)
    sin_eps = math.sin(eps)
    cos_eps = math.cos(eps)

    x = cos_lat * cos_lon
    y = cos_lat * sin_lon * cos_eps - sin_lat * sin_eps
    z = cos_lat * sin_lon * sin_eps + sin_lat * cos_eps

    ra = normalize_rad(math.atan2(y, x))
    dec = math.asin(z)

    # Moon phase & crescent orientation
    sun = sun_geocentric(T)
    cos_elong = math.sin(sun["dec_rad"]) * math.sin(dec) + math.cos(sun["dec_rad"]) * math.cos(dec) * math.cos(ra - sun["ra_rad"])
    cos_elong = max(-1.0, min(1.0, cos_elong))
    elongation = math.acos(cos_elong)

    R_sun_km = sun["dist_au"] * 149597870.7
    inc = math.atan2(R_sun_km * math.sin(elongation), dist_km - R_sun_km * math.cos(elongation))
    k = (1.0 + math.cos(inc)) / 2.0  # Phase fraction 0..1

    # Position angle of bright limb (chi)
    chi = math.atan2(
        math.cos(sun["dec_rad"]) * math.sin(sun["ra_rad"] - ra),
        math.sin(sun["dec_rad"]) * math.cos(dec) - math.cos(sun["dec_rad"]) * math.sin(dec) * math.cos(sun["ra_rad"] - ra)
    )

    return {
        "name": "Moon",
        "ra_rad": ra,
        "dec_rad": dec,
        "dist_km": dist_km,
        "phase": k,
        "elongation_deg": elongation * DEG,
        "limb_angle_rad": chi,
        "mag": -12.74 + 2.5 * math.log10(max(1e-4, 1.0 - k + 0.05)),
    }
