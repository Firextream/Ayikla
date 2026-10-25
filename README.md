# Ayikla

**Find your best frames. Build your shortlist.**

A simple, keyboard-first Windows photo culling app for RAW+JPEG shoots. First choose what to keep, then pick what to edit in Lightroom.

**Windows x64 · English interface · JPG/JPEG + common camera RAW formats · 1.2.0b1 Beta**

### [Download for Windows · ZIP](https://github.com/Firextream/Ayikla/releases/download/v1.2.0b1/Ayikla-1.2.0b1-Windows-x64.zip)

[Release notes](https://github.com/Firextream/Ayikla/releases/tag/v1.2.0b1) · [Share feedback](https://github.com/Firextream/Ayikla/issues/new?template=feedback.md) · [Report a bug](https://github.com/Firextream/Ayikla/issues/new?template=bug_report.md)

![Ayikla gallery with a neutral dark interface and Keep / Reject controls](docs/gallery.png)

*The photos in these screenshots are generated test images, not personal photographs.*

## Get started

1. Download the Windows ZIP above and extract **the entire archive**. GitHub's “Source code” archives are not the runnable app.
2. Open `Ayikla/Ayikla.exe`. **No Python installation needed.** Keep `_internal` next to the executable.
3. Choose **Open folder** and select the folder containing your JPEGs. Start with a separate copy of 20–50 photo pairs for your first beta test.

The package is unsigned, so Windows may show a warning. If it will not open, report the exact message; do not disable your security software. The included `MasaustuKisayolu.ps1` script can create an optional desktop shortcut without overwriting an existing one.

## Keep or pick for editing?

| Round | Your decision | What happens to the files |
|---|---|---|
| **1 · Keep / Reject** | Which frames should I keep? | Keep moves JPG + matching RAW to `01_secilen`; Reject moves them to `_red`. |
| **2 · Edit / Lightroom** | Which kept frames should I edit? | Press M, then E to **copy** JPG + RAW into `02_edit`. |

**Delete means Reject, not permanent deletion.** Z undoes the last decision, including after restarting the app. Decisions are saved automatically; there is no separate Save button. Import `02_edit` into Lightroom Classic yourself.

Folder names stay the same as earlier Turkish builds so existing shoots and journals continue to work.

## Keyboard

| Key | Action |
|---|---|
| → / Enter | Round 1: Keep → `01_secilen` |
| ← / X / Delete | Round 1: Reject → `_red`; no permanent deletion |
| Space / ↓ | Next photo without deciding; show summary at the end of round 2 |
| ↑ | Previous photo |
| Z | Undo the last decision, including after a restart |
| M | Switch between culling and edit picks |
| E | Round 2: copy to `02_edit`; press again to remove the edit pick |
| C | Round 2: color ideas — tone filter and similar palettes |
| F | 100% focus check / fit to window |
| Drag with left mouse button | Pan while zoomed in |
| I | EXIF: filename, time, shutter, aperture, ISO, focal length, lens |
| T | Toggle filmstrip; click a thumbnail to jump |
| H / ? | Keyboard help and app version |
| Ctrl+O | Open another shoot folder |
| F11 | Toggle full screen |
| Esc | Close help, then leave zoom, then leave full screen |

## Color ideas for your next post

In **round 2**, press **C** or **Color ideas**. Choose a tone (red, orange, yellow, green, teal, blue, purple, pink, dark, neutral or light), then require it to cover at least 15%, 30% or 50% of the frame. Or choose **Similar palette to current photo** to find frames that could work together in a post.

Up to 24 matches show thumbnails, palette swatches and color coverage or palette overlap. Click a frame to return to it, then **E** to pick it for editing. Suggestions never automatically select, move or copy anything. Unreadable JPEGs are skipped and listed in the round summary. Analysis runs locally in the background; closing the panel cancels it. Unchanged JPEG descriptors are reused for the current app session.

![Similar palettes among kept photos](docs/colors.png)

These are approximate JPEG color matches, not assessments of composition or photographic quality. Recognized embedded color profiles are converted to sRGB for analysis; untagged JPEGs are treated as sRGB. The camera's JPEG style and lighting influence the suggestions. This does not change the photos or apply a grade to RAW files.

## Camera support

| Camera family | Paired RAW extensions |
|---|---|
| Fujifilm | RAF |
| Sony | ARW, SRF, SR2 |
| Olympus / OM System | ORF |
| Canon | CR3, CR2, CRW |
| Nikon | NEF, NRW |
| Panasonic / Leica | RW2, RWL |
| Pentax / Samsung | PEF, SRW |
| DNG cameras / phones | DNG |

A matching **JPG/JPEG with the same filename stem** is required. RAW files are moved/copied as opaque files; they are not decoded, and support is not a claim that every camera model has been field-tested. RAW-only, HEIC and differently named JPEG/RAW pairs are not supported. If multiple RAW formats share one JPEG stem, Ayikla reports a conflict rather than guessing. Existing shoot folders and journals remain compatible.

## Inspect your photos and reach your files

The **Folders** menu opens the shoot, kept, rejected or edit folder in Explorer and shows current counts. **Open folder ↗** below the photo opens that photo's current folder. The round summary also links to kept and rejected files.

Filmstrip edges: **green = kept, red = rejected, purple = picked for editing**. Rejected photos can be previewed; decision keys are disabled during that preview. Capture times within one second show a **Burst 2/5** hint. Missing EXIF fields show “—”.

Normal previews and thumbnails use scaled decoding; full-resolution decoding is used only for 100% zoom. The last five folders and window/fullscreen state are remembered.

<details>
<summary>See focus check, EXIF, filmstrip and round summary</summary>

**100% focus check**

![100% zoom](docs/zoom.png)

**Photo information**

![EXIF information overlay](docs/info.png)

**Filmstrip**

![Filmstrip with photo states](docs/filmstrip.png)

**Round summary**

![Round summary and folder access](docs/end.png)

</details>

## File safety

- No photo deletion and no overwriting existing destinations. `_red` is never emptied by the app.
- Removed edit copies are moved to `.ayikla_saklanan`. Keep that folder and `ayikla_log.jsonl` for recovery and undo.
- File operations are journaled before they run. On reopening, interrupted operations are recovered when possible. **Retry** retries recovery and rescans the folder after external changes.
- macOS `._*`, `Thumbs.db`, `desktop.ini`, `.DS_Store` and Windows hidden/system files are ignored. They are not counted, displayed, moved or copied.
- A corrupt JPEG can still be kept or rejected. JPEGs that failed to open during the current session appear in the round summary.

Keep an independent backup of your original shoot. The app moves files in the folder you select. It scans immediate JPG/JPEG files only, pairs supported RAW files by case-insensitive filename stem, and does not recurse into other folders.

Portable preferences are stored in `ayikla_settings.jsonl` beside the executable. If that file cannot be read, the app starts with defaults and displays a notice. The shareable release ZIP does not include personal settings or shoot journals.

## Help shape the beta

We especially want feedback on the **Keep vs Edit distinction**, navigation speed, focus checking and folder access. [Share your experience](https://github.com/Firextream/Ayikla/issues/new?template=feedback.md) or [report a reproducible bug](https://github.com/Firextream/Ayikla/issues/new?template=bug_report.md). A GitHub account is required. Reports in English or Turkish are welcome.

Include the version shown in H help, Windows version, display scaling, camera and approximate photo count. Do not post private photos, personal paths, settings files or complete shoot journals.

**173 tests passed**, including reopening and undoing a journal from the previous Turkish release. The package and the app extracted from the ZIP are tested on Windows 11 x64 with generated JPEGs and dummy RAW files. Other computers, high DPI/multiple monitors, real card disconnection and ICC/color accuracy still need field testing. Minimum window size is 1024×680 logical pixels. RAW images are not decoded; automatic Lightroom import is not supported.

[Five-minute beta guide](BETA.md) · [Validation and benchmark report (Turkish)](RAPOR.md) · [Run from source and build](docs/GELISTIRME.md)

Python 3.12 + PySide6; Pillow reads EXIF headers only. Third-party license notices are included in [licenses](licenses/NOTICE.txt) and the app package. No open-source license has been selected for Ayikla's own source yet.
