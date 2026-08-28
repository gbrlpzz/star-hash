"""
tests/test_starhash.py
~~~~~~~~~~~~~~~~~~~~~~
Unit tests & astrometric verification for starhash.
"""
import math
import os
import unittest
from datetime import datetime, timezone

from star_hash import starhash, invert, CelestialSeal
from star_hash.ephemeris import date_to_jd, sun_geocentric, moon_geocentric, planet_geocentric
from star_hash.projection import stereographic_project, stereographic_deproject

class TestStarhash(unittest.TestCase):

    def test_j2000_julian_day(self):
        jd = date_to_jd(2000, 1, 1.5)
        self.assertAlmostEqual(jd, 2451545.0, places=4)

    def test_sun_equinox(self):
        # J2000.0 epoch
        sun = sun_geocentric(0.0)
        self.assertAlmostEqual(sun["dist_au"], 0.9833, places=3)
        self.assertAlmostEqual(sun["ra_rad"] * 180.0 / math.pi / 15.0, 18.752, places=2)

    def test_moon_phase_known_date(self):
        # Moon at J2000.0 was waning crescent ~23%
        moon = moon_geocentric(0.0)
        self.assertTrue(0.20 <= moon["phase"] <= 0.26)
        self.assertTrue(370000.0 <= moon["dist_km"] <= 405000.0)

    def test_stereographic_projection_conformal_inversion(self):
        alt = 45.0 * math.pi / 180.0
        az = 120.0 * math.pi / 180.0
        x, y, r = stereographic_project(alt, az)

        # Invert
        rec_alt, rec_az = stereographic_deproject(x, y)
        self.assertAlmostEqual(alt, rec_alt, places=6)
        self.assertAlmostEqual(az, rec_az, places=6)

    def test_starhash_generation(self):
        seal = starhash(
            latitude=47.3769,
            longitude=8.5417,
            date="2026-08-28T12:00:00Z",
            elevation_m=400.0,
            size=512,
        )
        self.assertIsInstance(seal, CelestialSeal)
        self.assertTrue(seal.hash.startswith("STARS-"))
        self.assertIn("<svg", seal.svg)
        self.assertIn("</svg>", seal.svg)
        self.assertIn('id="stars"', seal.svg)
        self.assertIn('id="planets"', seal.svg)
        self.assertTrue(len(seal.stars) > 0)

    def test_inverse_solver(self):
        # Generate known seal
        lat = 37.7749
        lon = -122.4194
        date = "2026-06-21T00:00:00Z"
        seal = starhash(latitude=lat, longitude=lon, date=date)

        # Invert from visible points
        solution = invert(seal.points, initial_guess=(lat + 1.0, lon - 1.0, seal.julian_day - 0.01))
        self.assertAlmostEqual(lat, solution["latitude_deg"], delta=1.5)
        self.assertAlmostEqual(seal.julian_day, solution["julian_day"], delta=0.05)

if __name__ == "__main__":
    unittest.main()
