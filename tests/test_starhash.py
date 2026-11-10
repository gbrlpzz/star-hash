"""Small deterministic checks for Starhash's geometry and reductions."""
import contextlib
import io
import math
import os
import re
import tempfile
import unittest

from star_hash import CelestialSeal, invert, read_claim, read_seal, sign, starhash, verify
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

    def test_sign_and_verify_round_trip(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        self.assertTrue(seal.digest.startswith("STARS-"))
        self.assertEqual(read_claim(seal.svg)["time"], self.WHEN)
        result = verify(seal.svg, b"the deed")
        self.assertTrue(result["ok"])
        self.assertEqual([c["ok"] for c in result["checks"]], [True, True, True, True])
        # Without the document the seal is still self-consistent.
        self.assertTrue(verify(seal.svg)["ok"])
        # The drawing is the plain sky; the record is not drawn.
        plain = starhash(date=self.WHEN, **self.PLACE)
        self.assertEqual(seal.svg.count("<circle"), plain.svg.count("<circle"))
        self.assertNotIn("<text", seal.svg)

    def test_ring_carries_the_document_hash_without_the_record(self):
        import hashlib
        from star_hash.read import parse_drawing
        from star_hash.seal import ring_matches

        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        printed = re.sub(r"<metadata.*?</metadata>", "", seal.svg, flags=re.S)
        ring = parse_drawing(printed).document_ring
        self.assertEqual(ring, hashlib.sha256(b"the deed").hexdigest()[:32])
        self.assertTrue(ring_matches(ring, b"the deed"))
        self.assertFalse(ring_matches(ring, b"another deed"))
        self.assertEqual(read_seal(printed).document_ring, ring)
        # The bare sky has no ring, and a ring for another document fails verify.
        self.assertIsNone(parse_drawing(starhash(date=self.WHEN, **self.PLACE).svg).document_ring)
        other = sign(b"another deed", date=self.WHEN, **self.PLACE)
        record = re.search(r"<metadata.*?</metadata>", seal.svg, re.S).group(0)
        regrafted = re.sub(r"<metadata.*?</metadata>", lambda _: record, other.svg, flags=re.S)
        checks = {c["check"]: c["ok"] for c in verify(regrafted, b"the deed")["checks"]}
        self.assertFalse(checks["ring"])

    def test_same_inputs_give_the_same_seal(self):
        a = sign(b"x", date=self.WHEN, **self.PLACE)
        b = sign(b"x", date="2026-08-29T00:00:00+02:00", **self.PLACE)
        self.assertEqual(a.svg, b.svg)
        self.assertNotEqual(a.digest, sign(b"y", date=self.WHEN, **self.PLACE).digest)

    def test_verify_rejects_changes(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        self.assertFalse(verify(seal.svg, b"another deed")["ok"])

        moved_claim = seal.svg.replace('"latitude": 47.3769', '"latitude": 48.3769')
        self.assertNotEqual(moved_claim, seal.svg)
        self.assertFalse(verify(moved_claim)["ok"])

        # Swap in the drawing of another night under the same record.
        other = sign(b"the deed", date="2026-08-29T22:00:00Z", **self.PLACE)
        record = re.search(r"<metadata.*?</metadata>", seal.svg, re.S).group(0)
        swapped = re.sub(r"<metadata.*?</metadata>", lambda _: record, other.svg, flags=re.S)
        checks = {c["check"]: c["ok"] for c in verify(swapped)["checks"]}
        self.assertTrue(checks["record"])
        self.assertFalse(checks["sky"])

        self.assertFalse(verify(starhash(date=self.WHEN, **self.PLACE).svg)["ok"])

    def test_drawing_alone_gives_back_place_and_time(self):
        seal = sign(b"the deed", date=self.WHEN, **self.PLACE)
        drawing_only = re.sub(r"<metadata.*?</metadata>", "", seal.svg, flags=re.S)
        reading = read_seal(drawing_only)
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
            self.assertEqual(cli_main(["read", seal_path, document]), 0)
            with open(document, "a") as handle:
                handle.write("!")
            self.assertEqual(cli_main(["verify", seal_path, document]), 1)
            self.assertEqual(cli_main(["read", seal_path, document]), 1)
            self.assertEqual(cli_main(["verify", os.path.join(folder, "missing.svg")]), 2)


if __name__ == "__main__":
    unittest.main()
