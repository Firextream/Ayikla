"""Reproducible local Windows benchmark; generated images only, never real shoots.

Usage: python scripts/benchmark.py generate
       python scripts/benchmark.py measure v1
       python scripts/benchmark.py startup LABEL EXE
All writes stay inside this project's .tmp/benchmark and docs/benchmark directories.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import random
import statistics
import struct
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".tmp" / "benchmark"
RESULTS = ROOT / "docs" / "benchmark"
sys.path.insert(0, str(ROOT))


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong),
                *[(name, ctypes.c_size_t) for name in
                  ("peak_rss", "rss", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
                   "pagefile", "peak_pagefile", "private")]]


def memory() -> dict:
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return {"rss_mib": round(counters.rss / 2**20, 2),
            "peak_rss_mib": round(counters.peak_rss / 2**20, 2),
            "private_mib": round(counters.private / 2**20, 2)}


def write_result(label: str, result: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{label}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True), flush=True)


def generate() -> None:
    from PIL import Image, TiffImagePlugin
    data = BASE / "data"
    if (data / "manifest.json").exists():
        print((data / "manifest.json").read_text("utf-8"), flush=True)
        return
    data.mkdir(parents=True, exist_ok=True)
    # Four deterministic RGB noise images force realistic JPEG entropy decoding.
    # Each of the 300 files gets a distinct EXIF time; no padding to fake 8 MB.
    templates = []
    for seed in range(4):
        import io
        image = Image.frombytes("RGB", (6000, 4000), random.Random(seed).randbytes(72_000_000))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=40, subsampling=2)
        templates.append(buffer.getvalue())
        print(f"Template {seed + 1}: {len(templates[-1]) / 1e6:.2f} MB", flush=True)
        image.close()
    sizes = []
    started = datetime(2026, 10, 25, 10, 0, 0)
    for index in range(300):
        exif = Image.Exif()
        exif[271], exif[272] = "Yapay test", "24 MP benchmark"
        timestamp = started + timedelta(seconds=(index // 5) * 3, milliseconds=(index % 5) * 180)
        exif[34665] = {36867: timestamp.strftime("%Y:%m:%d %H:%M:%S"),
                       37521: f"{timestamp.microsecond:06d}",
                       33434: TiffImagePlugin.IFDRational(1, 320),
                       33437: TiffImagePlugin.IFDRational(28, 10), 34855: 400,
                       37386: TiffImagePlugin.IFDRational(50), 42036: "Generated test lens 50mm"}
        payload = exif.tobytes()
        jpeg = templates[index % len(templates)]
        target = data / f"IMG_{index + 1:04d}.JPG"
        with target.open("xb") as stream:
            stream.write(jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + jpeg[2:])
        with target.with_suffix(".CR3").open("xb") as stream:
            stream.write(b"GENERATED DUMMY CR3\0" * 3500)
        sizes.append(target.stat().st_size)
        if (index + 1) % 50 == 0:
            print(f"Generated {index + 1}/300 pairs", flush=True)
    manifest = {"generated": True, "count": 300, "dimensions": [6000, 4000],
                "mean_jpeg_bytes": statistics.mean(sizes), "min_jpeg_bytes": min(sizes),
                "max_jpeg_bytes": max(sizes), "jpeg_quality": 40,
                "description": "4 seeded RGB-noise templates, 300 unique EXIF timestamps; no padding"}
    (data / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    write_result("dataset", manifest)


def fresh_shoot(label: str) -> Path:
    source = BASE / "data"
    manifest = json.loads((source / "manifest.json").read_text("utf-8"))
    if manifest["count"] != 300 or manifest["generated"] is not True:
        raise ValueError("Benchmark requires the generated 300-pair dataset")
    shoot = BASE / "runs" / f"{label}-{uuid.uuid4().hex[:8]}"
    shoot.mkdir(parents=True, exist_ok=False)
    for path in source.iterdir():
        if path.suffix in {".JPG", ".CR3"}:
            os.link(path, shoot / path.name)
    return shoot


def stats(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {"median_ms": round(statistics.median(samples), 2),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 2),
            "min_ms": round(min(samples), 2), "max_ms": round(max(samples), 2),
            "n": len(samples)}


def measure(label: str) -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["AYIKLA_STATE_DIR"] = str(BASE / "state" / label)
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication
    from ayikla.ui import MainWindow
    app = QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))

    def spin(predicate, timeout=15):
        deadline = time.perf_counter() + timeout
        while not predicate():
            app.processEvents()
            time.sleep(.0005)
            if time.perf_counter() > deadline:
                raise TimeoutError("Benchmark UI did not complete")
        app.processEvents()

    window = MainWindow()
    window._show_error = lambda error: (_ for _ in ()).throw(error)
    window.showNormal()
    window.resize(1440, 960)
    app.processEvents()
    opens = []
    for trial in range(3):
        shoot = fresh_shoot(f"{label}-{trial}")
        started = time.perf_counter()
        window.open_folder(shoot)
        spin(lambda: not window.busy and not window.canvas.image.isNull())
        window.canvas.repaint()
        opens.append((time.perf_counter() - started) * 1000)
        spin(lambda: not window.cache.inflight)
    cached = []
    for _ in range(20):
        spin(lambda: not window.cache.inflight)
        started = time.perf_counter()
        window.navigate(1)
        spin(lambda: not window.canvas.image.isNull())
        window.canvas.repaint()
        cached.append((time.perf_counter() - started) * 1000)
    uncached = []
    refresh_options = {"rescan": False} if hasattr(window.session, "rescan") else {}
    for index in range(100, 120):
        spin(lambda: not window.cache.inflight)
        window.cache.clear()
        started = time.perf_counter()
        window.refresh(window.photos[index].key, **refresh_options)
        spin(lambda: not window.canvas.image.isNull())
        window.canvas.repaint()
        uncached.append((time.perf_counter() - started) * 1000)
    spin(lambda: not window.cache.inflight)
    navigation_memory = memory()
    snapshot_times = []
    for _ in range(20):
        started = time.perf_counter()
        window.session.snapshot()
        snapshot_times.append((time.perf_counter() - started) * 1000)
    decisions = []
    for _ in range(10):
        photo = window.session.snapshot().pending[0]
        started = time.perf_counter()
        window.session.decide(photo, True)
        decisions.append((time.perf_counter() - started) * 1000)
        window.session.undo()
    zoom_memory = None
    if hasattr(window, "toggle_zoom"):
        window.refresh(window.photos[150].key)
        spin(lambda: not window.canvas.image.isNull())
        window.toggle_zoom()
        spin(lambda: window.canvas.image.width() == 6000)
        window.canvas.repaint()
        zoom_memory = memory()
    result = {"label": label, "python": sys.version.split()[0], "platform": sys.platform,
              "display": "1440x960 @ DPR=1; Qt offscreen; fit mode; filmstrip default off",
              "method": "fresh generated shoot per open; all JPEGs are 6000x4000 ~8 MB; application-cache-cold, OS cache uncontrolled; cached waits for preloading; includes forced paint",
              "folder_open_to_first_paint": stats(opens), "next_preloaded": stats(cached),
              "next_uncached": stats(uncached), "snapshot": stats(snapshot_times),
              "keep": stats(decisions), "navigation_memory": navigation_memory,
              "zoom_memory": zoom_memory,
              "cache_bytes": sum(item[0].sizeInBytes() for item in window.cache.cache.values())}
    window.close()
    app.processEvents()
    write_result(label, result)


def startup(label: str, executable: Path) -> None:
    samples = []
    for _ in range(5):
        marker = BASE / f"startup-{uuid.uuid4().hex}.json"
        environment = os.environ.copy()
        environment["AYIKLA_STARTUP_PROBE"] = str(marker)
        environment["AYIKLA_STATE_DIR"] = str(BASE / "state" / "startup")
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["TEMP"] = environment["TMP"] = str(ROOT / ".tmp")
        environment["PATH"] = str(Path(environment["WINDIR"]) / "System32")
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        started = time.perf_counter()
        process = subprocess.Popen([str(executable.resolve())], env=environment, cwd=BASE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.perf_counter() + 20
            while not marker.exists():
                if process.poll() is not None or time.perf_counter() > deadline:
                    raise RuntimeError(f"Startup probe failed: {process.poll()}")
                time.sleep(.001)
            ready = json.loads(marker.read_text("utf-8"))["ready"]
            samples.append((ready - started) * 1000)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
    if executable.parent.name == "dist":
        total = executable.stat().st_size
    else:
        total = sum(path.stat().st_size for path in executable.parent.rglob("*") if path.is_file())
    write_result(f"{label}-package", {"label": label, "startup_first_paint": stats(samples),
                                     "package_bytes": total, "exe_bytes": executable.stat().st_size,
                                     "method": "5 launches to first Qt paint; same offscreen backend; OS cache uncontrolled; no interpreter/source PATH"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["generate", "measure", "startup"])
    parser.add_argument("label", nargs="?", default="v1")
    parser.add_argument("executable", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "generate":
        generate()
    elif args.action == "measure":
        measure(args.label)
    else:
        startup(args.label, args.executable)
