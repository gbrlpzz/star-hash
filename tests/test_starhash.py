"""Small deterministic checks for Starhash's geometry and reductions."""
import contextlib
import io
import math
import os
import re
import tempfile
import unittest

from star_hash import CelestialSeal, invert, read_seal, sign, starhash, verify
from star_hash.cli import main as cli_main
from star_hash.ephemeris import (
    date_to_jd,
    jd_to_centuries,
    moon_geocentric,
    planet_geocentric,
    solve_kepler,
    sun_geocentric,
)
from star_hash.projection import stereographic_deproject, stereographic_project
from star_hash.astrometry import local_sidereal_time


class TestStarhash(unittest.TestCase):
    def test_julian_day_reference_dates(self):
        # Standard examples from Meeus, Astronomical Algorithms, chapter 7.
        examples = [
            ((1987, 1, 27.0), 2446822.5),
            ((1987, 6, 19.5), 2446966.0),
            ((1900, 1, 0.5), 2415020.0),
            ((2000, 1, 1.5), 2451545.0),
        ]
        for date, expected in examples:
            self.assertAlmostEqual(date_to_jd(*date), expected, places=6)

    def test_sidereal_time_reference(self):
        # Greenwich mean sidereal time at J2000.0 (Meeus, chapter 12).
        value_deg = math.degrees(local_sidereal_time(2451545.0, 0.0))
        self.assertAlmostEqual(value_deg, 280.46061837, places=6)

    def test_kepler_equation_residual(self):
        for mean_anomaly in (-3.0, -0.4, 0.0, 1.2, 3.0):
            eccentric_anomaly = solve_kepler(mean_anomaly, 0.21)
            residual = eccentric_anomaly - 0.21 * math.sin(eccentric_anomaly) - mean_anomaly
            self.assertLess(abs(residual), 1e-9)

    def test_sun_at_j2000(self):
        sun = sun_geocentric(0.0)
        self.assertAlmostEqual(sun["dist_au"], 0.9833, places=3)
        self.assertAlmostEqual(sun["ra_rad"] * 180.0 / math.pi / 15.0, 18.752, places=2)

    def test_moon_phase_and_distance_terms(self):
        moon = moon_geocentric(0.0)
        self.assertTrue(0.20 <= moon["phase"] <= 0.26)
        self.assertTrue(390000.0 <= moon["dist_km"] <= 410000.0)

        # The distance coefficients are in 0.001 km. These dates exercise the
        # large variation that would disappear if the scale were mistaken.
        near_new = moon_geocentric(jd_to_centuries(date_to_jd(2000, 1, 6.5)))
        near_full = moon_geocentric(jd_to_centuries(date_to_jd(2000, 1, 21.5)))
        self.assertGreater(near_new["dist_km"], 400000.0)
        self.assertLess(near_full["dist_km"], 380000.0)

    def test_stereographic_projection_round_trip(self):
        for alt_deg, az_deg in [(0.0, 0.0), (45.0, 120.0), (89.0, 359.0)]:
            alt = math.radians(alt_deg)
            az = math.radians(az_deg)
            x, y, radius = stereographic_project(alt, az)
            recovered_alt, recovered_az = stereographic_deproject(x, y)
            self.assertAlmostEqual(alt, recovered_alt, places=9)
            self.assertAlmostEqual(
                math.sin(az), math.sin(recovered_az), places=9
            )
            self.assertAlmostEqual(
                math.cos(az), math.cos(recovered_az), places=9
            )
            self.assertAlmostEqual(radius, math.hypot(x, y), places=9)

    def test_starhash_generation_is_label_free(self):
        seal = starhash(
            latitude=47.3769,
            longitude=8.5417,
            date="2026-08-28T22:00:00Z",
            elevation_m=400.0,
            size=512,
        )
        self.assertIsInstance(seal, CelestialSeal)
        self.assertTrue(seal.hash.startswith("STARS-"))
        self.assertIn("<svg", seal.svg)
        self.assertIn("</svg>", seal.svg)
        self.assertIn('id="stars"', seal.svg)
        self.assertIn('id="planets"', seal.svg)
        self.assertNotIn(seal.hash, seal.svg)
        self.assertEqual(len(seal.stars), 457)
        self.assertGreater(len(seal.points), 3)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            starhash(latitude=91.0, longitude=0.0, date=2451545.0)
        with self.assertRaises(ValueError):
            starhash(latitude=0.0, longitude=181.0, date=2451545.0)
        with self.assertRaises(ValueError):
            starhash(latitude=0.0, longitude=0.0, date=2451545.0, size=16)

    def test_inverse_solver_matches_its_forward_model(self):
        latitude = 37.7749
        longitude = -122.4194
        seal = starhash(
            latitude=latitude,
            longitude=longitude,
            date="2026-06-21T00:00:00Z",
            elevation_m=0.0,
        )
        solution = invert(
            seal.points,
            initial_guess=(latitude + 1.0, longitude - 1.0, seal.julian_day - 0.01),
            elevation_m=seal.elevation_m,
        )
        self.assertTrue(solution["converged"])
        self.assertAlmostEqual(latitude, solution["latitude_deg"], delta=1e-5)
        self.assertAlmostEqual(longitude, solution["longitude_deg"], delta=1e-5)
        self.assertAlmostEqual(seal.julian_day, solution["julian_day"], delta=1e-7)
        self.assertLess(solution["residual_rms"], 1e-8)

    def test_ecliptic_is_one_open_arc(self):
        seal = starhash(47.3769, 8.5417, "2026-08-28T22:00:00Z", size=512)
        track = re.search(r'<polyline[^>]* points="([^"]+)"', seal.svg).group(1)
        points = [tuple(map(float, pair.split(","))) for pair in track.split()]
        longest = max(math.dist(a, b) for a, b in zip(points, points[1:]))
        self.assertLess(longest, 40.0)


class TestSignedSeals(unittest.TestCase):
    PLACE = dict(latitude=47.3769, longitude=8.5417, elevation_m=400.0)
    WHEN = "2026-08-28T22:00:00Z"

    def test_seal_is_a_drawing_and_nothing_else(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        self.assertTrue(seal.digest.startswith("STARS-"))
        for hidden in ("<metadata", "<text", "<!--", "<title", "<desc", "data-", "planet-"):
            self.assertNotIn(hidden, seal.svg)
        for private in (seal.digest, seal.claim["document"]["sha256"], "deed"):
            self.assertNotIn(private, seal.svg)
        # Apart from the ring it is the plain sky.
        plain = starhash(date=self.WHEN, **self.PLACE)
        self.assertEqual(seal.svg.count("<circle"), plain.svg.count("<circle"))

    def test_verify_from_the_drawing(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        result = verify(seal.svg, b"the deed")
        self.assertTrue(result["ok"])
        self.assertEqual([c["ok"] for c in result["checks"]], [True, True, None])
        self.assertAlmostEqual(result["reading"]["latitude"], 47.3769, delta=0.005)
        self.assertTrue(verify(seal.svg)["ok"])
        self.assertFalse(verify(seal.svg, b"another deed")["ok"])

        stated = verify(seal.svg, b"the deed", date=self.WHEN, **self.PLACE)
        self.assertEqual([c["ok"] for c in stated["checks"]], [True, True, True])
        elsewhere = verify(seal.svg, b"the deed", 47.5, 8.5417, self.WHEN)
        self.assertFalse(elsewhere["ok"])
        later = verify(seal.svg, b"the deed", 47.3769, 8.5417, "2026-08-28T22:00:05Z", 400.0)
        self.assertFalse(later["ok"])

    def test_verify_rejects_a_disturbed_sky(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        stars = list(re.finditer(r'<circle cx="([\d.]+)" cy="[\d.]+" r="0\.79"', seal.svg))
        star = stars[len(stars) // 2]
        moved = seal.svg[:star.start(1)] + f"{float(star.group(1)) + 3:.2f}" + seal.svg[star.end(1):]
        checks = {c["check"]: c["ok"] for c in verify(moved, b"the deed")["checks"]}
        self.assertFalse(checks["sky"])
        self.assertFalse(verify("<svg></svg>")["ok"])

    def test_ring_carries_the_document_hash(self):
        import hashlib
        from star_hash.read import parse_drawing
        from star_hash.seal import ring_matches

        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        ring = parse_drawing(seal.svg).document_ring
        self.assertEqual(ring, hashlib.sha256(b"the deed").hexdigest()[:32])
        self.assertTrue(ring_matches(ring, b"the deed"))
        self.assertFalse(ring_matches(ring, b"another deed"))
        self.assertEqual(read_seal(seal.svg).document_ring, ring)
        self.assertIsNone(parse_drawing(starhash(date=self.WHEN, **self.PLACE).svg).document_ring)

    def test_same_inputs_give_the_same_seal(self):
        a = sign(b"x", date=self.WHEN, **self.PLACE)
        b = sign(b"x", date="2026-08-29T00:00:00+02:00", **self.PLACE)
        self.assertEqual(a.svg, b.svg)
        self.assertNotEqual(a.svg, sign(b"y", date=self.WHEN, **self.PLACE).svg)

    def test_every_planet_is_known_by_its_sign(self):
        seal = starhash(35.0, 25.0, "2022-06-24T05:30:00Z")
        up = {p["name"] for p in seal.planets if p["alt_rad"] > 0}
        self.assertEqual(up, {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"})
        from star_hash.read import parse_drawing
        self.assertTrue(up <= set(parse_drawing(seal.svg).bodies))

    def test_drawing_alone_gives_back_place_and_time(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        reading = read_seal(seal.svg)
        self.assertTrue(reading.converged)
        self.assertIn("Moon", reading.bodies)
        self.assertAlmostEqual(reading.latitude, 47.3769, delta=0.005)
        self.assertAlmostEqual(reading.longitude, 8.5417, delta=0.2)
        self.assertAlmostEqual(reading.julian_day, 2461281.4166667, delta=60.0 / 86400.0)
        self.assertEqual(reading.time[:16], "2026-08-28T22:00")

    def test_drawing_of_another_century_and_hemisphere(self):
        seal = starhash(-33.8688, 151.2093, "1969-07-20T20:17:00Z")
        reading = read_seal(seal.svg)
        self.assertAlmostEqual(reading.latitude, -33.8688, delta=0.005)
        error = (reading.longitude - 151.2093 + 180.0) % 360.0 - 180.0
        self.assertLess(abs(error), max(0.2, 5.0 * reading.sigma_longitude_deg))
        self.assertLess(
            abs(reading.julian_day - seal.julian_day) * 86400.0,
            max(60.0, 5.0 * reading.sigma_time_s),
        )

    def test_command_line(self):
        quiet = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            document = os.path.join(folder, "deed.txt")
            with open(document, "w") as handle:
                handle.write("the deed")
            args = ["--lat", "47.3769", "--lon", "8.5417", "--date", self.WHEN]
            self.assertEqual(cli_main(["sign", document] + args), 0)
            seal_path = document + ".seal.svg"
            self.assertEqual(cli_main(["verify", seal_path, document]), 0)
            self.assertEqual(cli_main(["verify", seal_path, document] + args), 0)
            self.assertEqual(cli_main(["verify", seal_path, "--lat", "1"]), 2)
            self.assertEqual(cli_main(["read", seal_path, document]), 0)
            with open(document, "a") as handle:
                handle.write("!")
            self.assertEqual(cli_main(["verify", seal_path, document]), 1)
            self.assertEqual(cli_main(["read", seal_path, document]), 1)
            self.assertEqual(cli_main(["verify", os.path.join(folder, "missing.svg")]), 2)


if __name__ == "__main__":
    unittest.main()
