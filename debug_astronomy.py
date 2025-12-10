try:
    import astronomy
    print("Astronomy imported")
    time = astronomy.Time.Make(2023, 12, 10, 12, 0, 0)
    print(f"Time: {time}")
    
    # Check geo vector
    pos = astronomy.GeoVector(astronomy.Body.Jupiter, time, True)
    print(f"Jupiter Vector: {pos}")
    
    # Check Equator
    obs = astronomy.Observer(0, 0, 0)
    equator = astronomy.Equator(astronomy.Body.Jupiter, time, obs, True, True)
    print(f"Jupiter RA: {equator.ra}, Dec: {equator.dec}")
    
    # Check Sidereal Time
    lst = astronomy.SiderealTime(time)
    print(f"LST (Greenwich): {lst}")

except Exception as e:
    print(f"Error: {e}")
