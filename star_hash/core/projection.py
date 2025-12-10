import math
from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime
import astronomy

@dataclass
class ProjectedBody:
    x: float      # Normalized -1 to 1 (horizon boundary)
    y: float
    mag: float
    name: str
    type: str     # 'star' or 'planet'
    phase: float = 1.0  # Illuminated fraction (0.0 to 1.0)
    ra_rad: float = 0.0 # For potential debugging/decoding
    dec_rad: float = 0.0

def _degrees_to_radians(deg: float) -> float:
    return deg * (math.pi / 180.0)

def _hours_to_radians(hrs: float) -> float:
    return hrs * (math.pi / 12.0)

def calculate_projection(
    bodies: List[Tuple[float, float, float, str, str]], # ra(hrs), dec(deg), mag, name, type
    lat: float, # degrees
    lon: float, # degrees
    time: datetime
) -> List[ProjectedBody]:
    """
    Projects celestial bodies onto a stereographic plane centered on the Zenith.
    Returns bodies with x,y in range roughly [-1, 1].
    """
    
    # 1. Calculate Local Sidereal Time
    astro_time = astronomy.Time.Make(
        time.year, time.month, time.day, time.hour, time.minute, time.second
    )
    gmst = astronomy.SiderealTime(astro_time) # Greenwich Mean Sidereal Time in hours
    lst_hours = gmst + (lon / 15.0)
    lst_rad = _hours_to_radians(lst_hours)
    
    lat_rad = _degrees_to_radians(lat)
    
    projected = []
    
    for ra_hours, dec_deg, mag, name, btype in bodies:
        ra_rad = _hours_to_radians(ra_hours)
        dec_rad = _degrees_to_radians(dec_deg)
        
        # Hour Angle
        ha_rad = lst_rad - ra_rad
        
        # Equatorial to Horizontal
        # sin(Alt)
        sin_alt = math.sin(lat_rad) * math.sin(dec_rad) + \
                  math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
        
        # Clamp for asin safety
        sin_alt = max(-1.0, min(1.0, sin_alt))
        alt_rad = math.asin(sin_alt)
        
        # Always include Sun and Moon regardless of altitude calculations,
        # but for others skip if below horizon.
        is_key_body = name in ('Sun', 'Moon')
        
        if alt_rad < 0 and not is_key_body:
            continue
            
        # Azimuth
        # y = -cos(Dec) * sin(HA)
        # x = sin(Dec)*cos(Lat) - cos(Dec)*sin(Lat)*cos(HA)
        # Az = atan2(y, x)
        y_az = -math.cos(dec_rad) * math.sin(ha_rad)
        x_az = math.sin(dec_rad) * math.cos(lat_rad) - \
               math.cos(dec_rad) * math.sin(lat_rad) * math.cos(ha_rad)
        az_rad = math.atan2(y_az, x_az)
        
        # Stereographic Projection
        # r = k * tan((90 - Alt) / 2) -> Zenith is 0, Horizon is 1 (if k=1, tan(45deg)=1)
        # Zenith distance z = pi/2 - alt
        z = (math.pi / 2.0) - alt_rad
        
        # If body is extremely far below horizon (nadir), tan(z/2) blows up (z -> pi).
        # We clamp r for key bodies that are invisible to avoid math artifacts?
        # Actually tan(pi/2) is infinity.
        # If alt = -90, z = 180 (pi). tan(90) = inf.
        if z >= math.pi - 1e-5:
             r = 1000.0 # Just far away
        else:
             r = math.tan(z / 2.0)
        
        # Convert Polar (r, az) to Cartesian (x, y)
        px = r * math.sin(az_rad)
        py = -r * math.cos(az_rad)
        
        # Phase Calculation
        phase = 1.0
        if name == 'Moon':
             # Calculate illumination
             # We need to call astronomy engine again or pass it in?
             # For performance, calling it here is fine (once per stamp)
             # But 'time' here is python datetime.
             astro_time_local = astronomy.Time.Make(
                time.year, time.month, time.day, time.hour, time.minute, time.second
             )
             illum = astronomy.Illumination(astronomy.Body.Moon, astro_time_local)
             phase = illum.phase_fraction
        
        projected.append(ProjectedBody(px, py, mag, name, btype, phase, ra_rad, dec_rad))
        
    return projected
