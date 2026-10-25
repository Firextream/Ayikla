# Development

Windows x64 and Python 3.12. Run these PowerShell commands from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\run.ps1
.\.venv\Scripts\python.exe -m pytest --basetemp .tmp\pytest-local -q
.\build.ps1
.\.venv\Scripts\python.exe scripts\verify_frozen.py
.\.venv\Scripts\python.exe scripts\verify_frozen.py --windows
.\.venv\Scripts\python.exe scripts\package_release.py
```

Tests use generated files, never real photos. Use a new `--basetemp` directory for each run. Keep project temporary files under `.tmp`.

The build uses `.venv`, or the project-local `.tools/python312/tools/python.exe` fallback. It stages the new package and preserves the previous bundle in `.tmp/replaced-builds`. Local portable settings are copied into the new `dist/Ayikla` folder.

`package_release.py` creates the shareable ZIP: executable, runtime/licenses, shortcut script and English quick guide. Personal settings and shoot journals are excluded. Existing ZIPs are never overwritten. Update the app, project and Windows version fields together. `dist` and developer tools are ignored by git; executables are distributed via GitHub Releases.

To reproduce benchmarks, use `scripts/benchmark.py generate`, then `measure <label>` and `startup <label> <exe-path>`. Generation writes about 2.5 GB of synthetic data under `.tmp/benchmark`. [Method and earlier results (Turkish)](../RAPOR.md).

## Change boundaries

- Never delete photos or overwrite destinations. Journal durably before moving/copying.
- Undo must preserve exact paths and work after reopening.
- Pair case-insensitively; ignore helper, hidden and system files.
- Add regression coverage for behavior changes. Discuss new features separately.
- Do not request private photos, settings or complete shoot journals in public reports.
