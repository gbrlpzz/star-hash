"""
star_hash.invert
~~~~~~~~~~~~~~~~
Non-linear least-squares inverse spacetime solver.
Given the relative projected celestial coordinates of visible bodies,
reconstructs the observer's physical coordinates: (latitude, longitude, timestamp).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Any

from star_hash.ephemeris import (
    RAD,
    DEG,
    TWO_PI,
    normalize_rad,
    normalize_deg,
    date_to_jd,
    jd_to_centuries,
    earth_rotation_angle,
    planet_geocentric,
    moon_geocentric,
)
from star_hash.stars import load_stars_for_epoch
from star_hash.astrometry import (
    local_sidereal_time,
    apply_topocentric_parallax,
    equatorial_to_horizontal,
)
from star_hash.projection import stereographic_project, stereographic_deproject

def evaluate_forward_model(
    lat_deg: float,
    lon_deg: float,
    jd_ut: float,
    body_names: List[str],
) -> Dict[str, Tuple[float, float]]:
    """
    Computes projected (x, y) coordinates for a set of celestial body names
    at candidate observer state (lat, lon, jd).
    """
    T = jd_to_centuries(jd_ut)
    lat_rad = lat_deg * RAD
    lon_rad = lon_deg * RAD
    last_rad = local_sidereal_time(jd_ut, lon_rad)

    # 1. Stars
    all_stars = {s["name"]: s for s in load_stars_for_epoch(T)}
    # 2. Moon
    moon_data = moon_geocentric(T)
    top_moon_ra, top_moon_dec = apply_topocentric_parallax(
        moon_data["ra_rad"],
        moon_data["dec_rad"],
        moon_data["dist_km"],
        lat_rad,
        0.0,
        last_rad,
    )
    moon_alt, moon_az = equatorial_to_horizontal(top_moon_ra, top_moon_dec, lat_rad, last_rad)
    mx, my, _ = stereographic_project(moon_alt, moon_az)

    # 3. Planets
    planets_data = {}
    for p in ["mercury", "venus", "mars", "jupiter", "saturn"]:
        pd = planet_geocentric(p, T)
        p_alt, p_az = equatorial_to_horizontal(pd["ra_rad"], pd["dec_rad"], lat_rad, last_rad)
        px, py, _ = stereographic_project(p_alt, p_az)
        planets_data[pd["name"]] = (px, py)

    coords: Dict[str, Tuple[float, float]] = {}
    for name in body_names:
        if name == "Moon":
            coords["Moon"] = (mx, my)
        elif name in planets_data:
            coords[name] = planets_data[name]
        elif name in all_stars:
            st = all_stars[name]
            st_alt, st_az = equatorial_to_horizontal(st["ra_rad"], st["dec_rad"], lat_rad, last_rad)
            sx, sy, _ = stereographic_project(st_alt, st_az)
            coords[name] = (sx, sy)

    return coords

def solve_spacetime(
    observed_points: Dict[str, Tuple[float, float]],
    initial_guess: Tuple[float, float, float] | None = None,
    max_iterations: int = 50,
) -> Dict[str, Any]:
    """
    Invert observed celestial projections back to (latitude, longitude, Julian Day).

    Arguments:
        observed_points: Dict mapping body names to observed (x, y) projected coordinates.
        initial_guess: Optional starting (lat_deg, lon_deg, jd_ut).

    Returns:
        Dict with estimated latitude, longitude, Julian Day, and residual error.
    """
    body_names = list(observed_points.keys())
    if len(body_names) < 3:
        raise ValueError("At least 3 celestial reference points are required for non-degenerate spacetime inversion.")

    # Default initial guess: Equator, Prime Meridian, J2000.0 epoch
    lat, lon, jd = initial_guess if initial_guess is not None else (0.0, 0.0, 2451545.0)

    # Finite difference step sizes
    h_lat = 0.01   # deg
    h_lon = 0.01   # deg
    h_jd  = 0.0001 # days (~8.6 sec)

    damping = 1e-3

    for iteration in range(max_iterations):
        # 1. Evaluate forward model at current state
        pred = evaluate_forward_model(lat, lon, jd, body_names)

        # 2. Compute residual vector
        residuals = []
        for name in body_names:
            if name in pred:
                px, py = pred[name]
                ox, oy = observed_points[name]
                residuals.append(px - ox)
                residuals.append(py - oy)

        cost = sum(r**2 for r in residuals)
        if cost < 1e-8:
            break

        # 3. Finite difference Jacobian
        pred_dlat = evaluate_forward_model(lat + h_lat, lon, jd, body_names)
        pred_dlon = evaluate_forward_model(lat, lon + h_lon, jd, body_names)
        pred_djd  = evaluate_forward_model(lat, lon, jd + h_jd,  body_names)

        # J has shape (2N, 3)
        # J^T J has shape (3, 3)
        # J^T r has shape (3,)
        jt_j = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        jt_r = [0.0, 0.0, 0.0]

        row_idx = 0
        for name in body_names:
            if name in pred:
                j_row_x = [
                    (pred_dlat[name][0] - pred[name][0]) / h_lat,
                    (pred_dlon[name][0] - pred[name][0]) / h_lon,
                    (pred_djd[name][0] - pred[name][0]) / h_jd,
                ]
                j_row_y = [
                    (pred_dlat[name][1] - pred[name][1]) / h_lat,
                    (pred_dlon[name][1] - pred[name][1]) / h_lon,
                    (pred_djd[name][1] - pred[name][1]) / h_jd,
                ]

                rx = residuals[row_idx]
                ry = residuals[row_idx + 1]
                row_idx += 2

                for i in range(3):
                    jt_r[i] += j_row_x[i] * rx + j_row_y[i] * ry
                    for j in range(3):
                        jt_j[i][j] += j_row_x[i] * j_row_x[j] + j_row_y[i] * j_row_y[j]

        # Add Levenberg-Marquardt damping
        for i in range(3):
            jt_j[i][i] += damping * (jt_j[i][i] + 1.0)

        # Invert 3x3 matrix (jt_j) * delta = -jt_r
        try:
            # Determinant of 3x3
            m = jt_j
            det = (
                m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
            )
            if abs(det) < 1e-12:
                damping *= 10.0
                continue

            inv_det = 1.0 / det
            inv = [
                [
                    (m[1][1] * m[2][2] - m[1][2] * m[2][1]) * inv_det,
                    (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * inv_det,
                    (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * inv_det,
                ],
                [
                    (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * inv_det,
                    (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * inv_det,
                    (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * inv_det,
                ],
                [
                    (m[1][0] * m[2][1] - m[1][1] * m[2][0]) * inv_det,
                    (m[0][1] * m[2][0] - m[0][0] * m[2][1]) * inv_det,
                    (m[0][0] * m[1][1] - m[0][1] * m[1][0]) * inv_det,
                ],
            ]

            delta_lat = -(inv[0][0] * jt_r[0] + inv[0][1] * jt_r[1] + inv[0][2] * jt_r[2])
            delta_lon = -(inv[1][0] * jt_r[0] + inv[1][1] * jt_r[1] + inv[1][2] * jt_r[2])
            delta_jd  = -(inv[2][0] * jt_r[0] + inv[2][1] * jt_r[1] + inv[2][2] * jt_r[2])

            lat += delta_lat
            lon = (lon + delta_lon) % 360.0
            if lon > 180.0:
                lon -= 360.0
            jd += delta_jd

            lat = max(-90.0, min(90.0, lat))

        except Exception:
            damping *= 10.0

    return {
        "latitude_deg": lat,
        "longitude_deg": lon,
        "julian_day": jd,
        "cost": cost,
        "iterations": iteration + 1,
    }
