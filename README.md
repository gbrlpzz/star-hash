# Star Hash (Timestamp)

`star-hash` (command: `timestamp`) generates a visual cryptographic stamp based on the exact arrangement of celestial bodies for a specific moment and location on Earth.

**It contains no text.** The geometry itself is the data.

## The Method

The stamp encodes coordinates (Latitude, Longitude) and Time (UTC) implicitly through orbital mechanics and spherical astronomy:

1.  **Horizon Ring (Place)**: The outer circle represents the local horizon. The specific set of visible stars uniquely identifies the observer's Latitude.
2.  **Star Positions (Sidereal Time)**: The rotation of the star field relative to the horizon encodes Local Sidereal Time, which correlates Longitude and Time.
3.  **Sun Position (Date & Solar Time)**: The Sun's position along the ecliptic (relative to background stars) encodes the Day of Year. Its altitude/azimuth encodes Solar Time.
4.  **Moon Phase & Position (Lunar Clock)**: The Moon's position and observing angle (phase) provide a secondary "hand" on the clock, cycling every ~27.3 days.
5.  **Planets**: Visible naked-eye planets (Venus, Mars, Jupiter, Saturn) add additional orbital constraints for precision.

### Deep Time Readability
This system is designed to be readable for millennia. It uses **J2000 to "Epoch of Date" precession** (using `astronomy-engine`), shifting star coordinates to account for Earth's axial wobble (~26,000-year cycle).

- **Year 2025**: Polaris is the Pole Star (Dec ~89°).
- **Year 12025**: Polaris has drifted to Dec ~46°. Vega is approaching the pole.

This means the stamp uniquely fingerprint's the **Era**, not just the time of day.

## Installation

```bash
git clone https://github.com/gbrlpzz/star-hash.git
cd star-hash
pip install -e .
```

To use it globally, link the script:
```bash
mkdir -p ~/.local/bin
ln -sf $(pwd)/.venv/bin/timestamp ~/.local/bin/timestamp
```

## Usage

### Timestamp (One-Click)
Generates a unique seal for your **current location** and **now**.

```bash
timestamp
```

**Output:**
```text
📍 Detecting location via IP...
--- TIMESTAMP DATA ---
Time   : 2025-12-10T19:42:01 (SYSTEM CLICK)
Place  : Rome [41.9028, 12.4964] (IP-GEOLOCATION)
----------------------
Cipher saved to ~/Desktop/cipher_Rome_20251210_1942.svg
```

### Manual Control
Generate a seal for a specific historical or future event:

```bash
timestamp --lat 40.7128 --lon -74.0060 --time "1969-07-20T20:17:00" --output apollo11.svg
```

## Specification

- **Format**: SVG (Vector)
- **Size**: Reference 472px (4cm @ 300 DPI) or 354px (3cm @ 300 DPI).
- **Geometry**:
    - **Border**: Exact 1pt stroke.
    - **Background**: Transparent.
    - **Crop**: Tangent to outer border.
- **Symbology**:
    - **Sun**: ☉ (Bronze Age Circled Dot).
    - **Moon**: Crescent (Rotated to face Sun, thickness based on illumination).
    - **Stars**: Scaled by magnitude.

## Verification

To verify the astronomical accuracy, you can run the deep-time simulation check:

```bash
python verify_deep_time.py
```
*(Confirms >40° shift in Polaris over 10,000 years)*.
