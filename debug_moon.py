import astronomy
from datetime import datetime

t = astronomy.Time.Make(2025, 12, 10, 12, 0, 0)
illum = astronomy.Illumination(astronomy.Body.Moon, t)
print(f"Phase Angle: {illum.phase_angle}")
print(f"Phase Fraction: {illum.phase_fraction}")
print(f"Mag: {illum.mag}")

# Check Sun position vs Moon position vector
sun = astronomy.GeoVector(astronomy.Body.Sun, t, True)
moon = astronomy.GeoVector(astronomy.Body.Moon, t, True)
print(f"Sun: {sun.x}, {sun.y}, {sun.z}")
print(f"Moon: {moon.x}, {moon.y}, {moon.z}")
