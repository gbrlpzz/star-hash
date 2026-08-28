from __future__ import annotations
import math
"""
star_hash.stars
~~~~~~~~~~~~~~~
The 57 standard IAU navigational stars embedded with J2000 coordinates,
proper motions, and apparent visual magnitudes.
"""
from typing import List, Dict, Any

# Table format: (Name, RA_deg, Dec_deg, Mag, ProperMotion_RA_arcsec_yr, ProperMotion_Dec_arcsec_yr)
# 57 standard navigational stars defined by nautical almanacs and celestial navigation standards.
NAVIGATIONAL_STARS: List[tuple[str, float, float, float, float, float]] = [
    ("Sirius", 101.2871, -16.7161, -1.46, -0.546, -1.223),
    ("Canopus", 95.9879, -52.6958, -0.74, 0.020, 0.023),
    ("Rigil Kentaurus", 219.9021, -60.8340, -0.27, -3.678, 0.481),
    ("Arcturus", 213.9153, 19.1824, -0.05, -1.093, -1.999),
    ("Vega", 279.2347, 38.7837, 0.03, 0.201, 0.287),
    ("Capella", 79.1723, 45.9980, 0.08, 0.075, -0.427),
    ("Rigel", 78.6345, -8.2016, 0.13, 0.002, -0.001),
    ("Procyon", 114.8255, 5.2250, 0.38, -0.717, -1.035),
    ("Achernar", 24.4285, -57.2367, 0.46, 0.088, -0.040),
    ("Betelgeuse", 88.7929, 7.4071, 0.50, 0.027, 0.011),
    ("Hadar", 210.9559, -60.3731, 0.61, -0.033, -0.025),
    ("Altair", 297.6958, 8.8683, 0.77, 0.537, 0.386),
    ("Acrux", 186.6496, -63.0991, 0.77, -0.035, -0.012),
    ("Aldebaran", 68.9802, 16.5093, 0.85, 0.063, -0.189),
    ("Antares", 247.3519, -26.4320, 0.96, -0.012, -0.023),
    ("Spica", 201.2983, -11.1613, 0.98, -0.042, -0.032),
    ("Pollux", 116.1245, 28.0262, 1.14, -0.626, -0.046),
    ("Fomalhaut", 344.4127, -29.6222, 1.16, 0.329, -0.165),
    ("Deneb", 310.3580, 45.2803, 1.25, 0.002, 0.002),
    ("Mimosa", 191.9303, -59.6888, 1.25, -0.048, -0.013),
    ("Regulus", 152.0930, 11.9672, 1.35, -0.249, 0.006),
    ("Adhara", 104.6565, -28.9721, 1.50, 0.003, 0.002),
    ("Castor", 113.6494, 31.8883, 1.58, -0.206, -0.148),
    ("Gacrux", 187.7915, -57.1132, 1.63, 0.028, -0.264),
    ("Shaula", 263.4022, -37.1038, 1.63, -0.009, -0.030),
    ("Bellatrix", 81.2829, 6.3497, 1.64, -0.009, -0.013),
    ("Elnath", 81.5730, 28.6075, 1.65, 0.024, -0.174),
    ("Miaplacidus", 138.3005, -69.7172, 1.68, -0.156, 0.113),
    ("Alnilam", 84.0534, -1.2019, 1.69, 0.001, -0.001),
    ("Alnair", 332.0583, -46.9609, 1.74, 0.127, -0.148),
    ("Alioth", 193.5073, 55.9598, 1.77, 0.112, -0.009),
    ("Dubhe", 165.9320, 61.7510, 1.79, -0.136, -0.035),
    ("Mirfak", 51.0807, 49.8612, 1.79, 0.024, -0.026),
    ("Wezen", 107.0979, -26.3932, 1.83, -0.003, 0.004),
    ("Alkaid", 206.8852, 49.3133, 1.86, -0.121, -0.016),
    ("Kaus Australis", 276.0430, -34.3846, 1.85, -0.040, -0.124),
    ("Avior", 125.6285, -59.5095, 1.86, -0.021, 0.020),
    ("Menkalinan", 89.8820, 44.9474, 1.90, -0.056, -0.228),
    ("Atria", 252.1661, -69.0277, 1.92, 0.021, -0.033),
    ("Alhena", 99.4280, 16.3986, 1.93, -0.043, -0.068),
    ("Peacock", 306.4120, -56.7350, 1.94, 0.076, -0.086),
    ("Alsephina", 131.1760, -54.7180, 1.96, -0.134, 0.158),
    ("Mirzam", 95.6749, -17.9559, 1.98, -0.003, -0.001),
    ("Alphard", 141.8968, -8.6586, 1.98, -0.015, 0.034),
    ("Polaris", 37.9546, 89.2641, 1.98, 0.044, -0.012),
    ("Hamal", 31.7934, 23.4624, 2.00, 0.191, -0.146),
    ("Diphda", 10.8974, -17.9866, 2.04, 0.233, 0.032),
    ("Nunki", 283.8164, -26.2967, 2.05, 0.018, -0.054),
    ("Menkent", 211.6700, -36.3700, 2.06, -0.052, -0.520),
    ("Mirach", 17.4330, 35.6206, 2.06, 0.176, -0.112),
    ("Alpheratz", 2.0969, 29.0904, 2.06, 0.136, -0.163),
    ("Rasalhague", 263.7336, 12.5600, 2.08, 0.108, -0.222),
    ("Kochab", 222.6764, 74.1555, 2.08, -0.032, 0.012),
    ("Saiph", 86.9391, -9.6696, 2.09, 0.001, -0.001),
    ("Denebola", 177.2649, 14.5721, 2.14, -0.500, -0.115),
    ("Algol", 47.0422, 40.9556, 2.12, 0.002, -0.001),
    ("Almach", 30.9748, 42.3327, 2.17, 0.043, -0.051),
]

def load_stars_for_epoch(T: float) -> List[Dict[str, Any]]:
    """
    Returns the standard navigational stars with proper motion and precession
    applied for epoch T (centuries from J2000.0).
    """
    # Precession in RA and Dec per century (Simon et al. / IAU 2006 linear terms)
    # m = 3.075 sec/yr = 46.12 arcsec/yr = 1.281 deg/century
    # n = 20.04 arcsec/yr = 0.5567 deg/century
    m_deg = 1.281232 * T
    n_deg = 0.556753 * T

    rad = 0.017453292519943295
    results: List[Dict[str, Any]] = []

    for name, ra_j2000, dec_j2000, mag, pm_ra, pm_dec in NAVIGATIONAL_STARS:
        ra_rad = ra_j2000 * rad
        dec_rad = dec_j2000 * rad

        # Proper motion displacement over T centuries (arcsec/yr -> deg)
        years = T * 100.0
        d_ra_pm = (pm_ra * years) / 3600.0
        d_dec_pm = (pm_dec * years) / 3600.0

        # Precession displacement
        d_ra_prec = m_deg + n_deg * math.sin(ra_rad) * math.tan(dec_rad)
        d_dec_prec = n_deg * math.cos(ra_rad)

        ra_epoch = (ra_j2000 + d_ra_pm + d_ra_prec) % 360.0
        dec_epoch = max(-90.0, min(90.0, dec_j2000 + d_dec_pm + d_dec_prec))

        results.append({
            "name": name,
            "ra_rad": (ra_epoch % 360.0) * rad,
            "dec_rad": dec_epoch * rad,
            "mag": mag,
            "type": "star",
        })

    return results
