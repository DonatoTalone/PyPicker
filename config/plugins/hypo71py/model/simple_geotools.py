# simple_geotools.py
"""
Lightweight replacement for mapping.geotools.* used by robspy.hypo_inv.
Requires: numpy, pyproj
"""

from typing import Iterable, List, Tuple, Union
import numpy as np
from pyproj import CRS, Transformer, Geod

# Constants
EARTH_RADIUS = 6371.0  # km, mean Earth radius
WGS84 = CRS.from_epsg(4326)
_geod = Geod(ellps="WGS84")


# -------------------------
# UTM helpers
# -------------------------
def get_utm_spec(lon: float, lat: float) -> Tuple[int, str]:
    """
    Determine UTM zone number and hemisphere for a lon/lat.
    Returns (zone, 'N'|'S').
    Works for scalar inputs.
    """
    # wrap longitude into [-180, 180)
    lon_wrapped = ((lon + 180) % 360) - 180
    zone = int(np.floor((lon_wrapped + 180) / 6.0)) + 1
    zone = max(1, min(60, zone))
    hemi = "N" if lat >= 0 else "S"
    return zone, hemi


def get_utm_srs(utm_spec: str = "UTM31N") -> CRS:
    """
    Return pyproj CRS for a UTM spec string "UTM{zone}{N|S}" (e.g. "UTM55S").
    """
    spec = utm_spec.upper()
    if not spec.startswith("UTM"):
        raise ValueError("utm_spec must start with 'UTM'")
    try:
        zone = int(spec[3:5])
        hemi = spec[5]
    except Exception as e:
        raise ValueError("Invalid utm_spec format. Expected e.g. 'UTM31N'") from e
    epsg = 32600 + zone if hemi == "N" else 32700 + zone
    return CRS.from_epsg(epsg)


# -------------------------
# Transform helpers (pyproj)
# -------------------------
def transform_coordinates(source_crs: CRS, target_crs: CRS,
                          coord_list: Iterable[Tuple[float, ...]]
                          ) -> List[Tuple[float, ...]]:
    """
    Transform a list of coordinates (x,y) or (x,y,z) from source_crs to target_crs.
    Returns a list of tuples with same dimensionality (2 or 3).
    """
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    out = []
    for c in coord_list:
        if len(c) == 3:
            x2, y2, z2 = transformer.transform(c[0], c[1], c[2])
            out.append((x2, y2, z2))
        else:
            x2, y2 = transformer.transform(c[0], c[1])
            out.append((x2, y2))
    return out


def transform_array_coordinates(source_crs: CRS, target_crs: CRS,
                                xs: Union[np.ndarray, List[float]],
                                ys: Union[np.ndarray, List[float]],
                                zs: Union[None, np.ndarray, List[float]] = None
                                ) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Vectorized transform for arrays. Returns arrays (x2_array, y2_array[, z2_array]).
    """
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    if zs is None:
        x2, y2 = transformer.transform(xs, ys)
        return np.asarray(x2), np.asarray(y2)
    else:
        zs = np.asarray(zs)
        x2, y2, z2 = transformer.transform(xs, ys, zs)
        return np.asarray(x2), np.asarray(y2), np.asarray(z2)


# -------------------------
# Lon/Lat <-> UTM
# -------------------------
def lonlat_to_utm(lons: Union[Iterable[Tuple], Iterable[float]],
                  lats: Union[None, Iterable[float]] = None,
                  z: Union[None, Iterable[float]] = None,
                  utm_spec: str = "UTM31N"):
    """
    Convert geographic coords (lon, lat [,z]) to UTM (easting, northing [, z]).
    Accepts either:
       - single iterable of (lon, lat[, z]) tuples, OR
       - separate lons, lats (and optional z) arrays.
    Returns list of tuples (x,y[,z]) if input was list-of-tuples,
    otherwise returns arrays (xs, ys [, zs]).
    """
    utm_crs = get_utm_srs(utm_spec)
    if lats is None:
        # assume lons is an iterable of tuples
        return transform_coordinates(WGS84, utm_crs, lons)
    else:
        xs, ys = transform_array_coordinates(WGS84, utm_crs, lons, lats) if z is None else transform_array_coordinates(WGS84, utm_crs, lons, lats, z)
        return (xs, ys) if z is None else (xs, ys, z)


def utm_to_lonlat(x: Union[Iterable[Tuple], Iterable[float]],
                  y: Union[None, Iterable[float]] = None,
                  z: Union[None, Iterable[float]] = None,
                  utm_spec: str = "UTM31N"):
    """
    Convert UTM coords to lon/lat ([z]).
    If y is None, expects x to be list-of-tuples and returns list-of-tuples.
    Otherwise returns arrays (lons, lats[, zs]).
    """
    utm_crs = get_utm_srs(utm_spec)
    if y is None:
        return transform_coordinates(utm_crs, WGS84, x)
    else:
        out = transform_array_coordinates(utm_crs, WGS84, x, y) if z is None else transform_array_coordinates(utm_crs, WGS84, x, y, z)
        return out


# -------------------------
# Spherical / Geodetic
# -------------------------
def spherical_distance(lon1, lat1, lon2, lat2, R=EARTH_RADIUS):
    """
    Great-circle distance using haversine formula.
    Inputs in degrees. Returns distance in metres.
    Works with scalars or numpy arrays.
    """
    lon1_rad, lat1_rad = np.radians(lon1), np.radians(lat1)
    lon2_rad, lat2_rad = np.radians(lon2), np.radians(lat2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c * 1000.0


def cartesian_point_at_geo(lon, lat, azimuth_deg, distance_m):
    """
    Geodetic destination from lon/lat given azimuth (deg) and distance (m).
    Returns (lon2, lat2).
    """
    lon2, lat2, _ = _geod.fwd(lon, lat, azimuth_deg, distance_m)
    return lon2, lat2


def cartesian_azimuth_geo(lon1, lat1, lon2, lat2):
    """
    Forward azimuth (deg) from point 1 to point 2 on ellipsoid.
    """
    az12, _, _ = _geod.inv(lon1, lat1, lon2, lat2)
    return az12


# -------------------------
# Planar (Cartesian)
# -------------------------
def cartesian_point_at(x1, y1, distance, azimuth):
    """
    Compute (x2, y2) at given azimuth (deg) and distance from (x1, y1).
    Angle convention: 0° = north, increasing clockwise.
    """
    az_rad = np.radians(azimuth)
    x2 = x1 + distance * np.sin(az_rad)
    y2 = y1 + distance * np.cos(az_rad)
    return x2, y2


def cartesian_azimuth(x1, y1, x2, y2):
    """
    Compute bearing in degrees 0..360 from point A to B using planar coords.
    0° = north, increases clockwise.
    """
    angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
    bearing = (90.0 - angle) % 360.0
    return bearing
