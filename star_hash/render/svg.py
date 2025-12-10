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
    
    dwg = svgwrite.Drawing(output_path, profile='tiny', size=(size, size))
    
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
    
    for body in projected_visible:
        sx = center + body.x * radius_path
        sy = center + body.y * radius_path
        pt = ONE_POINT_PX * scale
        
        if body.name == 'Sun':
            _render_sun(dwg, sx, sy, pt)
        elif body.name == 'Moon':
            # Pass angle and phase
            # Phase is attached to the body now
            phase = getattr(body, 'phase', 1.0) # Default to full if missing
            _render_moon_dynamic(dwg, sx, sy, pt, moon_angle_deg, phase)
        elif body.type == 'planet':
            # Planet: r=1.2pt, stroke=0.4pt
            dwg.add(dwg.circle(
                center=(sx, sy), 
                r=1.2 * pt, 
                fill='white', 
                stroke='black', 
                stroke_width=0.4 * pt
            ))
        else:
            # Stars
            r = max(0.25, 1.1 - (body.mag * 0.2)) * pt
            dwg.add(dwg.circle(center=(sx, sy), r=r, fill='black'))
    
    dwg.save()

def _render_sun(dwg, x, y, pt):
    """Ancient sun ☉"""
    dwg.add(dwg.circle(
        center=(x, y), 
        r=3.2 * pt, 
        fill='white', 
        stroke='black', 
        stroke_width=0.8 * pt
    ))
    dwg.add(dwg.circle(center=(x, y), r=1.0 * pt, fill='black'))

def _render_moon_dynamic(dwg, x, y, pt, angle_deg, phase):
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
    # r=2.8pt
    r_moon = 2.8 * pt
    g.add(dwg.circle(center=(x, y), r=r_moon, fill='black'))
    
    # 2. Masking (White) to create Crescent
    # Logic:
    # If Phase = 0 (New), Mask covers completely (Offset = 0).
    # If Phase = 0.5 (Quarter), Mask is offset by R?
    # If Phase = 1 (Full), Mask is far away or small.
    # Simple aesthetic approximation:
    # We slide a white circle (slightly smaller) across the black one.
    # Offset R_mask such that:
    # 0.0 -> concentric (black ring? or black hole?)
    # Actually, new moon is invisible (black on white? no, white on white?)
    # "Ancient" new moon is usually a black disk or circle.
    # Let's assume we draw the illuminated part as white? No, user wants light mode: Black ink.
    # So "Moon" usually means the dark body or the lit crescent?
    # In light mode, Black usually represents Light (Stars are black dots).
    # So a Crescent Moon should be a Black Crescent.
    # A Full Moon should be a Black Circle?
    # Yes.
    # So:
    # Draw Black Circle.
    # Cut away the "Shadow" with White Circle?
    # No, that's inverted. The "Shadow" is the unlit part (which matches the sky color -> White).
    # So we are drawing the SHADOW as White.
    # Wait.
    # If the Moon is a Black Crescent, the Black part is the Lit part.
    # The White part is the Unlit part.
    # So we draw a Black Disk (representing Full Lit).
    # Then we overlay a White Disk (representing the Shadow).
    # As the moon waxes (New -> Full):
    # New: Shadow covers everything (White circle on top of Black circle).
    # Full: Shadow is gone (White circle moves away).
    # Direction:
    # The Lit Part (Belly) points to Sun.
    # The Shadow Part (White Mask) is clearly *away* from the Sun.
    # So if `angle_deg` points to Sun (Right, 0 deg), the Crescent Belly is Right.
    # The Mask should be on the Left.
    # So Mask Offset should be negative x relative to rotation.
    
    # Mapping Phase (0..1) to Offset:
    # New (0.0): Offset = 0 (Concentric).
    # Full (1.0): Offset >= 2*R (Completely clear).
    # Phase 0.5: Offset ~ R?
    
    # Let's try linear: offset = phase * 2.5 * r_moon * (some direction)
    
    # But wait, gibbous (bulging) moon?
    # A simple circle mask can't produce a convex gibbous shape (it always makes a concave bite).
    # To draw a Gibbous moon with circles is hard (needs intersecting ellipses or just 2 circles doesn't work).
    # BUT, for a "Stamp" / "Cipher", a Crescent is the iconic symbol.
    # The user asked for "moon crescent based on actual moon phases".
    # Usually, if it's Gibbous, symbols often just show a fat crescent or full circle.
    # Let's stick to the Crescent aesthetic for phases < 0.5.
    # For phases > 0.5 (Gibbous), maybe just show Full Circle?
    # Or keep the "Bite" getting smaller?
    # If we shift the mask further, the bite gets smaller, approaching Full.
    # This works for Gibbous too (it just looks like a fat crescent).
    
    r_mask = r_moon * 0.9 # Slightly smaller mask so "New Moon" has a thin ring? 
    # Or if New Moon is invisible, r_mask >= r_moon.
    # Let's make r_mask = r_moon for simplicity.
    
    # Calculate offset
    # At phase 0 (New), offset=0 -> White covers Black -> Invisible (except stroke artifacts).
    # At phase 0.5 (Quarter), offset ~ r_moon.
    # At phase 1.0 (Full), offset >= 2*r_moon.
    
    offset_dist = phase * 2.2 * r_moon
    
    # Direction: Away from Sun. 
    # angle_deg rotates +X to Sun.
    # So Mask should be at -X (Left).
    
    mask_x = x - (r_moon * 1.1) + offset_dist 
    # Wait, if phase=0 (New), offset=0. We want mask centered.
    # So mask_x should be x.
    # As phase increases, mask moves Right (towards Sun)?
    # If mask moves Right, it reveals the Left side (Away from Sun).
    # That is WRONG.
    # We want to reveal the Right side (Towards Sun).
    # So Mask must move LEFT (Away from Sun).
    
    mask_offset = (phase * 2.5 * r_moon)
    # Start (Phase 0): Mask Centered (x).
    # End (Phase 1): Mask moved Left (-2.5r).
    # Real logic:
    # Phase 0: Mask at x. (Covered)
    # Phase 1: Mask at x - 2.5r. (Reveals Right side).
    
    target_mask_x = x - (phase * 2.5 * r_moon)
    
    # HOWEVER: White Mask on Black Disk makes a Crescent pointing RIGHT (Sun). Correct.
    # But wait, if we just simply move a circle, we only get "Cremona" shapes.
    # We never get Gibbous (convex).
    # We will accept this stylistic limitation:
    # The "Phase" indicates how FAT the crescent is.
    # Full moon = Full Black Circle.
    # Half moon = Half Circle.
    # Crescent = Thin Crescent.
    # The "Gibbous" will just look like a very fat crescent (almost full).
    
    # Refined logic:
    # r_mask same as r_moon.
    # new_moon_offset (Phase 0) = 0.
    # full_moon_offset (Phase 1) = 2.2 * r_moon (mask completely off body).
    
    offset = phase * 3.0 * r_moon # Move it out generously
    
    # We want to move mask AWAY from sun (Left, -x in rotated frame).
    # So mask center = (x - offset, y) ? No, that exposes LEFT side.
    # We want to expose RIGHT side (Sun).
    # So Mask must move LEFT.
    # YES.
    # But wait.
    # Phase 0: Mask at Center.
    # Phase 1: Mask Far Left.
    # Interpolation?
    # Phase 0.5: Mask at x - r_moon?
    # This leaves the right half exposed? Yes.
    
    # Wait, phase 0.5 means 50% illuminated?
    # A simple shift of r_moon gives roughly half area? Geometrically yes roughly.
    
    # But wait, Astronomy engine Phase 0 -> New. Phase 0.5 -> Full? 
    # Check debug output.
    # Output: "Phase Fraction: 0.64".
    # This is 64% illuminated (Gibbous).
    # Phase Fraction 1.0 = Full.
    # Phase Fraction 0.0 = New.
    
    # So logic:
    # r_mask = r_moon * 0.95 (to leave a thin ring at New Moon? Optional).
    # Let's say New Moon = Invisible.
    r_mask = r_moon * 1.05 # Slightly larger to cover fully
    
    current_offset = phase * 3.0 * r_moon
    
    # Direction: Away from Sun.
    # Sun is at +X (0 deg).
    # Mask moves to -X (180 deg).
    
    # Since we apply rotation to the group, we can just work in local coords relative to x,y.
    # The group rotates (x,y) around (x,y) ?? No.
    # `transform=rotate(deg, x, y)` rotates around the point (x,y).
    # So +X in local coords is "Towards Sun".
    # We draw Black Moon at (x,y).
    # We draw White Mask at (x - current_offset, y) ??
    # Let's trace.
    # mask at x=0. covers moon.
    # mask at x=-10. reveals right side of moon (+x side).
    # +x side is towards sun.
    # Correct.
    
    # But wait, `phase` 0.64 is getting closer to full.
    # So mask should be further away.
    # At phase 0, offset should be 0.
    # At phase 1, offset should be large.
    
    # Implementation:
    mask_x = x - (phase * 2.5 * r_moon)
    
    # Special fix for New Moon (Phase < 0.05):
    # Just don't draw anything? or draw circle stroke?
    # Let's just let the mask do its job (it will cover it).
    
    g.add(dwg.circle(center=(x, y), r=r_moon, fill='black'))
    g.add(dwg.circle(center=(mask_x, y), r=r_mask, fill='white'))
    
    dwg.add(g)

