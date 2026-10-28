"""Key-to-render navigation on the same generated 24 MP JPEG dataset."""

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def measure(label, source_root, output):
    os.environ["QT_QPA_PLATFORM"] = "windows"
    os.environ["QT_SCALE_FACTOR"] = "1"
    run = ROOT / ".tmp" / "benchmark" / "runs" / f"nav-{label}-{uuid.uuid4().hex[:8]}"
    run.mkdir(parents=True)
    os.environ["AYIKLA_STATE_DIR"] = str(run / "state")
    source = ROOT / ".tmp" / "benchmark" / "data"
    manifest = json.loads((source / "manifest.json").read_text("utf-8"))
    assert manifest["generated"] is True and manifest["dimensions"] == [6000, 4000]
    for path in source.glob("*.JPG"):
        os.link(path, run / path.name)
    sys.path.insert(0, str(Path(source_root).resolve()))
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ayikla import __version__
    from ayikla.ui import MainWindow
    app = QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.resize(1440, 960)
    window.show()
    errors, painted = [], []
    desired = [None]
    original_paint = window.canvas.paintEvent
    def paint(event):
        original_paint(event)
        if window.current and window.current.key == desired[0] and not window.canvas.image.isNull():
            painted.append(time.perf_counter())
    window.canvas.paintEvent = paint
    window._show_error = errors.append

    def wait(predicate, timeout=20):
        deadline = time.perf_counter() + timeout
        while not predicate() and not errors and time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(.0005)
        app.processEvents()
        assert not errors, str(errors)
        assert predicate(), "Navigation benchmark timed out"

    def settled():
        wait(lambda: not window.cache.inflight and not window._resize_timer.isActive())

    def key_to_paint(step):
        target = window.photos[window.index + step]
        wanted = window.cache.wanted
        hit = bool(wanted and window.cache.key(target.jpeg, QSize(wanted[3], wanted[4])) in window.cache.cache)
        desired[0], painted[:] = target.key, []
        started = time.perf_counter()
        QTest.keyClick(window, Qt.Key.Key_Up if step < 0 else Qt.Key.Key_Down)
        wait(lambda: not window.canvas.image.isNull())
        window.canvas.repaint()
        if not painted:
            window.canvas.grab()  # Force the native QWidget raster paint if hidden.
        wait(lambda: bool(painted))
        return (painted[0] - started) * 1000, hit

    def stats(samples):
        values = sorted(samples)
        return {"median_ms": round(statistics.median(values), 2),
                "p95_ms": round(values[min(len(values) - 1, int(len(values) * .95))], 2),
                "min_ms": round(values[0], 2), "max_ms": round(values[-1], 2), "n": len(values)}

    results = {}
    try:
        window.open_folder(run)
        wait(lambda: not window.busy and not window.canvas.image.isNull())
        settled()
        wait(lambda: window._metadata_pool.activeThreadCount() == 0)
        for mode, step in (("next_preloaded", 1), ("previous_preloaded", -1), ("next_cold", 1)):
            values, hits = [], 0
            window.refresh(window.photos[100 if step > 0 else 160].key, rescan=False)
            wait(lambda: not window.canvas.image.isNull())
            for _ in range(30):
                settled()
                if mode == "next_cold":
                    window.cache.clear()
                elapsed, hit = key_to_paint(step)
                values.append(elapsed)
                hits += hit
            results[mode] = {**stats(values), "cache_hits": hits, "samples_ms": [round(x, 3) for x in values]}
        # At a sustained ten keypresses/sec no wait for preloading is inserted.
        window.refresh(window.photos[200].key, rescan=False)
        wait(lambda: not window.canvas.image.isNull())
        settled()
        values, hits = [], 0
        for _ in range(30):
            begin = time.perf_counter()
            elapsed, hit = key_to_paint(1)
            values.append(elapsed)
            hits += hit
            while time.perf_counter() - begin < .1:
                app.processEvents()
                time.sleep(.001)
        results["next_at_10_keys_per_second"] = {**stats(values), "cache_hits": hits,
                                                   "samples_ms": [round(x, 3) for x in values]}
        result = {"label": label, "version": __version__, "source_root": str(Path(source_root)),
                  "dataset": manifest, "viewport": [1440, 960], "dpr": window.devicePixelRatioF(),
                  "canvas": [window.canvas.width(), window.canvas.height()],
                  "backend": "Windows QWidget raster; hidden window", "target_ms": 100,
                  "method": "Keypress to matching decoded frame and completed QWidget paint; 30 samples each. "
                            "Warm next/previous wait for background preloading; cold next explicitly clears the app cache. "
                            "10 keys/sec does not wait for preload. OS disk cache uncontrolled; no display scanout measurement.",
                  "results": results}
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(result, indent=2), "utf-8")
        print(json.dumps({k: {f: v for f, v in value.items() if f != "samples_ms"}
                          for k, value in results.items()}, indent=2))
    finally:
        settled()
        window.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--source-root", default=str(ROOT))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    measure(args.label, args.source_root, args.output)
