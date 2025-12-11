#!/usr/bin/env python3
import csv

def parse_bsc5_line(line):
    if len(line) < 197:
        return None
    try:
        hr_str = line[0:4].strip()
        if not hr_str:
            return None
        hr = int(hr_str)
        name = line[4:14].strip()
        ra_h = float(line[75:77].strip() or 0)
        ra_m = float(line[77:79].strip() or 0)
        ra_s = float(line[79:83].strip() or 0)
        ra_deg = (ra_h + ra_m/60.0 + ra_s/3600.0) * 15.0
        dec_sign = line[83]
        dec_d = float(line[84:86].strip() or 0)
        dec_m = float(line[86:88].strip() or 0)
        dec_s = float(line[88:90].strip() or 0)
        dec_deg = dec_d + dec_m/60.0 + dec_s/3600.0
        if dec_sign == '-':
            dec_deg = -dec_deg
        vmag_str = line[102:107].strip()
        if not vmag_str:
            return None
        try:
            vmag = float(vmag_str)
        except ValueError:
            return None
        if not name:
            name = f'HR{hr}'
        return {'hr': hr, 'name': name, 'ra_deg': ra_deg, 'dec_deg': dec_deg, 'vmag': vmag}
    except (ValueError, IndexError):
        return None

stars = []
print("Parsing BSC5...")
with open('/tmp/bsc5.dat', 'r', encoding='latin-1') as f:
    for line in f:
        star = parse_bsc5_line(line)
        if star and star['vmag'] <= 4.0:
            stars.append(star)

print(f"Found {len(stars)} stars with magnitude ≤ 4.0")
stars.sort(key=lambda s: s['vmag'])

with open('star_hash/data/navigational_stars.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Name', 'RA_Degrees', 'Dec_Degrees', 'Magnitude'])
    for star in stars:
        writer.writerow([star['name'], f"{star['ra_deg']:.4f}", f"{star['dec_deg']:.4f}", f"{star['vmag']:.2f}"])

print(f"✓ Wrote {len(stars)} stars to navigational_stars.csv")
