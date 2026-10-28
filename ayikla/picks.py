"""Versioned, local handoff for image adders. No writing-app dependency."""

import json

from PySide6.QtCore import QSize

from .colors import analyze
from .images import ImageCache
from .metadata import read_metadata


def serialize(photos, palette_cache) -> bytes:
    picks = []
    for photo in photos:
        info = read_metadata(photo.jpeg)
        try:
            signature = ImageCache.key(photo.jpeg, QSize(128, 128))
            palette = palette_cache.get(signature)
            if palette is None:
                palette = analyze(photo.jpeg)
                palette_cache[signature] = palette
            swatches = list(palette.swatches)
        except (OSError, ValueError):
            swatches = []
        picks.append({"filename": photo.jpeg.name,
                      "raw_filename": photo.raw.name if photo.raw else None,
                      "capture_time": info.taken.isoformat() if info.taken else None,
                      "camera": info.camera if info.camera != "—" else None,
                      "lens": info.lens if info.lens != "—" else None,
                      "settings": {name: getattr(info, name) if getattr(info, name) != "—" else None
                                   for name in ("shutter", "aperture", "iso", "focal_length")},
                      "palette": swatches, "caption": ""})
    return (json.dumps({"schema_version": 1, "picks": picks}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
