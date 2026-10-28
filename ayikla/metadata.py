"""JPEG/TIFF header-only EXIF reads; never decode photo pixels."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

from .core import natural_key
from .file_access import file_guard


@dataclass(frozen=True)
class CaptureInfo:
    filename: str
    taken: datetime | None = None
    shutter: str = "—"
    aperture: str = "—"
    iso: str = "—"
    focal_length: str = "—"
    lens: str = "—"

    def text(self) -> str:
        timestamp = self.taken.strftime("%d.%m.%Y  %H:%M:%S") if self.taken else "—"
        return (f"{self.filename}\n\nTaken     {timestamp}\nShutter     {self.shutter}\n"
                f"Aperture     {self.aperture}\nISO     {self.iso}\n"
                f"Focal length     {self.focal_length}\nLens     {self.lens}")


def read_metadata(path: str | Path) -> CaptureInfo:
    with file_guard(path):
        return _read_metadata(path)


def _read_metadata(path: str | Path) -> CaptureInfo:
    path = Path(path)
    try:
        with Image.open(path, formats=["JPEG", "TIFF"]) as image:
            top = image.getexif()
            values = dict(top)
            values.update(top.get_ifd(34665))
            date = values.get(36867) or values.get(306)
            taken = None
            if date:
                try:
                    taken = datetime.strptime(str(date).strip("\0 "), "%Y:%m:%d %H:%M:%S")
                    fraction = str(values.get(37521, "")).strip("\0 ")
                    if fraction.isdigit():
                        taken = taken.replace(microsecond=int((fraction + "000000")[:6]))
                except (ValueError, TypeError):
                    pass
            def number(tag):
                try:
                    result = float(values.get(tag, 0))
                    return result if 0 < result < 1e9 else 0
                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    return 0
            seconds, aperture, focal = number(33434), number(33437), number(37386)
            shutter = (f"1/{round(1 / seconds)} s" if seconds < 1 else f"{seconds:g} s") if seconds else "—"
            iso = values.get(34855, "—")
            if isinstance(iso, tuple):
                iso = iso[0] if iso else "—"
            lens = str(values.get(42036, "—")).replace("\0", "").strip()[:200] or "—"
            return CaptureInfo(path.name, taken, shutter, f"f/{aperture:g}" if aperture else "—",
                               str(iso), f"{focal:g} mm" if focal else "—", lens)
    except (OSError, ValueError, TypeError, SyntaxError, OverflowError):
        return CaptureInfo(path.name)


def burst_hints(items: dict[str, CaptureInfo]) -> dict[str, tuple[int, int]]:
    return {key: (index, len(group)) for group in burst_groups(items)
            for index, key in enumerate(group, 1)}


def burst_groups(items: dict[str, CaptureInfo]) -> list[tuple[str, ...]]:
    """Consecutive capture times at most one second apart, across all states."""
    ordered = sorted(((key, info) for key, info in items.items() if info.taken is not None),
                     key=lambda item: (item[1].taken, natural_key(item[1].filename)))
    groups: list[list[str]] = []
    previous = None
    for key, info in ordered:
        if previous is None or (info.taken - previous).total_seconds() > 1:
            groups.append([])
        groups[-1].append(key)
        previous = info.taken
    return [tuple(group) for group in groups if len(group) > 1]
