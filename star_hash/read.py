"""
star_hash.read
~~~~~~~~~~~~~~
Read a place and a time back out of a seal's drawing.

Nothing but the geometry is used: the dots are matched against the star
catalogue to find the observer's latitude and sidereal time, and the Moon,
Sun and planets are then used as clock hands to find the date. Longitude
follows from the difference between sidereal time and the date.

The planets are identified by their engraved signs; the stars carry no
labels and are identified by their mutual angles alone.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from star_hash.astrometry import (
    apply_topocentric_parallax,
    atmospheric_refraction,
    local_sidereal_time,
)
from star_hash.ephemeris import (
    DEG,
    RAD,
    date_to_jd,
    jd_to_centuries,
    moon_geocentric,
    planet_geocentric,
    sun_geocentric,
)
from star_hash.invert import _residual_vector, _solve_3x3, solve_spacetime
from star_hash.projection import stereographic_deproject
from star_hash.render import (
    ALCHEMICAL_SYMBOLS,
    HORIZON_MARGIN,
    PLANET_GLYPHS,
    RING_LONG,
    RING_SHORT,
)
from star_hash.stars import STAR_CATALOG

Vec = Tuple[float, float, float]

# Dot radii used by the renderer, in units of size/456, brightest first.
_STAR_RADII = (2.4, 1.8, 1.3, 0.95, 0.70)
_SYMBOL_TO_NAME = {symbol: name for name, symbol in ALCHEMICAL_SYMBOLS.items()}
PLANET_NAMES = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
_NUM = r"(-?\d+(?:\.\d+)?)"
_CIRCLE = re.compile(rf'<circle\s+cx="{_NUM}"\s+cy="{_NUM}"\s+r="{_NUM}"')
_PLANET = re.compile(
    rf'<circle\s+cx="{_NUM}"\s+cy="{_NUM}"[^>]*/>\s*<circle[^>]*/>\s*<text[^>]*>([^<]*)</text>'
)
_PLANET_GROUP = re.compile(rf'<g id="planet-([a-z]+)">\s*<circle\s+cx="{_NUM}"\s+cy="{_NUM}"')
_PLANET_SIGN = re.compile(
    rf'<g>\s*<circle\s+cx="{_NUM}"\s+cy="{_NUM}"[^>]*/>\s*<circle[^>]*/>\s*<path[^>]*\sd="([^"]+)"'
)
_GLYPH_TO_NAME = {" ".join(d.split()): name for name, d in PLANET_GLYPHS.items()}
_LINE = re.compile(rf'<line\s+x1="{_NUM}"\s+y1="{_NUM}"\s+x2="{_NUM}"\s+y2="{_NUM}"')
_MOON_ARC = re.compile(rf"A\s+{_NUM}\s+{_NUM}\s+0\s+0\s+([01])\s+{_NUM}\s+{_NUM}\s+Z")

# Precession rates of the star model, degrees per Julian century.
_PREC_M = 1.281232
_PREC_N = 0.556753
_OBLIQUITY = 23.43928 * RAD


class SealReadError(ValueError):
    """The file is not a Starhash drawing, or it cannot be solved."""


@dataclass
class Drawing:
    """The geometric content of a seal, in unit-disc coordinates."""

    size: float
    radius_px: float
    stars: List[Tuple[float, float, int]]          # x, y, brightness class 0..4
    bodies: Dict[str, Tuple[float, float]]         # Sun, Moon, planets
    moon_phase: Optional[float] = None             # illuminated fraction, if drawn
    document_ring: Optional[str] = None            # hex of the bits in the tick ring
    pixels: List[Tuple[float, float]] = field(default_factory=list)  # raw centres, for comparison


@dataclass
class Reading:
    """What a drawing says about where and when it was cast."""

    latitude: float
    longitude: Optional[float]
    julian_day: Optional[float]
    time: Optional[str]
    sidereal_time_deg: float
    stars_drawn: int
    stars_matched: int
    bodies: List[str]
    converged: bool
    residual_px: Optional[float] = None
    sigma_latitude_deg: Optional[float] = None
    sigma_longitude_deg: Optional[float] = None
    sigma_time_s: Optional[float] = None
    candidates: int = 0
    note: str = ""
    document_ring: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)   # other dates that fit as well

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _star_class_for_mag(mag: float) -> int:
    if mag <= 0.5:
        return 0
    if mag <= 1.5:
        return 1
    if mag <= 2.5:
        return 2
    if mag <= 3.5:
        return 3
    return 4


def _parse_ring(svg: str, cx: float, cy: float, radius: float, scale: float) -> Optional[str]:
    """Bits of the document ring as hex: clockwise from north, long tick = 1."""
    group = re.search(r'<g id="document">(.*?)</g>', svg, re.S)
    if not group:
        return None
    ticks = [tuple(float(v) for v in m.groups()) for m in _LINE.finditer(group.group(1))]
    count = len(ticks)
    if count == 0 or count % 8:
        raise SealReadError("document ring is damaged: tick count is not a whole number of bytes")
    threshold = radius + 0.5 * (RING_SHORT + RING_LONG) * scale
    bits: List[Optional[int]] = [None] * count
    for x1, y1, x2, y2 in ticks:
        mx, my = (x1 + x2) / 2.0 - cx, (y1 + y2) / 2.0 - cy
        azimuth = math.atan2(mx, -my) % (2.0 * math.pi)
        slot = int(azimuth / (2.0 * math.pi) * count) % count
        reach = max(math.hypot(x1 - cx, y1 - cy), math.hypot(x2 - cx, y2 - cy))
        if bits[slot] is not None:
            raise SealReadError("document ring is damaged: two ticks share a position")
        bits[slot] = 1 if reach > threshold else 0
    value = 0
    for bit in bits:
        value = (value << 1) | (bit or 0)
    return f"{value:0{count // 4}x}"


def parse_drawing(svg: str) -> Drawing:
    """Extract the horizon circle, star dots and body positions from a seal."""
    view = re.search(rf'viewBox="0 0 {_NUM} {_NUM}"', svg)
    clip = re.search(r'<clipPath id="horizon_clip">\s*' + _CIRCLE.pattern, svg)
    stars_group = re.search(r'<g id="stars">(.*?)</g>', svg, re.S)
    if not view or not clip or not stars_group:
        raise SealReadError("not a Starhash seal: horizon or star group missing")

    size = float(view.group(1))
    scale = size / 456.0
    cx, cy, radius = (float(clip.group(i)) for i in (1, 2, 3))
    # The renderer derives these from the canvas size; prefer the exact values
    # over the two-decimal ones written in the file when they agree.
    for margin in (HORIZON_MARGIN, 8.0):  # current layout, then the 1.0 layout
        exact_radius = size / 2.0 - margin * scale
        if abs(cx - size / 2.0) < 0.011 and abs(radius - exact_radius) < 0.011:
            cx = cy = size / 2.0
            radius = exact_radius
            break

    pixels: List[Tuple[float, float]] = []

    def unit(px: float, py: float) -> Tuple[float, float]:
        pixels.append((px, py))
        return (px - cx) / radius, (py - cy) / radius

    stars: List[Tuple[float, float, int]] = []
    for m in _CIRCLE.finditer(stars_group.group(1)):
        px, py, r = float(m.group(1)), float(m.group(2)), float(m.group(3))
        r_units = r / scale
        star_class = min(range(5), key=lambda i: abs(_STAR_RADII[i] - r_units))
        x, y = unit(px, py)
        stars.append((x, y, star_class))

    bodies: Dict[str, Tuple[float, float]] = {}
    moon_phase: Optional[float] = None
    moon_at = svg.find('<g id="moon">')
    if moon_at >= 0:
        moon_svg = svg[moon_at:svg.find('<g id="stars">')]
        m = _CIRCLE.search(moon_svg)
        if m:
            bodies["Moon"] = unit(float(m.group(1)), float(m.group(2)))
            r_moon = float(m.group(3))
            arc = _MOON_ARC.search(moon_svg)
            if arc and r_moon > 0:
                w = float(arc.group(1)) / r_moon
                moon_phase = (1.0 + w) / 2.0 if arc.group(3) == "1" else (1.0 - w) / 2.0
            elif len(_CIRCLE.findall(moon_svg)) > 1:
                moon_phase = 0.0
            else:
                moon_phase = 1.0

    sun_at = svg.find('<g id="sun">')
    if sun_at >= 0:
        m = _CIRCLE.search(svg, sun_at)
        if m:
            bodies["Sun"] = unit(float(m.group(1)), float(m.group(2)))

    # A planet is known by the sign engraved beside it.
    planets_at = svg.find('<g id="planets">')
    for m in _PLANET_SIGN.finditer(svg, planets_at if planets_at >= 0 else len(svg)):
        name = _GLYPH_TO_NAME.get(" ".join(m.group(3).split()))
        if name:
            bodies[name] = unit(float(m.group(1)), float(m.group(2)))
    if not any(name in bodies for name in PLANET_NAMES):
        # Version 1.1 drawings name the planet in the markup.
        for m in _PLANET_GROUP.finditer(svg):
            name = m.group(1).capitalize()
            if name in PLANET_NAMES:
                bodies[name] = unit(float(m.group(2)), float(m.group(3)))
    if not any(name in bodies for name in PLANET_NAMES):
        # Version 1.0 drawings mark planets with a text symbol.
        planets_group = re.search(r'<g id="planets">(.*?)</g>', svg, re.S)
        for m in _PLANET.finditer(planets_group.group(1) if planets_group else ""):
            name = _SYMBOL_TO_NAME.get(m.group(3).strip())
            if name:
                bodies[name] = unit(float(m.group(1)), float(m.group(2)))

    return Drawing(
        size=size,
        radius_px=radius,
        stars=stars,
        bodies=bodies,
        moon_phase=moon_phase,
        document_ring=_parse_ring(svg, cx, cy, radius, scale),
        pixels=pixels,
    )


# ---------------------------------------------------------------------------
# Small vector helpers
# ---------------------------------------------------------------------------

def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normalize(a: Vec) -> Vec:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _angle(a: Vec, b: Vec) -> float:
    return math.acos(max(-1.0, min(1.0, _dot(a, b))))


def _equatorial_vec(ra_rad: float, dec_rad: float) -> Vec:
    c = math.cos(dec_rad)
    return (c * math.cos(ra_rad), c * math.sin(ra_rad), math.sin(dec_rad))


def _rotate(v: Vec, w: Vec) -> Vec:
    """Rotate ``v`` by the rotation vector ``w`` (Rodrigues)."""
    theta = math.sqrt(_dot(w, w))
    if theta < 1e-15:
        return v
    k = (w[0] / theta, w[1] / theta, w[2] / theta)
    c, s = math.cos(theta), math.sin(theta)
    kxv = _cross(k, v)
    kv = _dot(k, v) * (1.0 - c)
    return (v[0] * c + kxv[0] * s + k[0] * kv, v[1] * c + kxv[1] * s + k[1] * kv, v[2] * c + kxv[2] * s + k[2] * kv)


def _precession_vector(T: float) -> Vec:
    """Rotation vector taking J2000 directions to the equator of date."""
    return (0.0, -_PREC_N * T * RAD, _PREC_M * T * RAD)


def _apply(rows: List[Vec], v: Vec) -> Vec:
    return (_dot(rows[0], v), _dot(rows[1], v), _dot(rows[2], v))


def _transpose(rows: List[Vec]) -> List[Vec]:
    return [(rows[0][i], rows[1][i], rows[2][i]) for i in range(3)]


def _triad(a1: Vec, a2: Vec) -> List[Vec]:
    t1 = a1
    t2 = _normalize(_cross(a1, a2))
    return [t1, t2, _cross(t1, t2)]


def _rotation_between(c1: Vec, c2: Vec, h1: Vec, h2: Vec) -> List[Vec]:
    """Proper rotation R with R c1 = h1 and R c2 ~ h2, as rows."""
    tc = _triad(c1, c2)
    th = _triad(h1, h2)
    return [
        tuple(sum(th[k][i] * tc[k][j] for k in range(3)) for j in range(3))  # type: ignore[misc]
        for i in range(3)
    ]


def _best_rotation(pairs: List[Tuple[Vec, Vec]]) -> Optional[List[Vec]]:
    """Least-squares rotation taking each catalogue vector to its observed one."""
    b = [[math.fsum(h[i] * c[j] for c, h in pairs) for j in range(3)] for i in range(3)]
    x = b
    for _ in range(40):
        det = (
            x[0][0] * (x[1][1] * x[2][2] - x[1][2] * x[2][1])
            - x[0][1] * (x[1][0] * x[2][2] - x[1][2] * x[2][0])
            + x[0][2] * (x[1][0] * x[2][1] - x[1][1] * x[2][0])
        )
        if det <= 1e-12:
            return None
        inv_t = [
            [
                (x[(i + 1) % 3][(j + 1) % 3] * x[(i + 2) % 3][(j + 2) % 3]
                 - x[(i + 1) % 3][(j + 2) % 3] * x[(i + 2) % 3][(j + 1) % 3]) / det
                for j in range(3)
            ]
            for i in range(3)
        ]
        x = [[0.5 * (x[i][j] + inv_t[i][j]) for j in range(3)] for i in range(3)]
    return [tuple(row) for row in x]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Stars: latitude and sidereal time
# ---------------------------------------------------------------------------

def _true_altitude(apparent_alt: float) -> float:
    """Invert the renderer's refraction."""
    alt = apparent_alt
    for _ in range(12):
        alt = apparent_alt - (atmospheric_refraction(alt) - alt)
    return alt


def _horizon_vec(x: float, y: float) -> Vec:
    """Unit vector in a right-handed (north, west, up) frame."""
    alt, az = stereographic_deproject(x, y)
    alt = _true_altitude(alt)
    c = math.cos(alt)
    return (c * math.cos(az), -c * math.sin(az), math.sin(alt))


_CATALOG: List[Tuple[Vec, int, str]] = [
    (_equatorial_vec(ra * RAD, dec * RAD), _star_class_for_mag(mag), name)
    for name, ra, dec, mag in STAR_CATALOG
]
_NAME_COUNT: Dict[str, int] = {}
for _entry in _CATALOG:
    _NAME_COUNT[_entry[2]] = _NAME_COUNT.get(_entry[2], 0) + 1


def _identify(observed: List[Tuple[Vec, int]]) -> Tuple[List[Vec], List[Tuple[int, int]]]:
    """Find the sky orientation and label the dots.

    Returns the rotation taking J2000 equatorial vectors to the horizon frame
    and a list of (observed index, catalogue index) matches.
    """
    vote_obs = [(v, k) for v, k in observed if k <= 2]
    vote_cat = [(v, k) for v, k, _ in _CATALOG if k <= 2]
    if len(vote_obs) < 4:
        raise SealReadError("too few bright stars in the drawing to orient it")

    anchors = sorted(vote_obs, key=lambda item: (item[1], -item[0][2]))[:8]
    pair_tol = 0.4 * RAD
    hit = math.cos(0.3 * RAD)
    enough = max(6, int(0.7 * len(vote_obs)))

    def score(rotation: List[Vec]) -> int:
        back = _transpose(rotation)
        count = 0
        for h, k in vote_obs:
            q = _apply(back, h)
            for c, kc in vote_cat:
                if kc == k and _dot(q, c) > hit:
                    count += 1
                    break
        return count

    best_score, best_rotation = 0, None
    for i in range(len(anchors)):
        for j in range(i + 1, len(anchors)):
            (h1, k1), (h2, k2) = anchors[i], anchors[j]
            separation = _angle(h1, h2)
            if separation < 5.0 * RAD:
                continue
            for c1, kc1, _ in _CATALOG:
                if kc1 != k1:
                    continue
                for c2, kc2, _ in _CATALOG:
                    if kc2 != k2 or c2 is c1:
                        continue
                    if abs(_angle(c1, c2) - separation) > pair_tol:
                        continue
                    rotation = _rotation_between(c1, c2, h1, h2)
                    s = score(rotation)
                    if s > best_score:
                        best_score, best_rotation = s, rotation
                    if best_score >= enough:
                        break
                if best_score >= enough:
                    break
            if best_score >= enough:
                break
        if best_score >= enough:
            break

    if best_rotation is None or best_score < 4:
        raise SealReadError("the dots do not match the star catalogue")

    rotation = best_rotation
    matches: List[Tuple[int, int]] = []
    for tolerance_deg in (0.3, 0.2):
        back = _transpose(rotation)
        limit = math.cos(tolerance_deg * RAD)
        chosen: Dict[int, Tuple[float, int]] = {}
        for oi, (h, k) in enumerate(observed):
            q = _apply(back, h)
            best_d, best_ci = limit, -1
            for ci, (c, kc, _) in enumerate(_CATALOG):
                if kc == k:
                    d = _dot(q, c)
                    if d > best_d:
                        best_d, best_ci = d, ci
            if best_ci >= 0 and (best_ci not in chosen or best_d > chosen[best_ci][0]):
                chosen[best_ci] = (best_d, oi)
        matches = [(oi, ci) for ci, (_, oi) in chosen.items()]
        refined = _best_rotation([(_CATALOG[ci][0], observed[oi][0]) for oi, ci in matches])
        if refined is not None:
            rotation = refined
    return rotation, matches


# ---------------------------------------------------------------------------
# Bodies: the date
# ---------------------------------------------------------------------------

class _Clock:
    """Compares the model's Sun, Moon and planets with the drawn ones.

    Everything is done in the J2000 frame of the star catalogue, so no
    knowledge of the observer's longitude is needed.
    """

    def __init__(self, rotation: List[Vec], bodies: Dict[str, Vec], moon_phase: Optional[float]):
        back = _transpose(rotation)
        self.zenith = _apply(back, (0.0, 0.0, 1.0))
        self.observed = {name: _apply(back, h) for name, h in bodies.items()}
        self.moon_phase = moon_phase
        moon = self.observed.get("Moon")
        if moon is not None:
            ce, se = math.cos(_OBLIQUITY), math.sin(_OBLIQUITY)
            self.moon_longitude = math.atan2(moon[1] * ce + moon[2] * se, moon[0]) * DEG

    def site(self, T: float) -> Tuple[float, float]:
        """Latitude and local sidereal time (radians) on the equator of date."""
        z = _rotate(self.zenith, _precession_vector(T))
        return math.asin(max(-1.0, min(1.0, z[2]))), math.atan2(z[1], z[0])

    def model(self, name: str, T: float) -> Vec:
        if name == "Sun":
            body = sun_geocentric(T)
            ra, dec = body["ra_rad"], body["dec_rad"]
        elif name == "Moon":
            return self.moon(T)[0]
        else:
            body = planet_geocentric(name.lower(), T)
            ra, dec = body["ra_rad"], body["dec_rad"]
        return _rotate(_equatorial_vec(ra, dec), _precession_vector(-T))

    def moon(self, T: float) -> Tuple[Vec, float]:
        body = moon_geocentric(T)
        lat, lst = self.site(T)
        ra, dec = apply_topocentric_parallax(
            body["ra_rad"], body["dec_rad"], body["dist_km"], lat, 0.0, lst
        )
        return _rotate(_equatorial_vec(ra, dec), _precession_vector(-T)), body["phase"]

    def cost(self, jd: float) -> float:
        T = jd_to_centuries(jd)
        return math.fsum(
            _angle(self.model(name, T), q) ** 2 for name, q in self.observed.items()
        )

    def phase_ok(self, phase: float) -> bool:
        if self.moon_phase is None:
            return True
        if self.moon_phase >= 1.0:
            return phase >= 0.95
        if self.moon_phase <= 0.0:
            return phase <= 0.05
        return abs(phase - self.moon_phase) < 0.03

    # -- search ------------------------------------------------------------

    def coarse_windows(self, jd_start: float, jd_end: float) -> List[Tuple[float, float]]:
        """Day ranges in which the Sun and slower planets stand where drawn."""
        order = ("Sun", "Mars", "Jupiter", "Saturn", "Venus", "Mercury")
        hands = [name for name in order if name in self.observed][:2]
        if not hands:
            return [(jd_start, jd_end)]
        limit = math.cos(3.0 * RAD)
        windows: List[Tuple[float, float]] = []
        run_start: Optional[float] = None
        jd = jd_start
        while jd <= jd_end + 1.0:
            T = jd_to_centuries(jd)
            ok = jd <= jd_end and all(
                _dot(self.model(name, T), self.observed[name]) >= limit for name in hands
            )
            if ok and run_start is None:
                run_start = jd
            elif not ok and run_start is not None:
                windows.append((run_start - 1.0, jd))
                run_start = None
            jd += 1.0
        return windows

    def moon_times(self, jd_a: float, jd_b: float) -> List[float]:
        """Moments in a window when the Moon stands where drawn."""
        step = 0.1
        limit = math.cos(1.3 * RAD)
        target = self.observed["Moon"]
        out: List[float] = []
        best: Optional[Tuple[float, float]] = None
        steps = int((jd_b - jd_a) / step) + 1
        for i in range(steps + 1):
            jd = jd_a + i * step
            T = (jd - 2451545.0) / 36525.0
            # Cheap rejection on the Moon's mean longitude before the full series.
            mean = 218.3164477 + 481267.88123421 * T
            off = (mean - self.moon_longitude - 1.396971 * T + 180.0) % 360.0 - 180.0
            d = -2.0
            if -12.0 < off < 12.0:
                vec, phase = self.moon(T)
                d = _dot(vec, target)
                if d < limit or not self.phase_ok(phase):
                    d = -2.0
            if d > -2.0:
                if best is None or d > best[0]:
                    best = (d, jd)
            elif best is not None:
                out.append(best[1])
                best = None
        if best is not None:
            out.append(best[1])
        return out

    def refine(self, jd: float, half_width: float) -> Tuple[float, float]:
        """Golden-section minimum of the angular misfit near ``jd``."""
        a, b = jd - half_width, jd + half_width
        g = (math.sqrt(5.0) - 1.0) / 2.0
        c, d = b - g * (b - a), a + g * (b - a)
        fc, fd = self.cost(c), self.cost(d)
        for _ in range(36):
            if fc < fd:
                b, d, fd = d, c, fc
                c = b - g * (b - a)
                fc = self.cost(c)
            else:
                a, c, fc = c, d, fd
                d = a + g * (b - a)
                fd = self.cost(d)
        return (c, fc) if fc < fd else (d, fd)

    def candidates(self, jd_start: float, jd_end: float) -> List[Tuple[float, float]]:
        """(misfit, jd) for every moment that could be the drawn one."""
        found: List[Tuple[float, float]] = []
        for a, b in self.coarse_windows(jd_start, jd_end):
            if "Moon" in self.observed:
                for jd in self.moon_times(a, b):
                    t, c = self.refine(jd, 0.1)
                    found.append((c, t))
            else:
                # A planet can pass the same spot more than once in a window
                # (retrograde loop), so keep every local best, not just one.
                samples = max(8, min(1600, int((b - a) / 0.25)))
                step = (b - a) / samples
                costs = [self.cost(a + i * step) for i in range(samples + 1)]
                for i, value in enumerate(costs):
                    before = costs[i - 1] if i > 0 else math.inf
                    after = costs[i + 1] if i < samples else math.inf
                    if value <= before and value < after:
                        t, c = self.refine(a + i * step, step)
                        found.append((c, t))
        found.sort()
        return found


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def jd_to_iso(jd: float) -> Optional[str]:
    """UTC timestamp for a Julian Day, or None outside years 1-9999."""
    try:
        moment = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)
    except OverflowError:
        return None
    moment = (moment + timedelta(microseconds=500000)).replace(microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _uncertainty(
    points: Dict[str, Tuple[float, float]], state: Tuple[float, float, float], sigma: float
) -> Optional[Tuple[float, float, float]]:
    """One-sigma errors in latitude (deg), longitude (deg) and time (days)."""
    steps = (1e-4, 1e-4, 1e-6)
    base = _residual_vector(points, state, 0.0, True)
    columns = []
    for axis, step in enumerate(steps):
        moved = list(state)
        moved[axis] += step
        shifted = _residual_vector(points, tuple(moved), 0.0, True)  # type: ignore[arg-type]
        columns.append([(b - a) / step for a, b in zip(base, shifted)])
    normal = [[math.fsum(x * y for x, y in zip(columns[i], columns[j])) for j in range(3)] for i in range(3)]
    out = []
    for axis in range(3):
        unit = [1.0 if i == axis else 0.0 for i in range(3)]
        solved = _solve_3x3(normal, unit)
        if solved is None or solved[axis] <= 0.0:
            return None
        out.append(sigma * math.sqrt(solved[axis]))
    return out[0], out[1], out[2]


def _profile(
    points: Dict[str, Tuple[float, float]], solution: Dict[str, Any], rounding: float
) -> Tuple[Dict[str, Any], float]:
    """Walk the time axis at fixed sidereal time around a solution.

    A slow planet barely moves in a day, so many nearby dates fit the drawing
    equally well. Returns the best solution found and the half-width (days)
    of the span of dates that the drawing cannot tell apart.
    """
    lat, lon0, jd0 = solution["latitude_deg"], solution["longitude_deg"], solution["julian_day"]

    def at(offset: float) -> Tuple[float, float, float]:
        lon = (lon0 - offset * 360.98564736629 + 180.0) % 360.0 - 180.0
        return (lat, lon, jd0 + offset)

    offsets = [i * 0.25 for i in range(-80, 81)]
    costs = [math.fsum(r * r for r in _residual_vector(points, at(o), 0.0, True)) for o in offsets]
    lowest = min(costs)
    centre = offsets[costs.index(lowest)]
    retry = solve_spacetime(points, initial_guess=at(centre))
    if retry["residual_rms"] < solution["residual_rms"]:
        solution = retry
    fits = [o for o, c in zip(offsets, costs) if c - lowest <= 8.0 * rounding * rounding]
    return solution, (max(fits) - min(fits)) / 2.0


def read_seal(svg: str, year_from: int = 1800, year_to: int = 2200) -> Reading:
    """Recover latitude, longitude and time from a seal's drawing alone.

    ``year_from`` and ``year_to`` bound the search for the date. Raises :class:`SealReadError` if the drawing cannot be
    oriented against the star catalogue.
    """
    if year_to <= year_from:
        raise ValueError("year_to must be later than year_from")
    drawing = parse_drawing(svg)
    observed = [(_horizon_vec(x, y), k) for x, y, k in drawing.stars]
    rotation, matches = _identify(observed)
    clock = _Clock(
        rotation,
        {name: _horizon_vec(x, y) for name, (x, y) in drawing.bodies.items()},
        drawing.moon_phase,
    )
    bodies = sorted(drawing.bodies)
    lat0, lst0 = clock.site(0.0)

    if not bodies:
        return Reading(
            latitude=lat0 * DEG,
            longitude=None,
            julian_day=None,
            time=None,
            sidereal_time_deg=(lst0 * DEG) % 360.0,
            stars_drawn=len(drawing.stars),
            stars_matched=len(matches),
            bodies=[],
            converged=False,
            document_ring=drawing.document_ring,
            note="No Sun, Moon or planet is above the horizon, so the drawing "
                 "fixes latitude and sidereal time but not the date or longitude.",
        )

    found = clock.candidates(date_to_jd(year_from, 1, 1.0), date_to_jd(year_to, 1, 1.0))
    if not found:
        raise SealReadError(
            f"no date between {year_from} and {year_to} puts the Moon and planets where drawn"
        )

    # Labelled points for the final fit: every body, and the brightest stars.
    points: Dict[str, Tuple[float, float]] = dict(drawing.bodies)
    ranked = sorted(matches, key=lambda m: _CATALOG[m[1]][1])
    for oi, ci in ranked:
        name = _CATALOG[ci][2]
        if _NAME_COUNT[name] == 1 and name not in points:
            points[name] = drawing.stars[oi][:2]
        if len(points) >= len(drawing.bodies) + 40:
            break

    best: Optional[Dict[str, Any]] = None
    solutions: List[Dict[str, Any]] = []
    for _, jd in found[:12]:
        lat, lst = clock.site(jd_to_centuries(jd))
        lon = ((lst - local_sidereal_time(jd, 0.0)) * DEG + 180.0) % 360.0 - 180.0
        solution = solve_spacetime(points, initial_guess=(lat * DEG, lon, jd))
        solutions.append(solution)
        if best is None or solution["residual_rms"] < best["residual_rms"]:
            best = solution
    assert best is not None

    rounding = 0.01 / math.sqrt(12.0) / drawing.radius_px
    slow_only = not ({"Moon", "Sun", "Mercury", "Venus", "Mars"} & set(bodies))
    spread = 0.0
    if slow_only:
        best, spread = _profile(points, best, rounding)
    state = (best["latitude_deg"], best["longitude_deg"], best["julian_day"])
    sigmas = _uncertainty(points, state, max(best["residual_rms"], rounding))
    if sigmas and spread > sigmas[2]:
        sigmas = (sigmas[0], min(180.0, max(sigmas[1], spread * 360.98564736629)), spread)

    # A slow planet returns to the same spot around its retrograde loop, so
    # other dates may fit the drawing as well as the best one does.
    slack = math.sqrt(best["residual_rms"] ** 2 + rounding ** 2 / 4.0)
    other_days: List[float] = []
    for solution in solutions:
        jd = solution["julian_day"]
        if (
            solution["residual_rms"] <= slack
            and abs(jd - state[2]) > max(1.0, 3.0 * spread)
            and all(abs(jd - seen) > 1.0 for seen in other_days)
        ):
            other_days.append(jd)
    alternatives = [iso for iso in (jd_to_iso(jd) for jd in sorted(other_days)) if iso]
    return Reading(
        latitude=state[0],
        longitude=state[1],
        julian_day=state[2],
        time=jd_to_iso(state[2]),
        sidereal_time_deg=(local_sidereal_time(state[2], state[1] * RAD) * DEG) % 360.0,
        stars_drawn=len(drawing.stars),
        stars_matched=len(matches),
        bodies=bodies,
        converged=bool(best["converged"]),
        residual_px=best["residual_rms"] * drawing.radius_px,
        sigma_latitude_deg=sigmas[0] if sigmas else None,
        sigma_longitude_deg=sigmas[1] if sigmas else None,
        sigma_time_s=sigmas[2] * 86400.0 if sigmas else None,
        candidates=len(found),
        document_ring=drawing.document_ring,
        alternatives=alternatives,
        note=(
            "Only slow planets are above the horizon; time and longitude are loosely fixed."
            if slow_only else ""
        ),
    )
