# 24 MP navigation · 1.4 versus 1.5

Both versions already preload the next two and previous one photos in background
threads. This measurement verifies that path; it does not credit 1.5 with adding
an existing feature. No decision, keyboard or image-file behavior changed.

| Scenario | 1.4 median / P95 | 1.5 median / P95 | 1.5 cache hits |
|---|---:|---:|---:|
| Next, preloaded | 4.48 / 6.45 ms | 4.24 / 4.90 ms | 30 / 30 |
| Previous, preloaded | 4.11 / 5.75 ms | 4.12 / 5.30 ms | 30 / 30 |
| Next, app cache cleared | 104.08 / 134.05 ms | 104.14 / 118.16 ms | 0 / 30 |
| Next at 10 keypresses/sec | 4.31 / 6.88 ms | 4.02 / 4.76 ms | 30 / 30 |

The **under-100 ms target is met for preloaded Next/Previous**, including the
sustained sequence. Cold reads remain above the target; an arbitrary jump or
navigation faster than decoding can still miss the cache. The small warm-cache
difference is not evidence of a major speed improvement. The fuller viewport in
1.5 did not materially worsen the measured navigation latency.

## Method

- Same generated folder: 300 JPEGs, 6000×4000, mean 8,303,674.5 bytes (~8.3 MB).
  Four seeded high-entropy templates with unique EXIF timestamps, not padded files.
- Baseline: unmodified `ayikla` source from commit `7131854`, extracted under
  `.tmp/nav-baseline-1.4-source`. After: working 1.5 code, same interpreter,
  machine, dataset and method. The source dataset is never written by the test.
- Windows Qt backend, 1440×960 logical viewport, DPR 1.0, fit mode, filmstrip off.
  Native windows are hidden to avoid interrupting the desktop.
- `QTest` sends Down (Next) or Up (Previous). Timing stops after the target frame
  is decoded and the widget's raster paint finishes. This excludes monitor
  scanout/compositor latency and cannot claim end-to-end display response.
- 30 samples per scenario. Warm scenarios wait for the background queue before
  each key. Cold scenarios clear only Ayikla's application cache. The 10-keys/sec
  scenario does not wait for preloading between keys. OS disk cache is uncontrolled.
- New run folders use hard links to generated JPEGs and contain their own
  navigation journals. No benchmark decisions move or edit source photos.

Raw samples: [1.4](navigation-v1.4-before.json), [1.5](navigation-v1.5-after.json).

```powershell
.\.tools\python312\tools\python.exe scripts/benchmark_navigation.py v1.4-before --source-root .tmp/nav-baseline-1.4-source --output docs/benchmark/navigation-v1.4-before.json
.\.tools\python312\tools\python.exe scripts/benchmark_navigation.py v1.5-after --output docs/benchmark/navigation-v1.5-after.json
```

The regression test also checks that decoding runs off the GUI thread, exactly
the intended neighbor set is requested/cached, immediate forward/back cache hits
work, and navigation does not add decisions to the undo stack.
