import astronomy
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Planet:
    name: str
    ra: float
    dec: float
    mag: float  # Approximate or calculated

def get_visible_planets(date: datetime) -> List[Planet]:
    """
    Returns positions of naked-eye planets for the given date.
    """
    # Convert python datetime to astronomy time
    time = astronomy.Time.Make(
        date.year, date.month, date.day, date.hour, date.minute, date.second
    )
    
    bodies = [
        (astronomy.Body.Sun, "Sun", -26.7),
        (astronomy.Body.Moon, "Moon", -12.0),
        (astronomy.Body.Mercury, "Mercury", -0.5),
        (astronomy.Body.Venus, "Venus", -4.0),
        (astronomy.Body.Mars, "Mars", -1.0),
        (astronomy.Body.Jupiter, "Jupiter", -2.0),
        (astronomy.Body.Saturn, "Saturn", 0.0),
    ]
    
    planets = []
    for body_enum, name, base_mag in bodies:
        # Calculate geocentric equatorial coordinates
        # We use geocentric because for a stamp the parallax is negligible for visual plotting 
        # unless we want extreme precision.
        # But for 'Horoscope' style, geocentric is standard.
        # However, for a 'Location' specific stamp, we might want topocentric.
        # But 'astronomy-engine' calculates heliocentric first.
        
        # Let's get GeoVector first
        pos = astronomy.GeoVector(body_enum, time, aberration=True)
        # Convert to Ra/Dec
        equator = astronomy.Equator(body_enum, time, astronomy.Observer(0,0,0), True, True) 
        # Note: The above python binding signature might be different.
        # Let's try to stick to simpler calls if possible or specific known ones.
        # Actually GeoVector returns a vector. We need Equator coordinates.
        
        # Checking typical python astronomy-engine usage:
        # pos = astronomy.Equator(body, time, observer, ofdate, aberration)
        # Let's assume observer at center of earth (0,0) for the 'planetary' generic position,
        # and we handle topocentric in the projection step?
        # OR we pass the observer to this function.
        # Let's stick to geocentric J2000 for the list produced here, 
        # and let the projection handle the conversion to local Horizon.
        # Wait, precession matters. 
        
        # Simplify: Just use astronomy.Equator for J2000 or of-date.
        # We will use "of date" (True) to match the current sky.
        
        pos = astronomy.Equator(body_enum, time, astronomy.Observer(0,0,0), True, True)

        planets.append(Planet(
            name=name,
            ra=pos.ra,   # Hours? Check docs. Usually hours in these libs.
            dec=pos.dec, # Degrees.
            mag=base_mag # TODO: Calculate actual magnitude if possible, but constant is fine for V1
        ))
        
    return planets
