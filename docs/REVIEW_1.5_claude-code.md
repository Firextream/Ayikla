# Ayikla 1.5 → 1.6 — review and fix list (brief for Claude Code, 29 Oct 2026)

Repo: C:\Users\edmes\Desktop\03 Projeler\Ayikla (Python 3.12 + PySide6). Codex built 1.0–1.5; you take over. Talk to Emir in Turkish, short.
Start in plan mode: read README.md, BETA.md, docs/POLISH_1.5.md, docs/polish-1.5/README.md, ayikla/ui.py, ayikla/core.py and the tests. Then show the plan and wait for Emir's "ok".
House rules (never break): English UI · keyboard-first · never delete or overwrite photos · every file op journaled before it runs · Z undo survives restart · suggestions never act on their own · folder names (01_secilen, _red, 02_edit) unchanged.
Tooling: `.\.tools\python312\tools\python.exe -m pytest -q`, `scripts/polish_capture.py --check` for screenshots, `build.ps1` + `scripts/verify_frozen.py` for the exe. One commit per item group. Ask before tagging or pushing.

Review basis: docs/polish-1.5/after/{100,125}/*.png, docs/import-card.png, docs/contact-sheet.png, keyPressEvent in ui.py.

## A. Navigation and undo (Emir: "the back button is gone") — do first
1. Previous/Next are bare orange "↑ ↓" glyphs next to Reject; Undo is faint text in the status row. Make them real buttons in the button row, same height as Reject/Keep, neutral colour: `Undo · Z` (left), `← Previous` / `Next →` (middle), `Reject · Delete` / `Keep · →` (right). Disabled state readable (≥3:1).
2. Key map — DECIDED by Emir (29 Oct): on first launch show a one-screen chooser "How do you want to use the arrow keys?" with two cards:
   - **Fast culling (default, Emir's choice):** → Keep, ← Reject, ↑/↓ previous/next (today's map).
   - **Browse first:** ← → previous/next, Enter Keep, X/Delete Reject.
   Changeable any time in Settings → Arrow keys. In both modes: Backspace/PageUp = Previous, PageDown = Next, and after every Reject a clear 3 s toast "Rejected IMG_0001 · Z to undo". Help (H) shows the active map.
3. Clicking the left/right third of the photo = Previous/Next (cursor hint on hover). Double-click = 100 % zoom (same as F).

## B. Labels and duplicates
4. The lone "↗" icon (open folder) → text `Open folder`.
5. Round 2 shows the same state three times ("Edit pick" chip + "Picked for editing" toast + status text). Keep the chip, drop the status-row repeat; toast only on change.
6. Status-row `Retry` → `Rescan folder` (tooltip: re-reads the folder and recovers interrupted operations).
7. Summary toast "Edit-pick handoff saved" is jargon → "Picks saved for Yazı" (and only if the picks file changed).
8. Summary card: the "Also save PDF" row has a dark block behind the checkbox — align it with the other rows, no background.

## C. Burst compare
9. Images use maybe 60 % of each pane; fit them to the pane (16 px margin), keep the 2 px keeper border and number badges. Shorten the header hint to "1–4 pick · Shift+Enter keep this, reject others · Esc back".

## D. Import from card (docs/import-card.png)
10. Long paths are cut from the left and unreadable → show `…\DCIM\100CANON` style middle-elided paths with full path in tooltip; dialog resizable, min width 720.
11. Progress: "Scanning… 142 / 380 files · 1.2 GB · ~40 s"; show the final folder name preview `2026-10-29_club` under Shoot name.
12. Auto-detect removable drives with a DCIM folder and offer them first.

## E. Contact sheet (docs/contact-sheet.png)
13. "1 frames" → correct plural. Title = shoot name + date, not "AYIKLA / EDIT PICKS".
14. Hide missing metadata lines (no "No lens metadata" ×3); for scans show just the filename.
15. Grid: 3 columns for ≤9 picks, 4 above; A4/letter-friendly PDF margins.

## F. Small polish
16. Start screen headline got small after 1.5 — restore ~28 px and keep the cards' full text visible at 100/125/150 %.
17. Help (H) overlay: group keys by Round 1 / Round 2 / Anywhere, reflect the chosen arrow-key mode.

## Done when
- Tests pass (add tests for new keys, click zones, arrow-key setting, plural/metadata on the contact sheet).
- polish_capture before/after at 100/125/150 % for start, round 1, round 2, burst, summary, import dialog, contact sheet.
- Frozen exe verified, version 1.6.0b1, README/BETA updated. Show Emir the screenshots, then commit. Ask before pushing.
