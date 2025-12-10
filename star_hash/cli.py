import typer
import json
import urllib.request
import os
from datetime import datetime
from typing import Optional
from star_hash.core.stars import get_stars_for_date
from star_hash.core.planets import get_visible_planets
from star_hash.core.projection import calculate_projection
from star_hash.render.svg import generate_stamp

app = typer.Typer()

def get_current_location():
    """Fetches current location via IP geolocation."""
    try:
        with urllib.request.urlopen("http://ip-api.com/json") as url:
            data = json.loads(url.read().decode())
            if data['status'] == 'success':
                return data['lat'], data['lon'], data['city']
    except Exception as e:
        typer.echo(f"Warning: Could not detect location ({e}). Using default Rome.")
    return 41.9028, 12.4964, "Rome"

@app.callback(invoke_without_command=True)
def create(
    lat: Optional[float] = typer.Option(None, help="Latitude in degrees (default: auto-detect)"),
    lon: Optional[float] = typer.Option(None, help="Longitude in degrees (default: auto-detect)"),
    time: Optional[datetime] = typer.Option(None, help="Date/Time (ISO format). Defaults to now."),
    output: Optional[str] = typer.Option(None, help="Output file path (default: Desktop with timestamp)"),
    size: int = typer.Option(472, help="Size in pixels (default: 4cm at 300 DPI)"),
    debug: bool = typer.Option(False, help="Output projection data for verification")
):
    """
    Generates a Star Cipher stamp - a cryptic celestial hash of time and place.
    
    Output: SVG only (transparent background).
    Default size: 4cm @ 300 DPI (472px).
    """
    # Determine source of time
    time_source = "USER-PROVIDED"
    if time is None:
        time = datetime.now()
        time_source = "SYSTEM CLICK"
        
    # Auto-detect location if needed
    loc_source = "USER-PROVIDED"
    city_name = "Unknown"
    
    if lat is None or lon is None:
        typer.echo("📍 Calculating coordinates from IP...")
        lat, lon, city_name = get_current_location()
        loc_source = "IP-Geolocation"

    # Precise logging
    typer.echo("\n--- OBSERVER PARAMETERS ---")
    typer.echo(f"Epoch (UTC): {time.isoformat()} (Source: {time_source})")
    typer.echo(f"Location   : {city_name} [{lat:.4f}, {lon:.4f}] (Source: {loc_source})")
    typer.echo("---------------------------\n")

    # Determine output path
    if output is None:
        desktop = os.path.expanduser("~/Desktop")
        timestamp = time.strftime("%Y%m%d_%H%M")
        safe_city = "".join([c for c in city_name if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        filename = f"cipher_{safe_city}_{timestamp}.svg"
        output = os.path.join(desktop, filename)
    elif not output.endswith('.svg'):
        output += ".svg"
        
    typer.echo(f"Calculating topocentric apparent positions (Epoch J2000 -> {time.date().isoformat()})...")
    
    # 1. Load stars with precession applied to target date
    star_bodies = get_stars_for_date(time)
    
    # 2. Get planets (already computed for date)
    planets = get_visible_planets(time)
    
    # 3. Combine bodies
    bodies = list(star_bodies)
    for p in planets:
        bodies.append((p.ra, p.dec, p.mag, p.name, 'planet'))
        
    typer.echo(f"Catalog: {len(star_bodies)} stars, {len(planets)} planets.")
        
    # 3b. Generate Ecliptic (Solar Path)
    # Simulate Sun position for +/- 6 months to trace the ecliptic of date
    ecliptic_points = []
    import astronomy
    from datetime import timedelta
    
    # Trace 360 degrees. Sun moves ~1 deg/day.
    # We want a smooth line. Step 2 days is fine.
    # Center on current time to ensure no gap near the Sun.
    for d in range(-185, 185, 2):
        sim_time = time + timedelta(days=d)
        astro_time = astronomy.Time.Make(
            sim_time.year, sim_time.month, sim_time.day, 
            sim_time.hour, sim_time.minute, sim_time.second
        )
        # Calculate Sun RA/Dec of date
        pos = astronomy.Equator(astronomy.Body.Sun, astro_time, astronomy.Observer(0,0,0), True, True)
        ecliptic_points.append((pos.ra, pos.dec, 0.0, 'ecliptic', 'ecliptic'))
        
    bodies.extend(ecliptic_points)
    typer.echo(f"Ecliptic: {len(ecliptic_points)} reference points computed.")

    # 4. Project
    projected = calculate_projection(bodies, lat, lon, time)
    visible_count = len(projected)
    typer.echo(f"Stereographic Projection: Zenith-centered. Visible objects: {visible_count}")
    
    # 5. Debug output for reverse-engineering verification
    if debug:
        typer.echo("\n--- CALCULATION DATA ---")
        sun_proj = next((b for b in projected if b.name == 'Sun'), None)
        moon_proj = next((b for b in projected if b.name == 'Moon'), None)
        if sun_proj:
            typer.echo(f"Sun Altitude : x={sun_proj.x:.4f}, y={sun_proj.y:.4f}")
        else:
            typer.echo("Sun Position : [Below Horizon]")
        if moon_proj:
            typer.echo(f"Moon Altitude: x={moon_proj.x:.4f}, y={moon_proj.y:.4f}")
        else:
            typer.echo("Moon Position: [Below Horizon]")
        typer.echo(f"Star Count   : {len([b for b in projected if b.type == 'star'])}")
    
    # 6. Render
    generate_stamp(projected, output, None, size)
    
    typer.echo(f"Cipher generation complete. Artifact written to: {output}")

if __name__ == "__main__":
    app()
