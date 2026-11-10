"""Experimental inverse model for Starhash projected observations."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from star_hash.astrometry import (
    apply_topocentric_parallax,
    atmospheric_refraction,
    equatorial_to_horizontal,
    local_sidereal_time,
)
from star_hash.ephemeris import (
    RAD,
    jd_to_centuries,
    moon_geocentric,
    planet_geocentric,
    sun_geocentric,
)
from star_hash.projection import stereographic_project
from star_hash.stars import load_stars_for_epoch


def _project_equatorial(
    ra_rad: float,
    dec_rad: float,
    lat_rad: float,
    last_rad: float,
    dist_km: float | None = None,
    elevation_m: float = 0.0,
    apply_refraction: bool = True,
) -> Tuple[float, float]:
    """Project one equatorial position with the same reductions as ``starhash``."""
    if dist_km is not None:
        ra_rad, dec_rad = apply_topocentric_parallax(
            ra_rad, dec_rad, dist_km, lat_rad, elevation_m, last_rad
        )
    alt_rad, az_rad = equatorial_to_horizontal(ra_rad, dec_rad, lat_rad, last_rad)
    if apply_refraction:
        alt_rad = atmospheric_refraction(alt_rad)
    x, y, _ = stereographic_project(alt_rad, az_rad)
    return x, y


def evaluate_forward_model(
    lat_deg: float,
    lon_deg: float,
    jd_ut: float,
    body_names: List[str],
    elevation_m: float = 0.0,
    apply_refraction: bool = True,
) -> Dict[str, Tuple[float, float]]:
    """Evaluate projected coordinates for named bodies at a candidate state.

    The reductions match :func:`star_hash.starhash`: finite-distance bodies use
    the WGS84 topocentric correction and all altitudes may use Bennett refraction.
    A glyph does not contain elevation, so callers must supply the assumed value.
    """
    T = jd_to_centuries(jd_ut)
    lat_rad = lat_deg * RAD
    last_rad = local_sidereal_time(jd_ut, lon_deg * RAD)

    stars = {star["name"]: star for star in load_stars_for_epoch(T)}
    moon = moon_geocentric(T)
    moon_xy = _project_equatorial(
        moon["ra_rad"],
        moon["dec_rad"],
        lat_rad,
        last_rad,
        moon["dist_km"],
        elevation_m,
        apply_refraction,
    )

    planets: Dict[str, Tuple[float, float]] = {}
    for planet_name in ("mercury", "venus", "mars", "jupiter", "saturn"):
        planet = planet_geocentric(planet_name, T)
        planets[planet["name"]] = _project_equatorial(
            planet["ra_rad"],
            planet["dec_rad"],
            lat_rad,
            last_rad,
            planet["dist_km"],
            elevation_m,
            apply_refraction,
        )

    projected: Dict[str, Tuple[float, float]] = {}
    for name in body_names:
        if name == "Moon":
            projected[name] = moon_xy
        elif name == "Sun":
            sun = sun_geocentric(T)
            projected[name] = _project_equatorial(
                sun["ra_rad"],
                sun["dec_rad"],
                lat_rad,
                last_rad,
                apply_refraction=apply_refraction,
            )
        elif name in planets:
            projected[name] = planets[name]
        elif name in stars:
            star = stars[name]
            projected[name] = _project_equatorial(
                star["ra_rad"],
                star["dec_rad"],
                lat_rad,
                last_rad,
                apply_refraction=apply_refraction,
            )
    return projected


def _solve_3x3(matrix: List[List[float]], rhs: List[float]) -> List[float] | None:
    """Solve a 3x3 system by Gaussian elimination with pivoting."""
    a = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(a[row][column]))
        if abs(a[pivot][column]) < 1e-14:
            return None
        if pivot != column:
            a[column], a[pivot] = a[pivot], a[column]
        scale = a[column][column]
        for j in range(column, 4):
            a[column][j] /= scale
        for row in range(3):
            if row == column:
                continue
            factor = a[row][column]
            for j in range(column, 4):
                a[row][j] -= factor * a[column][j]
    return [a[row][3] for row in range(3)]


def _residual_vector(
    observed_points: Dict[str, Tuple[float, float]],
    state: Tuple[float, float, float],
    elevation_m: float,
    apply_refraction: bool,
) -> List[float]:
    predicted = evaluate_forward_model(
        state[0], state[1], state[2], list(observed_points), elevation_m, apply_refraction
    )
    residuals: List[float] = []
    for name, (observed_x, observed_y) in observed_points.items():
        if name not in predicted:
            raise ValueError(f"Unknown or unsupported body name: {name}")
        predicted_x, predicted_y = predicted[name]
        residuals.extend((predicted_x - observed_x, predicted_y - observed_y))
    return residuals


def _cost(residuals: List[float]) -> float:
    return math.fsum(value * value for value in residuals)


def solve_spacetime(
    observed_points: Dict[str, Tuple[float, float]],
    initial_guess: Tuple[float, float, float] | None = None,
    max_iterations: int = 50,
    elevation_m: float = 0.0,
    apply_refraction: bool = True,
) -> Dict[str, Any]:
    """Fit latitude, longitude, and Julian day to labeled projected points.

    This is a local, experimental solver. It assumes that each observed point
    already has a known body name and that the observer elevation is supplied
    separately. It does not identify a host planet or discover star identities
    from an unlabeled SVG.
    """
    if len(observed_points) < 3:
        raise ValueError("At least 3 labeled celestial points are required.")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive.")
    if not all(math.isfinite(value) for point in observed_points.values() for value in point):
        raise ValueError("Observed points must contain finite coordinates.")

    if initial_guess is None:
        state = [0.0, 0.0, 2451545.0]
    else:
        state = [float(value) for value in initial_guess]
    if not all(math.isfinite(value) for value in state):
        raise ValueError("initial_guess must contain finite values.")

    steps = (0.01, 0.01, 0.0001)  # degrees, degrees, days
    damping = 1e-3
    residuals = _residual_vector(observed_points, tuple(state), elevation_m, apply_refraction)
    cost = _cost(residuals)
    iterations = 0
    converged = False

    for iteration in range(max_iterations):
        iterations = iteration + 1
        jacobian: List[List[float]] = []
        for axis, step in enumerate(steps):
            displaced = state[:]
            displaced[axis] += step
            displaced_residuals = _residual_vector(
                observed_points, tuple(displaced), elevation_m, apply_refraction
            )
            if axis == 0:
                d_lat = [(b - a) / step for a, b in zip(residuals, displaced_residuals)]
            elif axis == 1:
                d_lon = [(b - a) / step for a, b in zip(residuals, displaced_residuals)]
            else:
                d_jd = [(b - a) / step for a, b in zip(residuals, displaced_residuals)]
        jacobian = [[d_lat[i], d_lon[i], d_jd[i]] for i in range(len(residuals))]

        normal = [[0.0, 0.0, 0.0] for _ in range(3)]
        gradient = [0.0, 0.0, 0.0]
        for row, residual in zip(jacobian, residuals):
            for i in range(3):
                gradient[i] += row[i] * residual
                for j in range(3):
                    normal[i][j] += row[i] * row[j]
        for i in range(3):
            normal[i][i] += damping * (normal[i][i] + 1.0)

        delta = _solve_3x3(normal, [-value for value in gradient])
        if delta is None:
            damping *= 10.0
            continue

        # Backtracking makes the local method reject steps that increase error.
        accepted = False
        scale = 1.0
        trial_state = state[:]
        trial_residuals = residuals
        trial_cost = cost
        for _ in range(16):
            trial_state = [state[i] + scale * delta[i] for i in range(3)]
            trial_state[0] = max(-90.0, min(90.0, trial_state[0]))
            trial_state[1] = ((trial_state[1] + 180.0) % 360.0) - 180.0
            trial_residuals = _residual_vector(
                observed_points, tuple(trial_state), elevation_m, apply_refraction
            )
            trial_cost = _cost(trial_residuals)
            if trial_cost < cost:
                accepted = True
                break
            scale *= 0.5

        if not accepted:
            damping *= 10.0
            continue

        state = trial_state
        residuals = trial_residuals
        previous_cost = cost
        cost = trial_cost
        damping = max(damping / 3.0, 1e-12)
        scaled_step = max(
            abs(scale * delta[0]), abs(scale * delta[1]), abs(scale * delta[2]) * 360.0
        )
        if scaled_step < 1e-7 or abs(previous_cost - cost) < 1e-16:
            converged = True
            break

    return {
        "latitude_deg": state[0],
        "longitude_deg": state[1],
        "julian_day": state[2],
        "cost": cost,
        "residual_rms": math.sqrt(cost / len(residuals)) if residuals else 0.0,
        "iterations": iterations,
        "converged": converged,
    }
