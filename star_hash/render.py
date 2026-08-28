"""
star_hash.render
~~~~~~~~~~~~~~~~
Zero-dependency, pure-string SVG vector seal generator for Starhash ciphers.
Produces museum-grade conformal astrolabe celestial seals.
"""
from __future__ import annotations

import math
from typing import List, Dict, Any

from star_hash.ephemeris import RAD, DEG, TWO_PI
from star_hash.projection import stereographic_project

def generate_svg_seal(
    stars: List[Dict[str, Any]],
    planets: List[Dict[str, Any]],
    moon: Dict[str, Any] | None,
    sun: Dict[str, Any] | None,
    hash_label: str = "STARHASH-CIPHER",
    size: int = 512,
    horizon_cutoff: bool = True,
) -> str:
    """
    Renders a complete conformal celestial seal as a standalone SVG string.
    Zero external dependencies.
    """
    center = size / 2.0
    radius = (size / 2.0) - 28.0  # Outer horizon radius in px

    # Base SVG setup with embedded styles and filters
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Celestial Spacetime Seal">',
        '  <defs>',
        '    <radialGradient id="sh-sky" cx="50%" cy="50%" r="50%">',
        '      <stop offset="0%" stop-color="#0a0c12" stop-opacity="1" />',
        '      <stop offset="65%" stop-color="#050608" stop-opacity="1" />',
        '      <stop offset="100%" stop-color="#000000" stop-opacity="1" />',
        '    </radialGradient>',
        '    <filter id="sh-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '      <feGaussianBlur in="SourceGraphic" stdDeviation="1.0" result="blur" />',
        '      <feMerge>',
        '        <feMergeNode in="blur" />',
        '        <feMergeNode in="SourceGraphic" />',
        '      </feMerge>',
        '    </filter>',
        '  </defs>',
        f'  <rect width="{size}" height="{size}" fill="#000000" />',
        f'  <circle cx="{center}" cy="{center}" r="{radius:.1f}" fill="url(#sh-sky)" stroke="#272b38" stroke-width="1.2" />',
    ]

    # Altitude rings (30 deg and 60 deg above horizon)
    # r(30 deg) = tan(30/2 deg) = 0.57735
    # r(60 deg) = tan(15 deg)   = 0.26795
    r_30 = radius * 0.57735
    r_60 = radius * 0.26795
    svg.append(f'  <circle cx="{center}" cy="{center}" r="{r_30:.2f}" fill="none" stroke="#161a24" stroke-width="0.8" stroke-dasharray="2 3" />')
    svg.append(f'  <circle cx="{center}" cy="{center}" r="{r_60:.2f}" fill="none" stroke="#161a24" stroke-width="0.8" stroke-dasharray="2 3" />')

    # Meridian and Prime Vertical Axes
    svg.append(f'  <line x1="{center}" y1="{center - radius}" x2="{center}" y2="{center + radius}" stroke="#161a24" stroke-width="0.8" />')
    svg.append(f'  <line x1="{center - radius}" y1="{center}" x2="{center + radius}" y2="{center}" stroke="#161a24" stroke-width="0.8" />')
    svg.append(f'  <circle cx="{center}" cy="{center}" r="2" fill="#2d3345" />')

    # Cardinal markers
    svg.append(f'  <text x="{center}" y="{center - radius - 8:.1f}" fill="#64748b" font-family="ui-monospace, monospace" font-size="9" font-weight="600" text-anchor="middle">N</text>')
    svg.append(f'  <text x="{center + radius + 11:.1f}" y="{center + 3.5:.1f}" fill="#64748b" font-family="ui-monospace, monospace" font-size="9" font-weight="600" text-anchor="middle">E</text>')
    svg.append(f'  <text x="{center}" y="{center + radius + 16:.1f}" fill="#64748b" font-family="ui-monospace, monospace" font-size="9" font-weight="600" text-anchor="middle">S</text>')
    svg.append(f'  <text x="{center - radius - 11:.1f}" y="{center + 3.5:.1f}" fill="#64748b" font-family="ui-monospace, monospace" font-size="9" font-weight="600" text-anchor="middle">W</text>')

    # 1. Render Visible Stars
    svg.append('  <!-- Navigational Stars -->')
    svg.append('  <g id="stars">')
    for s in stars:
        alt = s["alt_rad"]
        az = s["az_rad"]
        if horizon_cutoff and alt < -0.01:
            continue
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if horizon_cutoff and r_proj > 1.02:
            continue

        px = center + radius * x_proj
        py = center + radius * y_proj

        mag = s.get("mag", 2.0)
        dot_r = max(0.6, min(3.4, 3.2 - 0.55 * mag))
        opacity = max(0.25, min(1.0, 1.0 - 0.16 * max(0.0, mag + 1.0)))

        if mag <= 1.4:
            svg.append(f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="{dot_r:.2f}" fill="#ffffff" opacity="{opacity:.2f}" filter="url(#sh-glow)" />')
        else:
            svg.append(f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="{dot_r:.2f}" fill="#cbd5e1" opacity="{opacity:.2f}" />')
    svg.append('  </g>')

    # 2. Render Planets
    svg.append('  <!-- Planets -->')
    svg.append('  <g id="planets">')
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
        color = "#e2b358" if name in ["Venus", "Jupiter", "Saturn"] else ("#f87171" if name == "Mars" else "#cbd5e1")
        svg.append(f'    <!-- {name} -->')
        svg.append(f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="4.5" fill="none" stroke="{color}" stroke-width="1.0" />')
        svg.append(f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="1.8" fill="{color}" />')
        svg.append(f'    <text x="{px + 6.5:.2f}" y="{py + 3.0:.2f}" fill="{color}" font-family="ui-monospace, monospace" font-size="8" font-weight="500" letter-spacing="0.04em">{name}</text>')
    svg.append('  </g>')

    # 3. Render Moon with True Geometrical Crescent
    if moon is not None and (not horizon_cutoff or moon.get("alt_rad", -1.0) >= -0.01):
        alt = moon["alt_rad"]
        az = moon["az_rad"]
        x_proj, y_proj, r_proj = stereographic_project(alt, az)
        if not (horizon_cutoff and r_proj > 1.02):
            px = center + radius * x_proj
            py = center + radius * y_proj
            phase = moon["phase"]  # 0.0 to 1.0
            limb_angle = moon.get("limb_angle_rad", 0.0)
            moon_r = 7.5

            svg.append('  <!-- Moon -->')
            svg.append(f'  <g id="moon" transform="translate({px:.2f}, {py:.2f})">')
            svg.append(f'    <circle cx="0" cy="0" r="{moon_r}" fill="#161b26" stroke="#475569" stroke-width="0.8" />')

            rot_deg = limb_angle * DEG + 90.0
            svg.append(f'    <g transform="rotate({rot_deg:.1f})">')
            if phase >= 0.98:
                svg.append(f'      <circle cx="0" cy="0" r="{moon_r}" fill="#f8fafc" />')
            elif phase > 0.02:
                w = moon_r * (2.0 * phase - 1.0)
                sweep_inner = 1 if phase > 0.5 else 0
                path_d = f"M 0 {-moon_r} A {moon_r} {moon_r} 0 0 1 0 {moon_r} A {abs(w):.2f} {moon_r} 0 0 {sweep_inner} 0 {-moon_r} Z"
                svg.append(f'      <path d="{path_d}" fill="#f8fafc" />')
            svg.append('    </g>')
            svg.append(f'    <text x="10" y="3" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="8">Moon {int(phase * 100)}%</text>')
            svg.append('  </g>')

    # 4. Outer Rim Hash & Minute Divisions
    svg.append('  <!-- Astrolabe Rim Divisions -->')
    for tick in range(72):
        angle = tick * (TWO_PI / 72.0)
        is_major = tick % 6 == 0
        r_in = radius if is_major else radius + 2.0
        r_out = radius + (7.0 if is_major else 4.0)
        x1 = center + r_in * math.sin(angle)
        y1 = center - r_in * math.cos(angle)
        x2 = center + r_out * math.sin(angle)
        y2 = center - r_out * math.cos(angle)
        stroke_c = "#475569" if is_major else "#262f3f"
        stroke_w = 1.0 if is_major else 0.6
        svg.append(f'  <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke_c}" stroke-width="{stroke_w}" />')

    # 5. Metadata Legend / Hash Stamp
    svg.append(f'  <text x="{center}" y="{size - 9:.1f}" fill="#64748b" font-family="ui-monospace, monospace" font-size="8.5" text-anchor="middle" letter-spacing="0.12em">{hash_label}</text>')
    svg.append('</svg>')

    return "\n".join(svg)
