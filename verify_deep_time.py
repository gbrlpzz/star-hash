from datetime import datetime
from types import SimpleNamespace
from star_hash.core.stars import get_stars_for_date
from star_hash.core.projection import calculate_projection
import math

def check_precession_shift():
    t1 = datetime(2025, 12, 10, 12, 0, 0)
    # Python datetime max is year 9999. Use mock for 12025.
    t2 = SimpleNamespace(year=12025, month=12, day=10, hour=12, minute=0, second=0)
    
    print(f"Comparing {t1} vs {t2}")
    
    stars1 = get_stars_for_date(t1)
    stars2 = get_stars_for_date(t2)
    
    # Track Polaris (HIP 11767)
    # Actually my CSV has simple names? Or just indices?
    # Navigation stars have names.
    
    # Find Polaris in list 1
    polaris1 = next((s for s in stars1 if s[3] == "Polaris"), None)
    polaris2 = next((s for s in stars2 if s[3] == "Polaris"), None)
    
    if polaris1 and polaris2:
        # Check coordinates (RA/Dec)
        # Note: stars1/stars2 are tuples: (ra, dec, mag, name, type)
        print(f"Polaris J2025:  RA={polaris1[0]:.4f}h, Dec={polaris1[1]:.4f}d")
        print(f"Polaris J12025: RA={polaris2[0]:.4f}h, Dec={polaris2[1]:.4f}d")
        
        diff_dec = abs(polaris1[1] - polaris2[1])
        print(f"Precession Shift in Dec: {diff_dec:.4f} degrees")
        if diff_dec > 5.0:
            print("PASS: Significant precession detected. Polaris is no longer the Pole Star.")
        else:
            print("FAIL: Precession shift too small?")
    else:
        print("Could not find Polaris in catalog.")

    # Check Vega (HIP 91262) - Future pole star around 14000 AD?
    vega1 = next((s for s in stars1 if s[3] == "Vega"), None)
    vega2 = next((s for s in stars2 if s[3] == "Vega"), None)
    if vega1 and vega2:
        print(f"Vega J2025:  Dec={vega1[1]:.4f}d")
        print(f"Vega J12025: Dec={vega2[1]:.4f}d")

check_precession_shift()
