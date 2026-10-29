# 1.6 review · before / after

Generated photos only. Before is 1.5.0b1, after is 1.6.0b1, from the same
`scripts/polish_capture.py` scenes at DPR 1.0, 1.25 and 1.5 (1440×960 physical,
1920×1080 at 150 %). Each set has a `capture.json` with its geometry checks.

| Screen | Before 100% | After 100% | After 125% | After 150% |
|---|---|---|---|---|
| Arrow-key choice (new) | — | [View](after/100/keys.png) | [View](after/125/keys.png) | [View](after/150/keys.png) |
| Start | [View](before/100/start.png) | [View](after/100/start.png) | [View](after/125/start.png) | [View](after/150/start.png) |
| Round 1 | [View](before/100/round1.png) | [View](after/100/round1.png) | [View](after/125/round1.png) | [View](after/150/round1.png) |
| Round 2 | [View](before/100/round2.png) | [View](after/100/round2.png) | [View](after/125/round2.png) | [View](after/150/round2.png) |
| Burst | [View](before/100/burst.png) | [View](after/100/burst.png) | [View](after/125/burst.png) | [View](after/150/burst.png) |
| Summary | [View](before/100/summary.png) | [View](after/100/summary.png) | [View](after/125/summary.png) | [View](after/150/summary.png) |
| Import dialog | [View](before/100/import.png) | [View](after/100/import.png) | [View](after/125/import.png) | [View](after/150/import.png) |
| Contact sheet | [View](before/100/contact.png) | [View](after/100/contact.png) | [View](after/125/contact.png) | [View](after/150/contact.png) |

Checks (all scales): Undo / Previous / Next have the Keep / Reject height and
≥ 3:1 disabled contrast, Previous / Next are centred when the row has room, the
file name stays whole; chooser cards are whole; burst images fit their panes with
16 px margins; import paths are never cut from the left and fit their fields.

The refreshed after captures show the active Reject key (← for Fast culling,
X for Browse first). Tooltips and Help list the same map, including alternate
keys. During copying, Import and open is disabled and Cancel is the primary,
default action. The import scene uses the dialog's copying state. Contact sheets
preserve each photo's aspect ratio in fixed rows for PDF pagination; unused image
space uses the paper colour (#f1f0eb).

```powershell
.\.tools\python312\tools\python.exe scripts/polish_capture.py --output docs/polish-1.6/after/100 --scale 1 --check
.\.tools\python312\tools\python.exe scripts/polish_capture.py --output docs/polish-1.6/after/125 --scale 1.25 --check
.\.tools\python312\tools\python.exe scripts/polish_capture.py --output docs/polish-1.6/after/150 --scale 1.5 --check
```
