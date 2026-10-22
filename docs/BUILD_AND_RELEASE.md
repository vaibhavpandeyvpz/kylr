# Build and release

The game uses official Godot 4.7.2 stable and matching official export templates.
Windows, macOS and Linux packages use prebuilt binaries. Blender authoring does
not run during packaging. Restore licensed animations and sounds through [asset setup](ASSET_SETUP.md)
before importing or packaging. CI uses
`python tools/install_private_assets.py --download` to restore the configured R2
bundle and clean up its temporary ZIP.

## Local Windows setup

Install Git LFS, PowerShell 7 and Python 3.12. Run `git lfs install` before cloning
and `git lfs pull` after a clone made without LFS. Binary assets and native addons
must contain their actual payloads before import.

From the repository root:

```powershell
python tools/prepare_godot.py --platform windows --templates
$env:GODOT = (Resolve-Path .local/godot/godot_console.exe).Path
```

The installer checks official release archive SHA-512 pins in
`tools/godot-release.json` before extracting files. Downloads remain temporary;
the editor is installed under ignored `.local/godot/` and Windows debug/release
export templates under Godot's per-user `export_templates/4.7.2.stable/` directory.
Update the release and checksum pins together.

Select an existing official installation through `GODOT`, PATH or an explicit
`-Godot` argument. Prefer the console wrapper for redirected diagnostics. Keep
machine-specific paths outside tracked files. On macOS and Linux, install the
official editor and matching templates, set `GODOT`, and use the same PowerShell
7 commands below. Universal macOS exports enable both desktop and Apple Silicon
texture formats in the project settings.

## Verification and packaging

Run game tools from `game/`:

```powershell
./tools/verify.ps1 -Godot $env:GODOT
./tools/package.ps1 -Godot $env:GODOT -Version dev-local
```

Verification imports assets, runs GUT, exercises all five match types and checks
the results flow. Packaging uses installed official templates, writes engine and
third-party notices, checks the native LimboAI release library, inspects PCK contents, smoke-tests
the exported executable and writes a manifest and SHA-256 checksum. Native PE
imports are inspected for unexpected external MSVC runtime requirements. Official
Godot and bundled LimboAI use system Windows/UCRT libraries.

Artifacts are written to `game/build/` and logs to `game/reports/`. Run packaging
on the target OS: Windows and Linux use x86_64, while macOS exports a universal
Intel/Apple Silicon app. Windows and macOS packages are ZIPs; Linux uses tar.gz
to preserve executable permissions. macOS ZIPs preserve app bundles and framework
links through `ditto`. Ship the complete archive. Windows builds are unsigned;
macOS uses ad-hoc signing without notarization. Headless checks cannot qualify rendered
appearance, audio, hardware compatibility or frame rates; follow
[rendering](RENDERING.md) and [playtesting](PLAYTESTING.md).

Exports omit GUT, tools, tests, diagnostic scripts and reports. Exclude
ProtonScatter's editor-only `presets/` scenes and Shaker's samples in
`addons/shaker/data/resources/`; they reference upstream demo assets. Runtime
classes and notices remain included. Preserve Phantom Camera's headless updater
guard and HTTP response validation when updating that addon.

## GitHub workflow

[The desktop workflow](../.github/workflows/package.yml) uses one matrix with
`windows-latest`, `ubuntu-latest` and `macos-latest`. Each runner checks out LFS,
sets up Python and official Godot 4.7.2 with matching export templates through
`chickensoft-games/setup-godot@v2`, restores licensed assets
and packages a native export. Export imports assets once; every OS checks the
exported app, and the full GUT suite runs once on Linux. Builds run independently
with `fail-fast: false`.
The setup action caches its downloads; game tools resolve its Windows alias to
the installed `.exe` and wait through a pipeline. All three packages and checksums
are uploaded as one-day Actions artifacts. Failed jobs also retain their logs.

Configure bucket-scoped R2 credentials, endpoint/object variables and
`PRIVATE_GAME_ASSETS_SHA256` as described in [asset setup](ASSET_SETUP.md). The
workflow checks the private bundle checksum and restores only catalog-required
paths. Credentials and downloaded private archives are not uploaded. Rebuild a
replacement bundle with `tools/bundle_private_assets.py` and update its R2 object
and checksum when licensed content changes. `KYLR_PUBLIC_API_URL` configures the
desktop clients' public API endpoint.

A pushed `v*` tag starts the matrix. One release job waits for all three builds,
downloads their artifacts, verifies SHA-256 checksums and publishes all packages
together to GitHub Releases. Only that job has release write permission. Tags
containing a hyphen are prereleases. Manual dispatch on `main` builds downloadable
artifacts; dispatch on a `v*` tag also publishes a release. Rerunning an old run
uses its original workflow revision; start a new run after workflow changes.
A completed hosted matrix is required to claim validation on all three OSes.

## Multiplayer services

[Cloud hosting](CLOUD_HOSTING.md) owns Render, Atlas and Edgegap configuration.
The manual multiplayer workflow runs one API/publication test suite against
MongoDB, then builds the private server image once. The download stage installs
checksum-pinned official Godot for Linux; the Docker build imports restored
assets and rejects script errors. BuildKit caches binary-download and import
layers. Optional publication uses the Docker login/build actions to push the
source commit as an immutable private image tag, then registers the Edgegap app
version. Hosting credentials never ship to clients.

## Terrain authoring

Terrain3D is used only by the [planetary terrain pipeline](library/PLANETARY_TERRAIN.md).
Game and server packages consume static map meshes and PBR textures, with no
Terrain3D native runtime. Package checks verify manifest resources and desktop
packages include its MIT notice under `licenses/terrain3d/LICENSE.txt`.
