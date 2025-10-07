from __future__ import annotations
from typing import Any, Dict, Optional, List, Tuple

import os
from PIL import Image, ExifTags  # type: ignore


def _convert_gps(info: Dict[int, Any]) -> Optional[Dict[str, float]]:
    # Convert GPSInfo dict to decimal degrees
    def _r2f(r):
        try:
            return float(r[0]) / float(r[1])
        except Exception:
            return float(r)

    try:
        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in info.items()}
        lat_ref = gps.get("GPSLatitudeRef", "N")
        lon_ref = gps.get("GPSLongitudeRef", "E")
        lat = gps.get("GPSLatitude")
        lon = gps.get("GPSLongitude")
        if not lat or not lon:
            return None
        lat_deg = _r2f(lat[0]) + _r2f(lat[1]) / 60.0 + _r2f(lat[2]) / 3600.0
        lon_deg = _r2f(lon[0]) + _r2f(lon[1]) / 60.0 + _r2f(lon[2]) / 3600.0
        if lat_ref == "S":
            lat_deg = -lat_deg
        if lon_ref == "W":
            lon_deg = -lon_deg
        return {"lat": lat_deg, "lon": lon_deg}
    except Exception:
        return None


def image_exif(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"exif": None}
    try:
        img = Image.open(path).convert("RGB")
        exif_raw = img._getexif() or {}
        exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
        gps_info = exif_raw.get(34853)  # GPSInfo
        gps = _convert_gps(gps_info) if gps_info else None
        out: Dict[str, Any] = {"exif": {k: v for k, v in exif.items() if k in ("Make","Model","DateTime","Software")}}
        if gps:
            out["gps"] = gps
            # Reverse geocode to city/country (best-effort)
            try:
                import reverse_geocoder as rg  # type: ignore
                res = rg.search((gps["lat"], gps["lon"]))  # type: ignore[arg-type]
                if res and isinstance(res, list):
                    r0 = res[0]
                    out["place"] = {"city": r0.get("name"), "country": r0.get("cc")}
                    # Place tags
                    out["place_tags"] = [t for t in (r0.get("name"), r0.get("cc")) if t]
            except Exception:
                pass
            # Timezone estimate
            try:
                from timezonefinder import TimezoneFinder  # type: ignore
                tf = TimezoneFinder()
                tz = tf.timezone_at(lng=gps["lon"], lat=gps["lat"])  # type: ignore[arg-type]
                if tz:
                    out["timezone"] = tz
            except Exception:
                pass
        # Color/brightness descriptors
        try:
            import numpy as np  # type: ignore
            arr = np.asarray(img)
            # brightness as mean of grayscale
            gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2])
            brightness = float(np.mean(gray) / 255.0)
            # dominant colors via k-means-like palette using PIL quantize
            pal_img = img.convert('P', palette=Image.ADAPTIVE, colors=5)
            palette = pal_img.getpalette()[0:15]  # first 5 colors * 3 channels
            colors: List[Tuple[int, int, int]] = [(palette[i], palette[i+1], palette[i+2]) for i in range(0, len(palette), 3)]
            hex_colors = ["#%02x%02x%02x" % c for c in colors]
            out["brightness"] = brightness
            out["dominant_colors"] = hex_colors
        except Exception:
            pass
        return out
    except Exception:
        return {"exif": None}
