# Visual polish · before / after

Generated photos only. Before is 1.4.0b1; after is 1.5.0b1. Five identical scenes
are captured through the native Windows Qt backend at DPR 1.0 and 1.25, using
1440×960 physical window captures (compare keeps its own dialog size). The
per-process `QT_SCALE_FACTOR` sets DPI; Windows display preferences are not changed.
An additional DPR 1.5 pass checks wrapping and clipping at 1920×1080 physical size.

| Screen | Before 100% | After 100% | Before 125% | After 125% |
|---|---|---|---|---|
| Start | [View](before/100/start.png) | [View](after/100/start.png) | [View](before/125/start.png) | [View](after/125/start.png) |
| Round 1 | [View](before/100/round1.png) | [View](after/100/round1.png) | [View](before/125/round1.png) | [View](after/125/round1.png) |
| Round 2 | [View](before/100/round2.png) | [View](after/100/round2.png) | [View](before/125/round2.png) | [View](after/125/round2.png) |
| Burst | [View](before/100/burst.png) | [View](after/100/burst.png) | [View](before/125/burst.png) | [View](after/125/burst.png) |
| Summary | [View](before/100/summary.png) | [View](after/100/summary.png) | [View](before/125/summary.png) | [View](after/125/summary.png) |

The gallery canvas grows from **647 to 768 logical px at 100%**, and from
**448 to 573 logical px at 125%** in the round 1 fixture. The two footer rows
contain photo controls and quiet status actions. One progress line is retained
at the top right; hints live in Help and helper counts in Folders.

Geometry checks verify full card body bounds, 24 px menu gaps, image-centered
16 px fit margins, a single visible progress line, no overlapping controls,
2 px keeper borders, image-corner number badges and equal-height compare buttons.
Disabled text-button contrast measures **3.73–3.83:1** against its actual background.

Capture/geometry reports are alongside each set as `capture.json`. The 150%
checks and screenshots are under [after/150](after/150/capture.json).

```powershell
.\.tools\python312\tools\python.exe scripts/polish_capture.py --output docs/polish-1.5/after/100 --scale 1 --check
.\.tools\python312\tools\python.exe scripts/polish_capture.py --output docs/polish-1.5/after/125 --scale 1.25 --check
.\.tools\python312\tools\python.exe scripts/polish_capture.py --output docs/polish-1.5/after/150 --scale 1.5 --check
```

No journal format, file engine, selection action, shortcut or image-decoding
algorithm changes are part of the polish. The existing next-two / previous-one
background preloading is verified by [a 24 MP benchmark](../benchmark/navigation-1.5.md).
