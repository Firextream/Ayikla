# Ayikla 1.5 — visual polish (brief for Codex, 29 Oct 2026)

Talk to Emir in Turkish, short. Plan first, wait for "ok". No new features; behaviour, keys and file safety stay exactly the same.
Goal: the photo is the hero, the chrome gets quieter. Review based on docs/gallery.png, resume.png, burst-compare.png, baslangic.png.

## Must fix (bugs)
1. Start screen cards (01 Keep/Reject, 02 Edit/Lightroom): the two body lines are clipped and overlap ("Keep → 01_secilen", "File / Delete → _red", "Ready to import into Lightroom"). Give the cards real height / wrap; check at 100 %, 125 %, 150 % Windows scaling.
2. Top bar: items are spread with uneven gaps and the dropdown arrows sit off the text baseline. Group them: left = AYIKLA + shoot name; right = Folders ▾ · Open · Settings ▾ · Full screen · Help, fixed 24 px gaps, arrows aligned.

## Calmer layout
3. One counter, not three. Today "1 / 4 · 0 kept · 0 rejected" (top right), "4 undecided" (photo bar) and "Round 1 · 0/4 decided" (status bar) repeat. Keep a single progress line top-right: "Round 1 · 12 / 380 · 9 kept · 3 rejected · ~12 min", remove the others.
4. Bottom chrome: three rows (file row, button row, status row) → two. File name + JPG+CR3 chip + Info/Filmstrip/100 % on the left of the button row; Undo/Start from first/Retry/Auto-save as small text in one status row.
5. The "ROUND 1 · KEEP OR REJECT: …" hint and "8 macOS helper files ignored" line: show once per session for 5 s (or only in Help), not permanently. Helper-file note moves into Folders menu.
6. Photo area: use the freed space — image fits the available area with 16 px margin, centered; burst badge sits on the image's top-left corner (overlay), not floating in the margin.
7. Disabled controls (Undo when nothing to undo, Previous on first photo) use a clearly lower but still readable contrast (WCAG 3:1 for text-like controls).

## Burst compare
8. Selected keeper: 2 px accent border around the image + label, not only green text. Pane headers a bit larger (13 px), equal padding; bottom buttons same height and evenly spaced; show a tiny "1–4" number badge on each image corner.

## Colour and type
9. Keep the neutral dark theme. One accent colour only (current Keep white button is fine); Keep = subtle green edge, Reject = subtle red edge on hover/press so the meaning is visible without reading.
10. One type scale: 12 / 13 / 15 / 20 px; uppercase only for small labels. Check every string fits at 125 % scaling.

## Done when
- Before/after screenshots of: start screen, gallery round 1, round 2, burst compare, end summary — at 100 % and 125 % scaling.
- Tests and frozen-exe verification still pass; version 1.5.0b1. Ask before pushing.
