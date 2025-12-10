import csv
import math
import pkg_resources
import astronomy
from dataclasses import dataclass
from typing import List
from datetime import datetime

@dataclass
class Star:
    name: str
    ra: float  # Degrees (J2000)
    dec: float # Degrees (J2000)
    mag: float

def load_stars() -> List[Star]:
    """Loads bright stars from the CSV data (J2000 coordinates)."""
    stars = []
    data_path = pkg_resources.resource_filename('star_hash', 'data/navigational_stars.csv')
    
    with open(data_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stars.append(Star(
                name=row['Name'],
                ra=float(row['RA_Degrees']),
                dec=float(row['Dec_Degrees']),
                mag=float(row['Magnitude'])
            ))
    return stars


def precess_star(ra_j2000_deg: float, dec_j2000_deg: float, target_time: datetime) -> tuple:
    """
    Precess star coordinates from J2000 epoch to the target date.
    
    This accounts for Earth's axial precession (~26,000 year cycle).
    Essential for deep-time readability of the cipher.
    
    Returns: (ra_degrees, dec_degrees) for the target date
    """
    astro_time = astronomy.Time.Make(
        target_time.year, target_time.month, target_time.day,
        target_time.hour, target_time.minute, target_time.second
    )
    
    # Convert RA/Dec to radians
    ra_rad = math.radians(ra_j2000_deg)
    dec_rad = math.radians(dec_j2000_deg)
    
    # Convert to unit vector in J2000 equatorial frame
    # Using standard spherical to Cartesian
    cos_dec = math.cos(dec_rad)
    x = cos_dec * math.cos(ra_rad)
    y = cos_dec * math.sin(ra_rad)
    z = math.sin(dec_rad)
    
    # Create a vector in J2000 frame
    vec_eqj = astronomy.Vector(x, y, z, astro_time)
    
    # Get rotation matrix from J2000 (EQJ) to true equator of date (EQD)
    rot = astronomy.Rotation_EQJ_EQD(astro_time)
    
    # Apply rotation
    vec_eqd = astronomy.RotateVector(rot, vec_eqj)
    
    # Convert back to RA/Dec
    # RA = atan2(y, x), Dec = asin(z) for unit vector
    ra_of_date = math.degrees(math.atan2(vec_eqd.y, vec_eqd.x))
    if ra_of_date < 0:
        ra_of_date += 360.0
    dec_of_date = math.degrees(math.asin(vec_eqd.z))
    
    return (ra_of_date, dec_of_date)


def get_stars_for_date(target_time: datetime) -> List[tuple]:
    """
    Load stars and precess their coordinates to the target date.
    
    Returns list of (ra_hours, dec_deg, mag, name, 'star') tuples
    ready for projection.
    """
    stars = load_stars()
    result = []
    
    for star in stars:
        # Precess from J2000 to target date
        ra_deg, dec_deg = precess_star(star.ra, star.dec, target_time)
        
        # Convert RA from degrees to hours
        ra_hours = ra_deg / 15.0
        
        result.append((ra_hours, dec_deg, star.mag, star.name, 'star'))
    
    return result
