"""Decode PostGIS WKB and imported WKT without inventing missing coordinates."""
from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from shapely import wkb, wkt
from shapely.geometry.base import BaseGeometry


def decode_geometry(value):
    if value is None:
        return None
    try:
        if isinstance(value, BaseGeometry):
            return value
        if isinstance(value, (WKBElement, WKTElement)):
            return to_shape(value)
        if isinstance(value, (bytes, memoryview)):
            return wkb.loads(bytes(value))
        text = str(value).split(";", 1)[-1]
        return wkt.loads(text) if "(" in text else wkb.loads(text, hex=True)
    except Exception:
        return None


def point_coordinates(value):
    geometry = decode_geometry(value)
    if geometry is None or geometry.is_empty or geometry.geom_type != "Point":
        return None, None
    return geometry.y, geometry.x


def validate_bbox(bbox):
    import math
    west, south, east, north = bbox
    if not all(math.isfinite(x) for x in bbox):
        raise ValueError("Bounding box coordinates must be finite")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Use west,south,east,north with west < east and south < north")
    return bbox
