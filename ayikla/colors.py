"""Small, read-only JPEG palette descriptors. No RAW decoding or quality scoring."""

from collections import Counter
from dataclasses import dataclass
import colorsys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColorSpace, QImage

from .images import read_image

TONES = ("Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Purple", "Pink",
         "Dark", "Neutral", "Light")


@dataclass(frozen=True)
class Palette:
    coverage: tuple[float, ...]
    histogram: tuple[float, ...]
    swatches: tuple[str, ...]


def describe(image: QImage) -> Palette:
    if image.isNull():
        raise ValueError("Could not read JPEG pixels.")
    if image.colorSpace().isValid():
        converted = image.convertedToColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        if not converted.isNull():
            image = converted
    image = image.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio)
    coverage = [0] * len(TONES)
    histogram = [0] * 39
    buckets = Counter()
    sums = {}
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            r, g, b = pixel.red(), pixel.green(), pixel.blue()
            hue, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if value < .18:
                tone, cell = 8, 36
            elif saturation < .18:
                tone = 10 if value > .82 else 9
                cell = 38 if tone == 10 else 37
            else:
                degrees = hue * 360
                tone = next((i for i, upper in enumerate((15, 45, 70, 165, 195, 255, 285, 345))
                             if degrees < upper), 0)
                cell = min(11, int(((hue + 1 / 24) % 1) * 12)) * 3 + min(2, int(value * 3))
            coverage[tone] += 1
            histogram[cell] += 1
            bucket = (r // 32, g // 32, b // 32)
            buckets[bucket] += 1
            total = sums.setdefault(bucket, [0, 0, 0])
            for i, channel in enumerate((r, g, b)):
                total[i] += channel
    count = image.width() * image.height()
    swatches = tuple('#' + ''.join(f'{round(channel / amount):02x}' for channel in sums[bucket])
                     for bucket, amount in buckets.most_common(5))
    return Palette(tuple(n / count for n in coverage), tuple(n / count for n in histogram), swatches)


def analyze(path: Path) -> Palette:
    image, error = read_image(path, QSize(128, 128))
    if image.isNull():
        raise ValueError(error or "Could not open JPEG.")
    return describe(image)


def similarity(first: Palette, second: Palette) -> float:
    return sum(min(a, b) for a, b in zip(first.histogram, second.histogram))


def rank(profiles: dict[str, Palette], *, tone: str | None = None,
         reference: str | None = None, minimum=.15, limit=24) -> list[tuple[str, float]]:
    if tone is not None:
        index = TONES.index(tone)
        scored = [(key, profile.coverage[index]) for key, profile in profiles.items()]
    elif reference in profiles:
        scored = [(key, similarity(profiles[reference], profile))
                  for key, profile in profiles.items() if key != reference]
        minimum = .5
    else:
        return []
    return sorted(((key, score) for key, score in scored if score >= minimum),
                  key=lambda item: (-item[1], item[0]))[:limit]
