"""ENU <-> WGS-84 conversions (Ottawa reference by default)."""
from __future__ import annotations
import math
import numpy as np

A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)

PARLIAMENT_HILL = (45.4236, -75.7009, 70.0)   # lat, lon, height above ellipsoid ~ (ground ~70 m ASL)


def geodetic_to_ecef(lat_deg, lon_deg, h_m):
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    x = (n + h_m) * math.cos(lat) * math.cos(lon)
    y = (n + h_m) * math.cos(lat) * math.sin(lon)
    z = (n * (1 - E2) + h_m) * math.sin(lat)
    return np.array([x, y, z])


def ecef_to_geodetic(xyz):
    x, y, z = xyz
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - E2))
    for _ in range(6):
        n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - E2 * n / (n + h)))
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h


def enu_to_geodetic(enu, ref=PARLIAMENT_HILL):
    lat0, lon0, h0 = ref
    lat, lon = math.radians(lat0), math.radians(lon0)
    r = np.array([[-math.sin(lon), -math.sin(lat) * math.cos(lon), math.cos(lat) * math.cos(lon)],
                  [math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat) * math.sin(lon)],
                  [0.0, math.cos(lat), math.sin(lat)]])
    ecef = geodetic_to_ecef(lat0, lon0, h0) + r @ np.asarray(enu, float)
    return ecef_to_geodetic(ecef)
