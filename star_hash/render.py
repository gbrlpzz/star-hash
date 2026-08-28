"""
star_hash.render
~~~~~~~~~~~~~~~~
High-elegance monochrome vector seal generator for Starhash spacetime ciphers.
Renders full celestial sky dome (457 stars, ecliptic track, lunar crescent,
and alchemical planetary nodes) with clean architectural linework.
"""
from __future__ import annotations

import math
from typing import List, Dict, Any

from star_hash.ephemeris import RAD, DEG, TWO_PI
from star_hash.projection import stereographic_project
from star_hash.astrometry import equatorial_to_horizontal

ALCHEMICAL_SYMBOLS = {
    "Sun": "\u2609",      # ☉
    "Moon": "\u263D",     # ☽
    "Mercury": "\u263F",  # ☿
    "Venus": "\u2640",    # ♀
    "Mars": "\u2642",     # ♂
    "Jupiter": "\u2643",  # ♃
    "Saturn": "\u2644",   # ♄
}

def generate_svg_seal(
    stars: List[Dict[str, Any]],
    planets: List[Dict[str, Any]],
    moon: Dict[str, Any] | None,
    sun: Dict[str, Any] | None,
    last_rad: float = 0.0,
    lat_rad: float = 0.0,
    hash_label: str = "STARHASH-CIPHER",
    size: int = 456,
    horizon_cutoff: bool = True,
) -> str:
    """
    Renders a high-precision monochrome vector seal.
    Zero external dependencies.
    """
    scale = size / 456.0
    center = size / 2.0
    radius = (size / 2.0) - (8.0 * scale)
    inner_alt_radius = radius * 0.70  # 20-degree altitude boundary

    # Hairline stroke weights
    w_border = 1.0 * scale
    w_hairline = 0.5 * scale

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Celestial Spacetime Seal">',
        '  <defs>',
        f'    <clipPath id="horizon_clip">',
        f'      <circle cx="{center:.2f}" cy="{center:.2f}" r="{radius:.2f}" />',
        '    </clipPath>',
        '  </defs>',
        # Clean white background
        f'  <rect width="{size}" height="{size}" fill="#ffffff" />',
        # Outer Horizon Ring
        f'  <circle cx="{center:.2f}" cy="{center:.2f}" r="{radius:.2f}" fill="none" stroke="#000000" stroke-width="{w_border:.2f}" shape-rendering="geometricPrecision" />',
        # Inner Altitude Ring (20-degree altitude reference)
        f'  <circle cx="{center:.2f}" cy="{center:.2f}" r="{inner_alt_radius:.2f}" fill="none" stroke="#000000" stroke-width="{w_hairline:.2f}" stroke-dasharray="{3.0*scale:.2f},{5.0*scale:.2f}" opacity="0.4" />',
        # Zenith Crosshair
        f'  <line x1="{center - 3.5*scale:.2f}" y1="{center:.2f}" x2="{center + 3.5*scale:.2f}" y2="{center:.2f}" stroke="#000000" stroke-width="{w_hairline:.2f}" />',
        f'  <line x1="{center:.2f}" y1="{center - 3.5*scale:.2f}" x2="{center:.2f}" y2="{center + 3.5*scale:.2f}" stroke="#000000" stroke-width="{w_hairline:.2f}" />',
        # Local North-South Meridian Line
        f'  <line x1="{center:.2f}" y1="{center - radius:.2f}" x2="{center:.2f}" y2="{center + radius:.2f}" stroke="#000000" stroke-width="{w_hairline:.2f}" stroke-dasharray="{2.0*scale:.2f},{7.0*scale:.2f}" opacity="0.35" />',
    ]

    # Cardinal Notches (N, E, S, W pointing inward)
    notch = 5.0 * scale
    cardinals = [
        (center, center - radius, 0, 1),       # N
        (center + radius, center, -1, 0),      # E
        (center, center + radius, 0, -1),      # S
        (center - radius, center, 1, 0),       # W
    ]
    for cx, cy, dx, dy in cardinals:
        svg.append(f'  <line x1="{cx:.2f}" y1="{cy:.2f}" x2="{cx + dx*notch:.2f}" y2="{cy + dy*notch:.2f}" stroke="#000000" stroke-width="{w_border:.2f}" />')

    # Bodies Group inside horizon boundary
    svg.append('  <g clip-path="url(#horizon_clip)">')

    # 1. Continuous Ecliptic Arc (Plane of the Solar System across the sky)
    ecl_points = []
    eps = 23.43928 * RAD
    for step in range(96):
        lon_step = step * (TWO_PI / 96.0)
        xe = math.cos(lon_step)
        ye = math.sin(lon_step) * math.cos(eps)
        ze = math.sin(lon_step) * math.sin(eps)
        ra_e = math.atan2(ye, xe)
        dec_e = math.asin(ze)
        alt_e, az_e = equatorial_to_horizontal(ra_e, dec_e, lat_rad, last_rad)
        if alt_e >= -0.05:
            xp, yp, rp = stereographic_project(alt_e, az_e)
            if rp <= 1.02:
                sx = center + radius * xp
                sy = center + radius * yp
                ecl_points.append(f"{sx:.2f},{sy:.2f}")

    if len(ecl_points) >= 2:
        svg.append('    <!-- Ecliptic Track -->')
        svg.append(f'    <polyline points="{" ".join(ecl_points)}" fill="none" stroke="#000000" stroke-width="{w_hairline:.2f}" stroke-dasharray="{3.0*scale:.2f},{6.0*scale:.2f}" opacity="0.35" />')

    # 2. Render Moon (Geometric Crescent oriented along solar elongation)
    if moon and (not horizon_cutoff or moon.get("alt_rad", -1.0) >= -0.01):
        alt = moon["alt_rad"]
        az = moon["az_rad"]
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if not (horizon_cutoff and r_proj > 1.01):
            mx = center + radius * x_proj
            my = center + radius * y_proj
            phase = moon.get("phase", 1.0)
            limb_angle = moon.get("limb_angle_rad", 0.0)
            r_moon = 5.6 * scale

            rot_deg = limb_angle * DEG + 90.0
            svg.append('    <g id="moon">')
            svg.append(f'      <g transform="rotate({rot_deg:.2f}, {mx:.2f}, {my:.2f})">')
            svg.append(f'        <circle cx="{mx:.2f}" cy="{my:.2f}" r="{r_moon:.2f}" fill="#000000" />')
            if phase < 0.98 and phase > 0.02:
                w = r_moon * (2.0 * phase - 1.0)
                sweep_inner = 1 if phase > 0.5 else 0
                path_d = f"M {mx:.2f} {my - r_moon:.2f} A {r_moon:.2f} {r_moon:.2f} 0 0 1 {mx:.2f} {my + r_moon:.2f} A {abs(w):.2f} {r_moon:.2f} 0 0 {sweep_inner} {mx:.2f} {my - r_moon:.2f} Z"
                svg.append(f'        <path d="{path_d}" fill="#ffffff" />')
            elif phase <= 0.02:
                svg.append(f'        <circle cx="{mx:.2f}" cy="{my:.2f}" r="{r_moon*0.92:.2f}" fill="#ffffff" />')
            svg.append('      </g>')
            svg.append('    </g>')

    # 3. Render Stars (Full 457-star catalog with calibrated magnitude hierarchy)
    svg.append('    <g id="stars">')
    for s in stars:
        alt = s["alt_rad"]
        az = s["az_rad"]
        if horizon_cutoff and alt < -0.01:
            continue
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if horizon_cutoff and r_proj > 1.01:
            continue

        sx = center + radius * x_proj
        sy = center + radius * y_proj
        mag = s.get("mag", 2.5)

        # Calibrated star sizing for high-res print clarity
        if mag <= 0.5:
            r_star = 2.4 * scale
        elif mag <= 1.5:
            r_star = 1.8 * scale
        elif mag <= 2.5:
            r_star = 1.3 * scale
        elif mag <= 3.5:
            r_star = 0.95 * scale
        else:
            r_star = 0.70 * scale

        svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_star:.2f}" fill="#000000" />')
    svg.append('    </g>')

    # 4. Render Sun (Classical Circumpunct ☉ when visible)
    if sun and (not horizon_cutoff or sun.get("alt_rad", -1.0) >= -0.01):
        alt = sun["alt_rad"]
        az = sun["az_rad"]
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if not (horizon_cutoff and r_proj > 1.01):
            sx = center + radius * x_proj
            sy = center + radius * y_proj
            r_sun_out = 5.2 * scale
            r_sun_in = 1.4 * scale
            svg.append('    <g id="sun">')
            svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_sun_out:.2f}" fill="#ffffff" stroke="#000000" stroke-width="{w_border:.2f}" />')
            svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_sun_in:.2f}" fill="#000000" />')
            svg.append('    </g>')

    # 5. Render Major Planets with Alchemical Symbols
    svg.append('    <g id="planets">')
    for p in planets:
        alt = p["alt_rad"]
        az = p["az_rad"]
        if horizon_cutoff and alt < -0.01:
            continue
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if horizon_cutoff and r_proj > 1.01:
            continue

        px = center + radius * x_proj
        py = center + radius * y_proj
        name = p["name"]
        symbol = ALCHEMICAL_SYMBOLS.get(name, "")

        planet_r = 3.0 * scale
        font_s = 9.5 * scale

        svg.append(f'      <!-- {name} {symbol} -->')
        svg.append(f'      <circle cx="{px:.2f}" cy="{py:.2f}" r="{planet_r:.2f}" fill="#ffffff" stroke="#000000" stroke-width="{w_hairline:.2f}" />')
        svg.append(f'      <circle cx="{px:.2f}" cy="{py:.2f}" r="{1.0 * scale:.2f}" fill="#000000" />')
        svg.append(f'      <text x="{px + planet_r + 2.5*scale:.2f}" y="{py + 3.0*scale:.2f}" fill="#000000" font-family="system-ui, -apple-system, sans-serif" font-size="{font_s:.1f}" font-weight="500">{symbol}</text>')
    svg.append('    </g>')

    svg.append('  </g>')

    # 6. Subtle Inscription Stamp
    svg.append(f'  <text x="{center:.2f}" y="{size - 2.0*scale:.2f}" fill="#71717a" font-family="ui-monospace, SFMono-Regular, monospace" font-size="{6.5*scale:.1f}" text-anchor="middle" letter-spacing="0.14em">{hash_label}</text>')
    svg.append('</svg>')

    return "\n".join(svg)
