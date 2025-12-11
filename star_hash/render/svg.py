import svgwrite
import math
from typing import List
from star_hash.core.projection import ProjectedBody

def generate_stamp(
    bodies: List[ProjectedBody],
    output_path: str,
    metadata_text: str = None,
    size: int = 456  # Default: 3.86cm at 300 DPI (~456px)
):
    """
    Generates a cryptic celestial cipher stamp.
    High-elegance pixel-perfect version.
    
    Refinements:
    - Finer strokes for planetary bodies
    - More subtle proportional scaling for stars (less "clumsy" blobs)
    - Clean geometric relationships
    - Dynamic Moon Phase and Angle
    """
    ONE_POINT_PX = 300.0 / 72.0  # ~4.1667 px
    
    # Visual Hierarchy (Etherial / Ghost)
    # User requested: "even lighter"
    # Primary: 0.3pt (Fine)
    # Secondary: 0.15pt (Hairline/Ghost)
    
    W_PRIMARY   = 0.3 * ONE_POINT_PX 
    W_SECONDARY = 0.15 * ONE_POINT_PX
    
    # Aliases
    W_HEAVY    = W_PRIMARY
    W_MEDIUM   = W_PRIMARY
    W_REGULAR  = W_SECONDARY
    W_FINE     = W_SECONDARY
    W_HAIRLINE = W_SECONDARY
    
    # Border stroke width (Horizon)
    BORDER_WIDTH_PX = W_HEAVY
    
    # Radius logic matching SVG (pixel perfect)
    radius_path = (size / 2.0) - (BORDER_WIDTH_PX / 2.0)
    center = size / 2.0
    inner_r = radius_path * 0.7
    scale = size / 472.0
    
    # Apply scale to all widths relative to canvas size if needed? 
    # The 'scale' var handles the 354 vs 472 sizing.
    # But usually stroke widths should scale with the image size.
    # The constants above are base pixels at 1:1 scale if scale=1?
    # No, ONE_POINT_PX is fixed spacing.
    # If we want the *appearance* of 1pt at 300dpi, we use ONE_POINT_PX.
    # But 'scale' is `size / 472`.
    # Let's scale the strokes by `scale` to maintain relative weight at different output sizes.
    W_HEAVY    *= scale
    W_MEDIUM   *= scale
    W_REGULAR  *= scale
    W_FINE     *= scale
    W_HAIRLINE *= scale
    BORDER_WIDTH_PX = W_HEAVY

    dwg = svgwrite.Drawing(output_path, profile='full', size=(size, size))
    
    # Horizon Ring
    dwg.add(dwg.circle(
        center=(center, center), 
        r=radius_path, 
        fill='none', 
        stroke='black', 
        stroke_width=W_HEAVY,
        shape_rendering='geometricPrecision'
    ))
    
    # Inner Ring (Subtle)
    dwg.add(dwg.circle(
        center=(center, center), 
        r=inner_r, 
        fill='none', 
        stroke='black', 
        stroke_width=W_HAIRLINE,
        opacity=0.5
    ))
    
    # Zenith Crosshair
    zenith_len = ONE_POINT_PX * 0.8 * scale
    dwg.add(dwg.line(start=(center-zenith_len, center), end=(center+zenith_len, center), stroke='black', stroke_width=W_FINE))
    dwg.add(dwg.line(start=(center, center-zenith_len), end=(center, center+zenith_len), stroke='black', stroke_width=W_FINE))
    
    # Local Meridian (North-South Line)
    # North is Up (y-), South is Down (y+). Zenith is Center.
    dwg.add(dwg.line(
        start=(center, center - radius_path), 
        end=(center, center + radius_path), 
        stroke='black', 
        stroke_width=W_HAIRLINE, 
        stroke_dasharray=f"{ONE_POINT_PX*scale*0.5},{ONE_POINT_PX*scale*2}",
        opacity=0.4
    ))
    
    # Cardinal Ticks (N, E, S, W)
    tick_len = ONE_POINT_PX * 1.5 * scale
    cardinals = [
        (center, center - radius_path), # N
        (center, center + radius_path), # S
        (center + radius_path, center), # E
        (center - radius_path, center)  # W
    ]
    for cx, cy in cardinals:
        vx, vy = cx - center, cy - center
        dist = (vx**2 + vy**2)**0.5
        vx, vy = vx/dist, vy/dist
        p1 = (cx, cy)
        p2 = (cx - vx*tick_len, cy - vy*tick_len)
        dwg.add(dwg.line(start=p1, end=p2, stroke='black', stroke_width=W_MEDIUM))
    
    # 1. Identify Sun and Moon for angle calculation
    sun_body = next((b for b in bodies if b.name == 'Sun'), None)
    moon_body = next((b for b in bodies if b.name == 'Moon'), None)
    
    moon_angle_deg = 0.0
    if sun_body and moon_body:
        dx = sun_body.x - moon_body.x
        dy = sun_body.y - moon_body.y
        moon_angle_deg = math.degrees(math.atan2(dy, dx))
    
    # Filter visible bodies
    projected_visible = []
    
    for b in bodies:
        r_sq = b.x**2 + b.y**2
        if r_sq**0.5 <= 1.0:
            projected_visible.append(b)
            
    projected_visible.sort(key=lambda b: b.mag, reverse=True)
    
    # Define Clip Path (Inner edge of the border)
    # Border stroke is centered at radius_path with width BORDER_WIDTH_PX
    # Inner edge = radius_path - (BORDER_WIDTH_PX / 2.0)
    clip_r = radius_path - (BORDER_WIDTH_PX / 2.0)
    
    # Add clip definition
    clip_id = "horizon_clip"
    clip = dwg.clipPath(id=clip_id)
    clip.add(dwg.circle(center=(center, center), r=clip_r))
    dwg.defs.add(clip)
    
    # Create group for bodies with clip
    body_group = dwg.g(clip_path=f"url(#{clip_id})")
    dwg.add(body_group)

    # 0. Draw Ecliptic Path (Solar Path)
    ecliptic_points = [b for b in bodies if b.type == 'ecliptic']
    if ecliptic_points:
        ecl_coords = []
        for p in ecliptic_points:
            sx = center + p.x * radius_path
            sy = center + p.y * radius_path
            ecl_coords.append((sx, sy))
        
        body_group.add(dwg.polyline(
            points=ecl_coords,
            fill='none',
            stroke='black',
            stroke_width=W_HAIRLINE,
            stroke_dasharray=f"{ONE_POINT_PX*scale},{ONE_POINT_PX*scale*2}",
            opacity=0.6
        ))

    
    # Render Moon FIRST (backmost layer) to prevent covering other objects
    moon_bodies = [b for b in projected_visible if b.name == 'Moon']
    if moon_bodies:
        moon = moon_bodies[0]
        sx = center + moon.x * radius_path
        sy = center + moon.y * radius_path
        pt = ONE_POINT_PX * scale
        phase = getattr(moon, 'phase', 1.0)
        _render_moon_dynamic(dwg, body_group, sx, sy, pt, moon_angle_deg, phase)
    
    # Then render all other bodies (stars, planets, Sun)
    for body in projected_visible:
        if body.type == 'ecliptic' or body.name == 'Moon':
            continue

        sx = center + body.x * radius_path
        sy = center + body.y * radius_path
        pt = ONE_POINT_PX * scale
        
        if body.name == 'Sun':
            _render_sun(dwg, body_group, sx, sy, pt, W_MEDIUM)
        elif body.type == 'planet':
            # Planet (magnitude-based sizing)
            planet_r = max(0.8, 1.5 - (body.mag * 0.15)) * pt
            body_group.add(dwg.circle(
                center=(sx, sy), 
                r=planet_r, 
                fill='white', 
                stroke='black', 
                stroke_width=W_REGULAR
            ))
        else:
            # Stars (Enhanced hierarchy)
            r = max(0.2, 0.65 - (body.mag * 0.12)) * pt
            body_group.add(dwg.circle(center=(sx, sy), r=r, fill='black'))
    
    dwg.save()

def _render_sun(dwg, group, x, y, pt, stroke_w):
    """Ancient sun ☉"""
    group.add(dwg.circle(
        center=(x, y), 
        r=3.2 * pt, 
        fill='white', 
        stroke='black', 
        stroke_width=stroke_w
    ))
    group.add(dwg.circle(center=(x, y), r=1.0 * pt, fill='black'))

def _render_moon_dynamic(dwg, group, x, y, pt, angle_deg, phase):
    """
    Renders Moon Phase.
    x, y: Center position
    pt: Scale unit
    angle_deg: Rotation angle (direction to Sun)
    phase: Illuminated fraction (0.0 to 1.0)
    """
    # Group to handle rotation
    # center is (x,y)
    g = dwg.g(transform=f"rotate({angle_deg}, {x}, {y})")
    
    # 1. Base Disk (Black - reduced size)
    r_moon = 1.5 * pt  # 6.25px at default scale
    g.add(dwg.circle(center=(x, y), r=r_moon, fill='black'))
    
    # 2. Masking (White) to create Crescent
    # Logic:
    # Phase 0 (New): Offset 0 (Covers completely)
    # Phase 1 (Full): Offset 2.5*R (Reveals completely)
    # Mask moves Away from Sun (Left, -X) to reveal Right side (Sun side).
    
    r_mask = r_moon * 1.05 # Slightly larger to ensure full coverage
    
    # Linear shift for now
    shift = phase * 2.5 * r_moon
    
    # Target X for mask (moving left from center)
    mask_x = x - shift
    
    g.add(dwg.circle(center=(mask_x, y), r=r_mask, fill='white'))
    
    group.add(g)

