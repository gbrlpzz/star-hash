"""
star_hash.render
~~~~~~~~~~~~~~~~
High-elegance monochrome vector seal generator for Starhash spacetime ciphers.
Implements crisp architectural engraving aesthetics, alchemical planetary symbols,
and conformal stereographic astrolabe geometry.
"""
from __future__ import annotations

import math
from typing import List, Dict, Any

from star_hash.ephemeris import RAD, DEG, TWO_PI
from star_hash.projection import stereographic_project

# Classical Astronomical / Alchemical Symbols for the wandering bodies
ALCHEMICAL_SYMBOLS = {
    "Sun": "\u2609",      # ☉ Circumpunct
    "Moon": "\u263D",     # ☽ First Quarter / Crescent
    "Mercury": "\u263F",  # ☿ Caduceus
    "Venus": "\u2640",    # ♀ Ankh
    "Mars": "\u2642",     # ♂ Shield & Spear
    "Jupiter": "\u2643",  # ♃ Zeta / Lightning
    "Saturn": "\u2644",   # ♄ Sickle / Scythe
}

def generate_svg_seal(
    stars: List[Dict[str, Any]],
    planets: List[Dict[str, Any]],
    moon: Dict[str, Any] | None,
    sun: Dict[str, Any] | None,
    hash_label: str = "STARHASH-CIPHER",
    size: int = 456,
    horizon_cutoff: bool = True,
) -> str:
    """
    Renders a high-precision monochrome vector seal.
    Zero external dependencies.
    """
    scale = size / 456.0
    pt = (300.0 / 72.0) * scale  # Base point scale factor (~4.167px at 300DPI)

    # Stroke hierarchy (fine letterpress / engraving weights)
    w_heavy = 0.30 * pt      # Outer horizon border (~1.25px)
    w_hairline = 0.15 * pt   # Secondary grid lines & axes (~0.62px)

    center = size / 2.0
    radius = (size / 2.0) - (w_heavy / 2.0) - (4.0 * scale)
    inner_alt_radius = radius * 0.70  # 20-degree altitude boundary

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Celestial Spacetime Seal">',
        '  <defs>',
        f'    <clipPath id="horizon_clip">',
        f'      <circle cx="{center}" cy="{center}" r="{radius:.2f}" />',
        '    </clipPath>',
        '  </defs>',
        # Clean white background
        f'  <rect width="{size}" height="{size}" fill="#ffffff" />',
        # Outer Horizon Ring
        f'  <circle cx="{center}" cy="{center}" r="{radius:.2f}" fill="none" stroke="#000000" stroke-width="{w_heavy:.2f}" shape-rendering="geometricPrecision" />',
        # Inner Altitude Ring (20-degree altitude boundary)
        f'  <circle cx="{center}" cy="{center}" r="{inner_alt_radius:.2f}" fill="none" stroke="#000000" stroke-width="{w_hairline:.2f}" opacity="0.45" />',
        # Zenith Crosshair
        f'  <line x1="{center - 3.5*scale:.2f}" y1="{center:.2f}" x2="{center + 3.5*scale:.2f}" y2="{center:.2f}" stroke="#000000" stroke-width="{w_hairline:.2f}" />',
        f'  <line x1="{center:.2f}" y1="{center - 3.5*scale:.2f}" x2="{center:.2f}" y2="{center + 3.5*scale:.2f}" stroke="#000000" stroke-width="{w_hairline:.2f}" />',
        # North-South Meridian Line (dashed)
        f'  <line x1="{center:.2f}" y1="{center - radius:.2f}" x2="{center:.2f}" y2="{center + radius:.2f}" stroke="#000000" stroke-width="{w_hairline:.2f}" stroke-dasharray="{2.0*scale:.2f},{8.0*scale:.2f}" opacity="0.4" />',
    ]

    # Cardinal Ticks (N, E, S, W pointing inward)
    tick_len = 6.0 * scale
    cardinals = [
        (center, center - radius, 0, 1),       # North (top)
        (center + radius, center, -1, 0),      # East (right)
        (center, center + radius, 0, -1),      # South (bottom)
        (center - radius, center, 1, 0),       # West (left)
    ]
    for cx, cy, dx, dy in cardinals:
        x2 = cx + dx * tick_len
        y2 = cy + dy * tick_len
        svg.append(f'  <line x1="{cx:.2f}" y1="{cy:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#000000" stroke-width="{w_heavy:.2f}" />')

    # Bodies Group inside horizon clip
    svg.append('  <g clip-path="url(#horizon_clip)">')

    # 1. Render Moon (Geometric Crescent with Solar Vector Alignment)
    if moon and (not horizon_cutoff or moon.get("alt_rad", -1.0) >= -0.01):
        alt = moon["alt_rad"]
        az = moon["az_rad"]
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if not (horizon_cutoff and r_proj > 1.02):
            mx = center + radius * x_proj
            my = center + radius * y_proj
            phase = moon.get("phase", 1.0)
            limb_angle = moon.get("limb_angle_rad", 0.0)
            r_moon = 6.2 * scale

            # Rotate crescent to face the Sun
            rot_deg = limb_angle * DEG + 90.0
            svg.append(f'    <!-- Moon (Phase: {int(phase*100)}%) -->')
            svg.append(f'    <g id="moon" transform="rotate({rot_deg:.2f}, {mx:.2f}, {my:.2f})">')
            # Base black disk
            svg.append(f'      <circle cx="{mx:.2f}" cy="{my:.2f}" r="{r_moon:.2f}" fill="#000000" />')
            if phase < 0.98 and phase > 0.02:
                # White crescent mask
                w = r_moon * (2.0 * phase - 1.0)
                sweep_inner = 1 if phase > 0.5 else 0
                path_d = f"M {mx:.2f} {my - r_moon:.2f} A {r_moon:.2f} {r_moon:.2f} 0 0 1 {mx:.2f} {my + r_moon:.2f} A {abs(w):.2f} {r_moon:.2f} 0 0 {sweep_inner} {mx:.2f} {my - r_moon:.2f} Z"
                svg.append(f'      <path d="{path_d}" fill="#ffffff" />')
            elif phase <= 0.02:
                svg.append(f'      <circle cx="{mx:.2f}" cy="{my:.2f}" r="{r_moon*0.95:.2f}" fill="#ffffff" />')
            svg.append('    </g>')

    # 2. Render Stars (Proportional Hierarchical Sizing)
    svg.append('    <g id="stars">')
    for s in stars:
        alt = s["alt_rad"]
        az = s["az_rad"]
        if horizon_cutoff and alt < -0.01:
            continue
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if horizon_cutoff and r_proj > 1.02:
            continue

        sx = center + radius * x_proj
        sy = center + radius * y_proj
        mag = s.get("mag", 2.0)
        # Scaled dot radius
        r_star = max(0.45 * scale, (0.65 - (mag * 0.12)) * pt)
        svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_star:.2f}" fill="#000000" />')
    svg.append('    </g>')

    # 3. Render Sun (Classical Circumpunct ☉)
    if sun and (not horizon_cutoff or sun.get("alt_rad", -1.0) >= -0.01):
        alt = sun["alt_rad"]
        az = sun["az_rad"]
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if not (horizon_cutoff and r_proj > 1.02):
            sx = center + radius * x_proj
            sy = center + radius * y_proj
            r_sun_outer = 3.2 * pt
            r_sun_inner = 1.0 * pt
            svg.append('    <g id="sun">')
            svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_sun_outer:.2f}" fill="#ffffff" stroke="#000000" stroke-width="{w_heavy:.2f}" />')
            svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_sun_inner:.2f}" fill="#000000" />')
            svg.append('    </g>')

    # 4. Render Planets (With Classical Alchemical / Astrological Glyphs)
    svg.append('    <g id="planets">')
    for p in planets:
        alt = p["alt_rad"]
        az = p["az_rad"]
        if horizon_cutoff and alt < -0.01:
            continue
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if horizon_cutoff and r_proj > 1.02:
            continue

        px = center + radius * x_proj
        py = center + radius * y_proj
        name = p["name"]
        mag = p.get("mag", 0.0)
        planet_r = max(0.8, 1.5 - (mag * 0.15)) * pt
        symbol = ALCHEMICAL_SYMBOLS.get(name, "")

        svg.append(f'      <!-- {name} {symbol} -->')
        svg.append(f'      <circle cx="{px:.2f}" cy="{py:.2f}" r="{planet_r:.2f}" fill="#ffffff" stroke="#000000" stroke-width="{w_hairline:.2f}" />')
        svg.append(f'      <text x="{px + planet_r + 2.5*scale:.2f}" y="{py + 3.5*scale:.2f}" fill="#000000" font-family="system-ui, -apple-system, sans-serif" font-size="{10.0*scale:.1f}" font-weight="500">{symbol}</text>')
    svg.append('    </g>')

    svg.append('  </g>')

    # 5. Outer Bottom Stamp Hash Label (Subtle, Monochrome)
    svg.append(f'  <text x="{center:.2f}" y="{size - 4.0*scale:.2f}" fill="#71717a" font-family="ui-monospace, SFMono-Regular, monospace" font-size="{7.5*scale:.1f}" text-anchor="middle" letter-spacing="0.10em">{hash_label}</text>')
    svg.append('</svg>')

    return "\n".join(svg)
