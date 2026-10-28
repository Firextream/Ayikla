# Ayikla 1.5.0b1 · Photo club beta

Cull JPG/JPEG + RAW shoots or standalone JPEG/TIFF scans in two rounds: choose what to keep, then what to edit in Lightroom. Windows x64. No Python installation required.

## Start

1. Extract the whole ZIP into a writable folder. Keep `Ayikla.exe` and `_internal` together; do not run from inside the ZIP.
2. For your first test, use a **separate copy of 20–50 photo pairs** and keep an independent backup of your original shoot. The app moves files in the selected folder.
3. Open `Ayikla.exe` → **Open**. Select the folder directly containing the JPEGs; nested folders are not scanned.

This package is unsigned. If Windows prevents it from opening, report the warning text and version. Do not disable your security software.

## Two rounds

| Action | Key | Result |
|---|---|---|
| Keep | → / Enter | Moves JPG + matching RAW to `01_secilen` |
| Reject | ← / X / Delete | Moves the pair to `_red`; **not permanent deletion** |
| Undo | Z | Restores exact original paths; works after reopening too |
| Navigate without deciding | Space / ↓ / ↑ | Does not move photos |
| Switch to edit picks | M | Choose from your kept photos |
| Pick / unpick for editing | E | Copies the pair to `02_edit`; unpicking archives the copies |
| Check focus | F; drag | 100% zoom / pan; F again to fit |
| Burst compare | B | 2-up / 4-up; left/right page through the burst |
| Choose keeper | 1–4 in compare | Select a frame without changing files |
| Confirm burst | Shift+Enter | Keep selected and reject all other burst frames; one Z undoes the group |
| Color ideas (round 2) | C | Filter by tone or find similar palettes; click a result, then E to pick it |
| Info / filmstrip / help | I / T / H | Toggle the panel |
| Full screen | F11 | Toggle window / full screen |
| Import from card | Ctrl+I | Verified copies; remembers destination root |
| Contact sheet | Ctrl+Shift+E in round 2 summary | Export JPEG; optional PDF checkbox |

Decisions are saved automatically. **Folders** opens your kept, rejected and edit files. Import `02_edit` into Lightroom yourself. Folder names are unchanged from the Turkish release for compatibility.

Keep `_red`, `.ayikla_saklanan` and `ayikla_log.jsonl`. The app does not delete photos or overwrite existing destinations. Press **Retry** to rescan after external changes. macOS `._` helper files are ignored. Corrupt JPEGs can still be kept/rejected; encountered decoding failures are listed in the round summary.

## Visual polish in 1.5

Start-screen cards no longer clip their body text. Header controls use aligned
menu arrows and consistent gaps. A single top-right progress line replaces the
repeated counters; file information and photo actions share one bottom row.
Round instructions are in Help and ignored-file counts are in Folders. The
image has 16 px fit margins, with the burst badge on its corner. Burst compare
adds an explicit keeper border and numbered image badges. Font sizes use
12 / 13 / 15 / 20 px. Disabled text controls have at least 3:1 measured contrast.

Keys, decisions, journals and file safety are unchanged. Background preloading
of the next two / previous one photos was already present and is verified.
On generated 24 MP JPEGs, preloaded Next median was 4.48 ms in 1.4 and 4.24 ms
in 1.5 (P95 6.45 / 4.90 ms). These are same-machine key-to-widget-paint results,
not a claim about every disk or monitor; cleared-cache reads are about 104 ms.
See `docs/polish-1.5/README.md` and `docs/benchmark/navigation-1.5.md`.

## Also included from 1.4

- **Resume:** each shoot journal remembers the round, filename and capture time.
  Reopening resumes with a toast and **Start from first** action. If the saved
  photo moved or was renamed, fallback uses the nearest undecided capture time
  (natural filename order if EXIF is missing). Decisions remain unchanged.
- **Progress:** round 1 shows decided / total and an approximate remaining time
  after ten decisions this session, using the median seconds per frame. Round 2
  shows edit picks. Opening another shoot resets the pace estimate.
- **Import:** Ctrl+I copies supported JPEG/TIFF/RAW from nested card folders into
  `<root>/YYYY-MM-DD_<name>`. Destination root is remembered. New files are verified
  by size and SHA-256; identical copies are skipped and collisions never overwrite.
  Cancel removes partial staging data and keeps verified files. Z archives the
  batch's new copies, including after restarting. The source/card stays untouched.
  Keep `ayikla_import.jsonl`; it contains local source paths, so do not publish it.
- **Contact sheet:** round 2 summary → Export contact sheet, or Ctrl+Shift+E.
  Check Also save PDF if needed. Edit picks appear in a JPEG grid with filename
  and key EXIF. Exports go into `02_edit/contact_sheet_<date>.jpg` / `.pdf`, with
  numbered names for repeat exports. One Z archives both outputs. Extremely
  large sheets require a smaller selection (80 MP / 65,000-pixel height limit).

## Also included from 1.3

- **Burst compare:** F zooms all panes and drag pans them together. Esc returns
  to the keeper after confirmation. Remove existing edit picks before changing
  the burst's decisions.
- **XMP:** Settings → Write Lightroom XMP sidecars is on by default. Keep = one
  star + Pick; edit copy = three stars; Reject = Rating -1 + Reject. Existing
  XMP is archived first; Camera Raw adjustments and other metadata are preserved.
  Undo restores the original sidecar bytes after restart. Lightroom import and
  metadata refresh are manual; flag support requires Classic 13.2 or later.
  JPEG/TIFF sidecar recognition varies by editor/version; test your workflow.
- **Film scans:** standalone JPG/JPEG and TIF/TIFF work automatically. Missing
  EXIF shows “—”. Color ideas accepts TIFF. 16-bit conversion affects only the
  preview. Some TIFF decoders need full source memory before reducing the
  preview; multipage files show their first page.
- **Yazı handoff:** edit-pick changes and the round 2 summary refresh
  `02_edit/ayikla_picks.json`. It contains metadata, palette swatches and empty
  captions. See `docs/picks-schema.md`; keep authored captions in Yazı's own
  data. JSON updates are archived and included in selection undo.

## Five-minute test

Keep two photos, reject one, then press Z. Close and reopen the shoot: do decisions and undo still work? Press M → E and check the JPG+RAW copies in `02_edit`. Try F for focus, I for EXIF and T for the filmstrip.

## Feedback

Open a feedback or bug report at **https://github.com/Firextream/Ayikla/issues**. English and Turkish are welcome.

- App version: **1.5.0b1**, also shown in H help.
- Windows version, display resolution and scaling (100%/125%/150%).
- Camera, photo count and storage type (internal/external/SD card).
- What did you do? What did you expect? What happened? Can you reproduce it?
- Was Keep vs Edit clear? Which step felt slow or confusing?

Do not attach private photos, `ayikla_settings.jsonl` or complete decision journals. Hide personal names/paths in screenshots. Start with the error text; a small generated sample can be requested if needed.

## Beta limits

JPG/JPEG pairs with RAF (Fuji), ARW/SRF/SR2 (Sony), ORF (Olympus), CR3/CR2/CRW, NEF/NRW, RW2/RWL, PEF, SRW and DNG. Matching filename stems are required. RAW-only and HEIC are not supported. RAW images are not decoded. Lightroom import is manual. Other computers, high DPI/multiple monitors, real card removal and physical power loss have not been field-tested. Minimum window size is 1024×680 logical pixels; scaling reduces available space. ICC/color accuracy has not been validated. This is a small-club beta, not a broadly validated stable release.

## Color ideas

Press C in round 2. Select a tone and minimum frame coverage, or find similar palettes to the current photo. Up to 24 matches are shown. Click a frame to return to it; E is still your explicit edit-pick action. Analysis uses small JPEG/TIFF previews locally, never changes files, and is cancelled when you close the panel. Color matches are approximate, influenced by camera style, scan processing and lighting, and do not rate photographic quality.
