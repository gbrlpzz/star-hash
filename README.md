# Star Hash

**`star-hash`** generates a cryptographic celestial timestamp by projecting the precise astronomical configuration of the sky for a given location and time as an SVG visualization.

The geometric arrangement of celestial bodies encodes spacetime coordinates (latitude, longitude, and time) through their ephemeris positions and observational geometry—no plaintext metadata required.

---

## Scientific Basis

### Coordinate Encoding

The visualization encodes observer coordinates through multiple independent astronomical parameters:

1. **Latitude** — Determined by which stars are visible above the horizon and their altitude distribution
2. **Longitude + Time** — Encoded in the rotation of the celestial sphere (sidereal time)
3. **Date** — The Sun's position along the ecliptic encodes day of year
4. **Epoch** — Axial precession shifts star positions over millennia

### Astronomical Calculations

**Coordinate Systems:**
- Input star positions in J2000.0 equatorial coordinates (RA/Dec)
- Precession transformation to epoch-of-date using IAU 2000/2006 precession model
- Conversion to horizontal coordinates (altitude/azimuth) for observer location
- Stereographic projection centered on local zenith

**Celestial Bodies:**
- **Stars**: 457 stars with V ≤ 4.0 from Yale Bright Star Catalog (BSC5)
- **Planets**: Mercury, Venus, Mars, Jupiter, Saturn (computed via JPL ephemeris)
- **Sun**: Position along ecliptic computed for epoch
- **Moon**: Position and illumination phase

**Time Reference:**  
All times are UTC. Local sidereal time computed from Greenwich Mean Sidereal Time plus longitude correction.

---

## Visual Design

### Projection Geometry

The visualization uses a **zenith-centered stereographic projection**:
- **Center (zenith)**: Observer's overhead point (90° altitude)
- **Horizon ring**: 0° altitude circle
- **Radial distance**: `r = tan(z/2)` where `z` is zenith distance

This projection preserves angular relationships and is conformal (locally angle-preserving).

### Visual Elements

- **Outer border** (1pt): Horizon circle clipboundary
- **Inner reference ring** (0.15pt, 50% opacity): 70% radius marker
- **Local meridian** (dashed): North-south line through zenith
- **Cardinal ticks**: N/S/E/W direction markers
- **Ecliptic path** (0.15pt, 30% opacity): Sun's annual path through stars
- **Stars**: Filled circles sized by visual magnitude (brighter = larger)
- **Planets**: White circles with black stroke, sized by magnitude
- **Sun**: ☉ symbol (circled dot)
- **Moon**: Dynamically oriented crescent showing illumination phase

### Size & Scale

- **Default output**: 456×456px (3.86 cm @ 300 DPI)
- **Star sizing**: `r = max(0.2, 0.65 - mag×0.12) × pt` where pt = 4.17px
  - Magnitude -1.5 (Sirius): ~3.5px
  - Magnitude 4.0 (faintest): ~0.8px
- **Planet sizing**: Magnitude-based, Venus (mag -4.0) largest at ~8.8px
- **Moon**: 6.25px radius (hidden when below horizon to avoid clipping)

---

## Installation

```bash
git clone https://github.com/gbrlpzz/star-hash.git
cd star-hash
pip install -e .
```

Optional - add to PATH:
```bash
mkdir -p ~/.local/bin
ln -sf $(pwd)/.venv/bin/timestamp ~/.local/bin/timestamp
```

---

## Usage

### Current Time & Location
```bash
timestamp
```
Auto-detects location via IP geolocation and uses system time (UTC).

### Specific Event
```bash
timestamp --lat 40.7128 --lon -74.0060 --time "1969-07-20T20:17:00" --output apollo11.svg
```

### Parameters
- `--lat`: Latitude in decimal degrees
- `--lon`: Longitude in decimal degrees  
- `--time`: ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SS)
- `--output`: Output SVG file path
- `--size`: Canvas size in pixels (default: 456)
- `--debug`: Print projection data for verification

---

## Data Sources

### Star Catalog
**Yale Bright Star Catalog, 5th Edition (BSC5)**
- 457 stars with visual magnitude ≤ 4.0
- J2000.0 equatorial coordinates (RA/Dec)
- Covers all stars visible from suburban locations
- Source: Hoffleit & Warren (1991), http://tdc-www.harvard.edu/catalogs/bsc5.html

### Planetary Ephemeris
**`astronomy-engine` Python library**
- JPL Development Ephemeris calculations
- Supports precession, nutation, aberration
- Geocentric equatorial positions
- Source: https://github.com/cosinekitty/astronomy

### Precession Model
**IAU 2000A Precession**
- Accounts for Earth's axial wobble (~26,000 year cycle)
- Transforms J2000.0 coordinates to epoch-of-date
- Ensures accuracy over deep time scales

---

## Technical Details

### Coordinate Transformations

1. **J2000 → Epoch of Date**
   ```
   RA_epoch, Dec_epoch = Precess(RA_J2000, Dec_J2000, target_date)
   ```

2. **Equatorial → Horizontal**
   ```
   LST = GMST + (longitude / 15°)
   HA = LST - RA
   sin(Alt) = sin(Lat)×sin(Dec) + cos(Lat)×cos(Dec)×cos(HA)
   ```

3. **Horizontal → Stereographic**
   ```
   z = 90° - Alt  (zenith distance)
   r = tan(z / 2)
   x = r × sin(Az)
   y = -r × cos(Az)
   ```

### Rendering Order (Back to Front)

1. Horizon circle & reference rings
2. Local meridian & cardinal markers
3. Ecliptic path (clipped to horizon)
4. Stars (faintest to brightest)
5. Planets
6. Moon (if above horizon)
7. Sun

---

## Verification

### Deep Time Precession Test
```bash
python verify_deep_time.py
```
Confirms Polaris declination shift from ~89° (year 2025) to ~46° (year 12025).

### Cross-Reference with Planetarium
Compare output with Stellarium or similar planetarium software:
- Same location coordinates
- Same UTC time (convert to local time in software)
- Verify star positions and planet locations match

---

## Limitations

- **Accuracy**: ~1 arcminute for stars, ~0.1° for planets (sufficient for visual identification)
- **Time resolution**: Limited by visual precision of hand-drawn comparisons
- **Light pollution**: Assumes magnitude 4.0 visibility threshold (suburban skies)
- **Refraction**: Not modeled (introduces ~0.5° error near horizon)
- **Proper motion**: Not included (stars treated as fixed over human timescales)

---

## Scientific References

- Hoffleit, D., & Warren Jr., W. H. (1991). *The Bright Star Catalogue, 5th Edition*. VizieR Online Data Catalog.
- Lieske, J. H., et al. (1977). *Expressions for the Precession Quantities Based upon the IAU (1976) System of Astronomical Constants*. Astronomy and Astrophysics, 58, 1-16.
- Snyder, J. P. (1987). *Map Projections—A Working Manual*. USGS Professional Paper 1395.
- Meeus, J. (1998). *Astronomical Algorithms, 2nd Edition*. Willmann-Bell, Inc.

---

## License

MIT License - See LICENSE file for details.
