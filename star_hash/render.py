"""
star_hash.render
~~~~~~~~~~~~~~~~
Monochrome SVG seal renderer for Starhash.
Renders a local sky view with stars, the ecliptic, the Moon, and planets.
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

# Layout, in units of size/456. The horizon sits inside a limb, the band that
# carries the document ring, like the graduated edge of an astrolabe.
HORIZON_MARGIN = 22.0   # canvas edge to horizon circle
LIMB_WIDTH = 16.0       # horizon circle to the outer circle of the limb
RING_INNER = 4.0        # document ticks start here, beyond the horizon
RING_SHORT = 7.0        # a short tick (bit 0) ends here
RING_LONG = 12.0        # a long tick (bit 1) ends here

# Planet signs as engraved strokes, drawn in a box about 7 wide and 10 high
# centred on the origin, so that no font is needed to render or read them.
PLANET_GLYPHS = {
    "Mercury": "M -2 -6.4 A 2 2 0 0 0 2 -6.4 M 2 -2.4 A 2 2 0 1 0 -2 -2.4 A 2 2 0 1 0 2 -2.4 M 0 -0.4 L 0 4 M -1.8 2 L 1.8 2",
    "Venus": "M 2.4 -2.2 A 2.4 2.4 0 1 0 -2.4 -2.2 A 2.4 2.4 0 1 0 2.4 -2.2 M 0 0.2 L 0 4.6 M -2 2.4 L 2 2.4",
    "Mars": "M 1.6 1.1 A 2.5 2.5 0 1 0 -3.4 1.1 A 2.5 2.5 0 1 0 1.6 1.1 M 0.9 -0.7 L 3.4 -3.2 M 1.2 -3.2 L 3.4 -3.2 L 3.4 -1",
    "Jupiter": "M -3 -2.6 C -2 -4.6 0.8 -4.2 0.2 -1.6 C -0.2 0 -1.8 1 -3 1.8 L 3 1.8 M 1.4 -4.2 L 1.4 4.4",
    "Saturn": "M -1.6 -4.6 L -1.6 2.2 M -3.2 -3 L 0.2 -3 M -1.6 0 C -0.6 -2 2.2 -1.8 2.2 0.4 C 2.2 1.8 0.8 2.4 0.9 3.6 C 1 4.3 1.8 4.6 2.6 4.1",
}

ARIES_GLYPH = "M -2.8 -1.4 C -2.8 -3.8 -0.3 -3.8 0 -0.6 L 0 3.6 M 0 -0.6 C 0.3 -3.8 2.8 -3.8 2.8 -1.4"

INK = "#000000"
PAPER = "#ffffff"


def generate_svg_seal(
    stars: List[Dict[str, Any]],
    planets: List[Dict[str, Any]],
    moon: Dict[str, Any] | None,
    sun: Dict[str, Any] | None,
    last_rad: float = 0.0,
    lat_rad: float = 0.0,
    size: int = 456,
    horizon_cutoff: bool = True,
    document_digest: bytes | None = None,
) -> str:
    """Render a label-free monochrome SVG seal.

    Every mark carries information; nothing is ornament. The sky fills the
    horizon circle, north at the top. Around it runs the limb; when ``document_digest`` is given, its bits are engraved there as
    ticks, read clockwise from the north mark, long for 1 and short for 0.
    """
    scale = size / 456.0
    center = size / 2.0
    radius = (size / 2.0) - (HORIZON_MARGIN * scale)
    limb = radius + LIMB_WIDTH * scale

    w_border = 1.0 * scale
    w_hairline = 0.5 * scale
    w_fine = 0.3 * scale

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Celestial Spacetime Seal">',
        '  <defs>',
        '    <clipPath id="horizon_clip">',
        f'      <circle cx="{center:.2f}" cy="{center:.2f}" r="{radius:.2f}" />',
        '    </clipPath>',
        '  </defs>',
        f'  <rect width="{size}" height="{size}" fill="{PAPER}" />',
        # Limb: horizon inside, a hairline outside.
        f'  <circle cx="{center:.2f}" cy="{center:.2f}" r="{radius:.2f}" fill="none" stroke="{INK}" stroke-width="{0.8*scale:.2f}" />',
        f'  <circle cx="{center:.2f}" cy="{center:.2f}" r="{limb:.2f}" fill="none" stroke="{INK}" stroke-width="{w_fine:.2f}" />',
    ]

    # North: a solid wedge resting on the limb. East, south, west: a short stroke.
    tip, base, half = limb + 0.2 * scale, limb + 4.4 * scale, 2.0 * scale
    svg.append(
        f'  <path id="north" d="M {center:.2f} {center - tip:.2f} L {center - half:.2f} {center - base:.2f} '
        f'L {center + half:.2f} {center - base:.2f} Z" fill="{INK}" />'
    )
    for dx, dy in ((1, 0), (0, 1), (-1, 0)):
        svg.append(
            f'  <line x1="{center + dx*limb:.2f}" y1="{center + dy*limb:.2f}" '
            f'x2="{center + dx*(limb + 5.0*scale):.2f}" y2="{center + dy*(limb + 5.0*scale):.2f}" '
            f'stroke="{INK}" stroke-width="{w_hairline:.2f}" />'
        )

    # Document ring: one tick per bit of the document's hash, read clockwise
    # from north as drawn. A long tick is 1, a short tick is 0.
    if document_digest:
        bits = len(document_digest) * 8
        r_in = radius + RING_INNER * scale
        svg.append('  <g id="document">')
        for k in range(bits):
            bit = (document_digest[k // 8] >> (7 - k % 8)) & 1
            r_out = radius + (RING_LONG if bit else RING_SHORT) * scale
            az = (k + 0.5) * TWO_PI / bits
            dx, dy = math.sin(az), -math.cos(az)
            svg.append(f'    <line x1="{center + r_in*dx:.2f}" y1="{center + r_in*dy:.2f}" x2="{center + r_out*dx:.2f}" y2="{center + r_out*dy:.2f}" stroke="{INK}" stroke-width="{0.6*scale:.2f}" />')
        svg.append('  </g>')

    # Zenith: a small open ring, with two faint circles of equal altitude
    # (30 and 60 degrees) widening from it like ripples.
    svg.append(f'  <circle id="zenith" cx="{center:.2f}" cy="{center:.2f}" r="{1.8*scale:.2f}" fill="none" stroke="{INK}" stroke-width="{w_fine:.2f}" />')
    for altitude_deg in (60.0, 30.0):
        r_alt = radius * math.tan((90.0 - altitude_deg) * RAD / 2.0)
        svg.append(f'  <circle cx="{center:.2f}" cy="{center:.2f}" r="{r_alt:.2f}" fill="none" stroke="{INK}" stroke-width="{w_fine:.2f}" opacity="0.28" />')

    svg.append('  <g clip-path="url(#horizon_clip)">')

    # The celestial pole, the still point the sky turns about.
    pole_az = 0.0 if lat_rad >= 0.0 else math.pi
    xp, yp, _ = stereographic_project(abs(lat_rad), pole_az)
    qx, qy = center + radius * xp, center + radius * yp
    arm, diag = 4.2 * scale, 1.9 * scale
    svg.append(
        f'    <path id="pole" d="M {qx - arm:.2f} {qy:.2f} L {qx + arm:.2f} {qy:.2f} M {qx:.2f} {qy - arm:.2f} L {qx:.2f} {qy + arm:.2f} '
        f'M {qx - diag:.2f} {qy - diag:.2f} L {qx + diag:.2f} {qy + diag:.2f} M {qx - diag:.2f} {qy + diag:.2f} L {qx + diag:.2f} {qy - diag:.2f}" '
        f'fill="none" stroke="{INK}" stroke-width="{w_fine:.2f}" opacity="0.7" />'
    )

    # 1. Ecliptic: the one drawn line in the sky. The visible part is one arc;
    # start the walk just after the hidden part so it never closes across.
    eps = 23.43928 * RAD
    steps = 180

    def ecliptic_point(step: int):
        lon_step = step * (TWO_PI / steps)
        ra_e = math.atan2(math.sin(lon_step) * math.cos(eps), math.cos(lon_step))
        dec_e = math.asin(math.sin(lon_step) * math.sin(eps))
        return equatorial_to_horizontal(ra_e, dec_e, lat_rad, last_rad)

    hidden = [ecliptic_point(step)[0] < -0.05 for step in range(steps)]
    start = next((s + 1 for s in range(steps) if hidden[s] and not hidden[(s + 1) % steps]), 0)
    ecl_points = []
    for step in range(start, start + steps):
        alt_e, az_e = ecliptic_point(step)
        if alt_e >= -0.05:
            xp, yp, rp = stereographic_project(alt_e, az_e)
            if rp <= 1.06:
                ecl_points.append(f"{center + radius * xp:.2f},{center + radius * yp:.2f}")
    if len(ecl_points) >= 2:
        svg.append(f'    <polyline id="ecliptic" points="{" ".join(ecl_points)}" fill="none" stroke="{INK}" stroke-width="{0.4*scale:.2f}" opacity="0.5" />')

    # The twelve signs: a small stroke across the ecliptic every 30 degrees,
    # and the sign of Aries where the count begins.
    def ecliptic_xy(lon_deg: float):
        lon = lon_deg * RAD
        ra_e = math.atan2(math.sin(lon) * math.cos(eps), math.cos(lon))
        dec_e = math.asin(math.sin(lon) * math.sin(eps))
        alt_e, az_e = equatorial_to_horizontal(ra_e, dec_e, lat_rad, last_rad)
        xe, ye, _ = stereographic_project(alt_e, az_e)
        return alt_e, center + radius * xe, center + radius * ye

    signs = []
    for sign_index in range(12):
        alt_e, ex, ey = ecliptic_xy(30.0 * sign_index)
        if alt_e < 0.0:
            continue
        _, bx, by = ecliptic_xy(30.0 * sign_index + 0.5)
        along = math.hypot(bx - ex, by - ey) or 1.0
        nx, ny = -(by - ey) / along, (bx - ex) / along
        half = (3.4 if sign_index % 3 == 0 else 2.0) * scale
        signs.append(f"M {ex - nx*half:.2f} {ey - ny*half:.2f} L {ex + nx*half:.2f} {ey + ny*half:.2f}")
        if sign_index == 0:
            # Set the ram's horns on the side of the line facing the zenith.
            if (center - ex) * nx + (center - ey) * ny < 0.0:
                nx, ny = -nx, -ny
            svg.append(
                f'    <path id="aries" transform="translate({ex + nx*9.5*scale:.2f},{ey + ny*9.5*scale:.2f}) scale({scale:.4f})" '
                f'd="{ARIES_GLYPH}" fill="none" stroke="{INK}" stroke-width="0.6" stroke-linecap="round" opacity="0.75" />'
            )
    if signs:
        svg.append(f'    <path id="signs" d="{" ".join(signs)}" fill="none" stroke="{INK}" stroke-width="{0.4*scale:.2f}" opacity="0.6" />')

    # 2. Moon: a disc with the dark part cut away, turned to face the Sun.
    if moon and (not horizon_cutoff or moon.get("alt_rad", -1.0) >= -0.01):
        x_proj, y_proj, r_proj = stereographic_project(moon["alt_rad"], moon["az_rad"])
        if not (horizon_cutoff and r_proj > 1.01):
            mx = center + radius * x_proj
            my = center + radius * y_proj
            phase = moon.get("phase", 1.0)
            limb_angle = moon.get("limb_angle_rad", 0.0)
            r_moon = 5.6 * scale

            rot_deg = limb_angle * DEG + 90.0
            svg.append('    <g id="moon">')
            svg.append(f'      <g transform="rotate({rot_deg:.2f}, {mx:.2f}, {my:.2f})">')
            svg.append(f'        <circle cx="{mx:.2f}" cy="{my:.2f}" r="{r_moon:.2f}" fill="{INK}" />')
            if phase < 0.98 and phase > 0.02:
                w = r_moon * (2.0 * phase - 1.0)
                sweep_inner = 1 if phase > 0.5 else 0
                path_d = f"M {mx:.2f} {my - r_moon:.2f} A {r_moon:.2f} {r_moon:.2f} 0 0 1 {mx:.2f} {my + r_moon:.2f} A {abs(w):.2f} {r_moon:.2f} 0 0 {sweep_inner} {mx:.2f} {my - r_moon:.2f} Z"
                svg.append(f'        <path d="{path_d}" fill="{PAPER}" />')
            elif phase <= 0.02:
                svg.append(f'        <circle cx="{mx:.2f}" cy="{my:.2f}" r="{r_moon*0.92:.2f}" fill="{PAPER}" />')
            svg.append('      </g>')
            # The whole disc in outline, so the lit fraction can be measured.
            svg.append(f'      <ellipse cx="{mx:.2f}" cy="{my:.2f}" rx="{r_moon:.2f}" ry="{r_moon:.2f}" fill="none" stroke="{INK}" stroke-width="{w_fine:.2f}" />')
            svg.append('    </g>')

    # 3. Stars: dots in five sizes by magnitude.
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

        svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r_star:.2f}" fill="{INK}" />')
    svg.append('    </g>')

    # 4. Sun: the circumpunct.
    if sun and (not horizon_cutoff or sun.get("alt_rad", -1.0) >= -0.01):
        x_proj, y_proj, r_proj = stereographic_project(sun["alt_rad"], sun["az_rad"])
        if not (horizon_cutoff and r_proj > 1.01):
            sx = center + radius * x_proj
            sy = center + radius * y_proj
            svg.append('    <g id="sun">')
            svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{5.2*scale:.2f}" fill="{PAPER}" stroke="{INK}" stroke-width="{w_border:.2f}" />')
            svg.append(f'      <circle cx="{sx:.2f}" cy="{sy:.2f}" r="{1.4*scale:.2f}" fill="{INK}" />')
            svg.append('    </g>')

    # 5. Planets: a ringed point, with its sign engraved beside it.
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
        # Keep the sign inside the horizon: place it on the zenith side.
        side = -1.0 if x_proj > 0.0 else 1.0
        gx = px + side * 9.5 * scale

        svg.append(f'      <g id="planet-{name.lower()}">')
        svg.append(f'        <circle cx="{px:.2f}" cy="{py:.2f}" r="{3.2*scale:.2f}" fill="{PAPER}" stroke="{INK}" stroke-width="{w_fine:.2f}" />')
        svg.append(f'        <circle cx="{px:.2f}" cy="{py:.2f}" r="{1.0*scale:.2f}" fill="{INK}" />')
        glyph = PLANET_GLYPHS.get(name)
        if glyph:
            svg.append(f'        <path transform="translate({gx:.2f},{py:.2f}) scale({scale:.4f})" d="{glyph}" fill="none" stroke="{INK}" stroke-width="0.6" stroke-linecap="round" stroke-linejoin="round" />')
        svg.append('      </g>')
    svg.append('    </g>')

    svg.append('  </g>')
    svg.append('</svg>')

    return "\n".join(svg)
