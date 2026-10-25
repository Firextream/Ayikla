# Ayikla 1.2.0b1 · Photo club beta

Cull JPG/JPEG + RAW shoots in two rounds: choose what to keep, then what to edit in Lightroom. Windows x64; this build is verified on Windows 11. No Python installation required.

## Start

1. Extract the whole ZIP into a writable folder. Keep `Ayikla.exe` and `_internal` together; do not run from inside the ZIP.
2. For your first test, use a **separate copy of 20–50 photo pairs** and keep an independent backup of your original shoot. The app moves files in the selected folder.
3. Open `Ayikla.exe` → **Open folder**. Select the folder directly containing the JPEGs; nested folders are not scanned.

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
| Color ideas (round 2) | C | Filter by tone or find similar palettes; click a result, then E to pick it |
| Info / filmstrip / help | I / T / H | Toggle the panel |
| Full screen | F11 | Toggle window / full screen |

Decisions are saved automatically. **Folders** opens your kept, rejected and edit files. Import `02_edit` into Lightroom yourself. Folder names are unchanged from the Turkish release for compatibility.

Keep `_red`, `.ayikla_saklanan` and `ayikla_log.jsonl`. The app does not delete photos or overwrite existing destinations. Press **Retry** to rescan after external changes. macOS `._` helper files are ignored. Corrupt JPEGs can still be kept/rejected; encountered decoding failures are listed in the round summary.

## Five-minute test

Keep two photos, reject one, then press Z. Close and reopen the shoot: do decisions and undo still work? Press M → E and check the JPG+RAW copies in `02_edit`. Try F for focus, I for EXIF and T for the filmstrip.

## Feedback

Open a feedback or bug report at **https://github.com/Firextream/Ayikla/issues**. English and Turkish are welcome.

- App version: **1.2.0b1**, also shown in H help.
- Windows version, display resolution and scaling (100%/125%/150%).
- Camera, photo count and storage type (internal/external/SD card).
- What did you do? What did you expect? What happened? Can you reproduce it?
- Was Keep vs Edit clear? Which step felt slow or confusing?

Do not attach private photos, `ayikla_settings.jsonl` or complete decision journals. Hide personal names/paths in screenshots. Start with the error text; a small generated sample can be requested if needed.

## Beta limits

JPG/JPEG pairs with RAF (Fuji), ARW/SRF/SR2 (Sony), ORF (Olympus), CR3/CR2/CRW, NEF/NRW, RW2/RWL, PEF, SRW and DNG. Matching filename stems are required. RAW-only and HEIC are not supported. RAW images are not decoded. Lightroom import is manual. Other computers, high DPI/multiple monitors, real card removal and physical power loss have not been field-tested. Minimum window size is 1024×680 logical pixels; scaling reduces available space. ICC/color accuracy has not been validated. This is a small-club beta, not a broadly validated stable release.

## Color ideas

Press C in round 2. Select a tone and minimum frame coverage, or find similar palettes to the current photo. Up to 24 matches are shown. Click a frame to return to it; E is still your explicit edit-pick action. Analysis uses small JPEG previews locally, never changes files, and is cancelled when you close the panel. Color matches are approximate, influenced by camera style and lighting, and do not rate photographic quality.
