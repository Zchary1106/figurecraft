# Installation and runtime readiness

FigureCraft uses the same portable skill files for all supported hosts on macOS
and Windows. The one-command installer adds a managed Python runtime; Python
itself, native Cairo, and fonts are not bundled. Copy-only installation does
**not** prove a host can render figures.

## One-command installation

Install Python 3.11+ from python.org if needed, download the project, and run from
the project directory:

```sh
# macOS
bash ./install.sh
```

```powershell
# Windows PowerShell 5.1 or PowerShell 7
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Both default to `--setup --scope user --agent all`. They find a suitable Python,
create one isolated runtime, install Python dependencies from `pyproject.toml`,
check SVG/Draw.io readiness, then install the core and six specialists into each
host. All selected hosts share the same runtime. No global pip installation,
administrator permission, shell-profile edit, or persistent execution-policy
change is made. Network access is needed to download Python dependencies.

Append the same Python-style options to either script:

| Option | Effect |
| --- | --- |
| `--agent codex`, `claude`, or `copilot` | Install one host instead of all three |
| `--scope project --project "path with spaces"` | Install into one project |
| `--force` | Replace installed copies, preserving local edits in backups |
| `--require-export` | Require native-Cairo diagram PNG/PDF before copying skills |
| `--cairo-dir "absolute path"` | Configure an existing native-library directory for this runtime only |
| `--runtime-root "absolute path"` | Override the directory holding versioned runtimes |

Use `FIGURECRAFT_PYTHON` to choose a particular Python executable. Windows also
supports the standard `py -3` launcher. The direct equivalent, using a Python
3.11+ executable, is `python install.py --setup --agent all --scope user`.

### Runtime behavior and upgrades

User runtimes live under `~/.figurecraft/runtimes/<id>/` (Windows:
`%USERPROFILE%\.figurecraft\runtimes\<id>\`). Project runtimes live under the
target project's `.figurecraft/runtimes/<id>/`. Each setup creates a fresh runtime;
failed dependency installation or readiness checks remove only that new runtime,
before any skill copies are installed. Existing installations are preflighted
for all selected hosts before setup starts.

Each installed core records the absolute interpreter path in
`scripts/.figurecraft-runtime.json`. Calling `python scripts/figure.py ...`
dispatches to that interpreter automatically. Copy-only `--force` upgrades retain
an existing runtime binding. Do not copy these bindings between machines; rerun
setup if the configured runtime was moved or deleted. Installer errors return a
nonzero exit status; copy failures are rolled back per host, not across hosts
already installed successfully.

Old runtimes are retained so prior installed copies and backups still work.
Remove an old runtime only after checking that no active or backed-up skill copy
you need references it. Native-library search paths affect FigureCraft processes
only. Standard Homebrew Cairo directories are detected on macOS; custom or
Windows MSYS2 installations can use `--cairo-dir`, for example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 --cairo-dir "C:\msys64\mingw64\bin" --require-export
```

Default setup reports missing native Cairo/CJK fonts as optional limitations.
It does not claim diagram PNG/PDF works just because CairoSVG was installed.
Statistical-chart PNG/PDF uses Matplotlib instead of Cairo.

## Host locations

Run the repository installer from its checkout:

```sh
python3 install.py --agent all --scope project --project /path/to/project
```

Without `--setup`, this copies skills only and does not install dependencies.

| Host | Project scope (under `--project`) | User scope (`--scope user`) |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |

Each location receives the core `figurecraft` and six specialist directories.
Use `--agent claude`, `copilot`, or `codex` to install only one host.
Existing copies are unchanged without `--force`. With `--force`, the installer
stages all files first and preserves existing copies, including local edits, in
`<skills directory>/.figurecraft-backups/<unique id>/<skill name>/`. A copy or
replacement error rolls back replacements; backups are never silently deleted
after a successful install. Review these backups before removing them manually.
Source-overlapping targets and symlinked target/source skill paths are rejected.
The installer writes only inside the selected skills directory.

## Upgrading from VizWeaver

The suite is now FigureCraft: use `figurecraft` and `figurecraft-*` skill names,
`skills/figurecraft/scripts/figure.py`, and the `figurecraft-skill` Python package.
In the same Python environment where the old package was installed, run:

```sh
python3 -m pip uninstall vizweaver-skill
python3 -m pip install -e ".[export]"
```

Reinstall the skills with the installer above. It creates the new names without
deleting old `vizweaver*` directories or their backups. If you previously installed
the old names, preserve any local edits, then move those seven old directories
outside the host's skill-discovery directory to avoid duplicate suggestions.
`--force` replaces only the new names; it does not migrate customized old copies.

Existing FigureSpecs need no conversion. Rendering into an existing delivery
accepts legacy manifest names while retaining artifact-integrity protections.
New manifests and delivery metadata use FigureCraft; historical image files and
versioned snapshots are not rewritten simply because the project was renamed.

## Python dependencies

Python 3.11 or newer is required. In an environment you control:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "matplotlib>=3.8" "numpy>=1.26" "jsonschema>=4.20" "PyYAML>=6.0"
.venv/bin/python skills/figurecraft/scripts/figure.py check-env
```

On Windows use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.
For an installed copy replace `skills/figurecraft` with the host path from the
table. JSON input does not require PyYAML; YAML input does.

The report performs imports and small in-memory operations, not merely package
version lookups. The default check gates readiness on the baseline diagram SVG
pipeline while reporting optional capabilities. An unavailable optional export
or CJK font does not fail this baseline check.

```sh
.venv/bin/python skills/figurecraft/scripts/figure.py check-env --format svg --format drawio
.venv/bin/python skills/figurecraft/scripts/figure.py check-env --kind chart.line --format png --format pdf
.venv/bin/python skills/figurecraft/scripts/figure.py check-env --format png --format pdf --cjk
```

Explicit formats require their tested pipeline to work. Diagram SVG/draw.io need
Matplotlib font metrics (and its NumPy runtime) plus JSON Schema validation.
Charts and Gantt PNG/PDF exports use Matplotlib directly, **not CairoSVG**.
The JSON report is available with `--json`. Remediation commands name the exact
current Python interpreter. Checks never install dependencies or change process
environment variables.

## Optional diagram PNG/PDF

```sh
.venv/bin/python -m pip install "CairoSVG>=2.7"
```

Also install native Cairo:

- macOS: `brew install cairo`.
- Debian/Ubuntu: `sudo apt-get install libcairo2`.
- Windows: install Cairo through MSYS2, for example
  `pacman -S mingw-w64-x86_64-cairo`, and make its `bin` directory available to
  the Python process; match Python and Cairo architectures.

Apple Silicon Homebrew typically provides
`/opt/homebrew/lib/libcairo.2.dylib`. If library discovery fails, use a
command-scoped setting rather than modifying application code or global shell
configuration:

```sh
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python skills/figurecraft/scripts/figure.py check-env --format png --format pdf
```

The check imports CairoSVG, calls the native Cairo runtime, and converts a tiny
SVG to each raster/PDF format. A distribution marked “installed” can still fail
these checks because of a missing shared library or architecture mismatch.

## Chinese/CJK labels

Font availability is always reported; `--cjk` makes it required. The
sample `中文图表` is measured using the same glyph-aware typography code as
diagram labels. Passing the sample is not a guarantee for every character.

- Linux: `sudo apt-get install fonts-noto-cjk` (Noto Sans CJK SC).
- macOS: enable PingFang SC in Font Book, or install Noto Sans CJK SC.
- Windows: enable Microsoft YaHei, or install Noto Sans CJK SC.

Restart the Python process after installing fonts. For a custom font set
`style.overrides.svg_font_family` to its installed family name. Missing glyphs
are errors, not silently substituted boxes. Keep the original FigureSpec,
editable/vector outputs, and fonts or font requirements together when handing
figures to another machine.
