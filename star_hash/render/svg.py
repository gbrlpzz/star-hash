import svgwrite
import math
from typing import List
from star_hash.core.projection import ProjectedBody

def generate_stamp(
    bodies: List[ProjectedBody],
    output_path: str,
    metadata_text: str = None,
    size: int = 472  # Default: 4cm at 300 DPI (~472.44px)
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
    
    # Border stroke width: Exactly 1pt
    BORDER_WIDTH_PX = ONE_POINT_PX
    
    # Radius logic matching SVG (pixel perfect)
    radius_path = (size / 2.0) - (BORDER_WIDTH_PX / 2.0)
    center = size / 2.0
    inner_r = radius_path * 0.7
    scale = size / 472.0
    
    dwg = svgwrite.Drawing(output_path, profile='full', size=(size, size))
    
    # Horizon Ring
    dwg.add(dwg.circle(
        center=(center, center), 
        r=radius_path, 
        fill='none', 
        stroke='black', 
        stroke_width=BORDER_WIDTH_PX,
        shape_rendering='geometricPrecision'
    ))
    
    # Inner Ring
    dwg.add(dwg.circle(
        center=(center, center), 
        r=inner_r, 
        fill='none', 
        stroke='black', 
        stroke_width=ONE_POINT_PX * 0.15,
        opacity=0.5
    ))
    
    # Zenith Crosshair
    zenith_len = ONE_POINT_PX * 0.8 * scale
    dwg.add(dwg.line(start=(center-zenith_len, center), end=(center+zenith_len, center), stroke='black', stroke_width=ONE_POINT_PX*0.3))
    dwg.add(dwg.line(start=(center, center-zenith_len), end=(center, center+zenith_len), stroke='black', stroke_width=ONE_POINT_PX*0.3))
    
    # 1. Identify Sun and Moon for angle calculation
    # They are in the list (even if r > 1, per updated projection)
    sun_body = next((b for b in bodies if b.name == 'Sun'), None)
    moon_body = next((b for b in bodies if b.name == 'Moon'), None)
    
    moon_angle_deg = 0.0
    if sun_body and moon_body:
        # Calculate angle from Moon to Sun in projection plane
        # y is naturally inverted in SVG processing logic later (sy = center + y*r), 
        # but projection.y includes the flip (-r*cos).
        # So sx, sy are direct cartesian coordinates on the canvas centered at (0,0).
        # We can work in unit coordinates for angle.
        dx = sun_body.x - moon_body.x
        dy = sun_body.y - moon_body.y
        moon_angle_rad = math.atan2(dy, dx)
        moon_angle_deg = math.degrees(moon_angle_rad)
    
    # Filter visible bodies (Stars/Planets inside horizon)
    # Sun/Moon are special: if inside, draw them. If outside, don't.
    # But for Moon, we need its phase info which is on the object.
    
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

    for body in projected_visible:
        sx = center + body.x * radius_path
        sy = center + body.y * radius_path
        pt = ONE_POINT_PX * scale
        
        if body.name == 'Sun':
            _render_sun(dwg, body_group, sx, sy, pt)
        elif body.name == 'Moon':
            phase = getattr(body, 'phase', 1.0)
            _render_moon_dynamic(dwg, body_group, sx, sy, pt, moon_angle_deg, phase)
        elif body.type == 'planet':
            # Planet
            body_group.add(dwg.circle(
                center=(sx, sy), 
                r=1.2 * pt, 
                fill='white', 
                stroke='black', 
                stroke_width=0.4 * pt
            ))
        else:
            # Stars
            r = max(0.25, 1.1 - (body.mag * 0.2)) * pt
            body_group.add(dwg.circle(center=(sx, sy), r=r, fill='black'))
    
    dwg.save()

def _render_sun(dwg, group, x, y, pt):
    """Ancient sun ☉"""
    group.add(dwg.circle(
        center=(x, y), 
        r=3.2 * pt, 
        fill='white', 
        stroke='black', 
        stroke_width=0.8 * pt
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
    
    # 1. Base Disk (Black)
    r_moon = 2.8 * pt
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

