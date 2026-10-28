# Edit-pick handoff · schema 1

Ayikla writes UTF-8 JSON to `02_edit/ayikla_picks.json` when edit picks change
and refreshes it at the round 2 summary. Yazı or another image adder can read it
without any connection to Ayikla. Ayikla has no dependency on Yazı.

```json
{
  "schema_version": 1,
  "picks": [
    {
      "filename": "IMG_0001.JPG",
      "raw_filename": "IMG_0001.CR3",
      "capture_time": "2026-10-29T12:34:56.180000",
      "camera": "Generated Camera",
      "lens": "Generated 50mm",
      "settings": {
        "shutter": "1/320 s",
        "aperture": "f/2.8",
        "iso": "400",
        "focal_length": "50 mm"
      },
      "palette": ["#517b91", "#d2c4a3", "#3f6458"],
      "caption": ""
    }
  ]
}
```

- `schema_version`: integer `1`; readers should reject unsupported versions.
- `picks`: array, naturally sorted by filename; empty when there are no picks.
- `filename`: JPEG/TIFF basename relative to the JSON's directory, including its
  original spelling. It names the preview image to add, not the RAW. No absolute
  paths or parent-directory traversal are emitted.
- `raw_filename`: matching RAW basename or `null`.
- `capture_time`: ISO 8601 capture time with optional fractional seconds, or
  `null`. EXIF has no guaranteed timezone; do not assume UTC.
- `camera`, `lens`: strings, or `null` when missing.
- `settings`: shutter, aperture, ISO and focal-length display strings, each
  nullable. These values include units and are not numeric measurements.
- `palette`: zero to five lowercase `#rrggbb` preview swatches. Reuses Color
  ideas' cached descriptor when available; otherwise computes the same local
  descriptor. An unreadable image has an empty palette and remains a pick.
- `caption`: empty string reserved for the consumer. Store written captions in
  the consumer's own data; Ayikla regenerates this handoff with empty captions.

All fields above are emitted for every pick. Readers should ignore unknown
fields in schema 1. TIFF/JPEG pixels and embedded metadata are never changed.
JSON replacements first archive the previous file in `.ayikla_saklanan` and are
journaled with the selection. Undo restores the previous handoff, including
after restarting. Do not remove the journal or archive. Readers should retry
briefly if the file is absent during archive-and-publish or a recovered operation.

The core Python API keeps sidecar generation opt-in (`export_picks=True`,
`write_xmp=True`) for existing integrations. Both are enabled by the desktop
application; only XMP has a user setting.
