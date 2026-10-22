# Build and release

The game uses official Godot 4.7.2 stable and matching official export templates.
Windows packages and Linux servers use prebuilt binaries. Blender authoring does
not run during packaging. Restore licensed animations and sounds through [asset setup](ASSET_SETUP.md)
before importing or packaging.

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
machine-specific paths outside tracked files.

## Verification and packaging

Run game tools from `game/`:

```powershell
./tools/verify.ps1 -Godot $env:GODOT
./tools/package_windows.ps1 -Godot $env:GODOT -Version dev-local
```

Verification imports assets, runs GUT, exercises all five match types and checks
the results flow. Packaging uses installed official templates, writes engine and
third-party notices, checks LimboAI's release DLL, inspects PCK contents, smoke-tests
the exported executable and writes a manifest and SHA-256 checksum. Native PE
imports are inspected for unexpected external MSVC runtime requirements. Official
Godot and bundled LimboAI use system Windows/UCRT libraries.

Artifacts are written to `game/build/` and logs to `game/reports/`. Ship the complete
ZIP. Windows builds are unsigned. Headless checks cannot qualify rendered
appearance, audio, hardware compatibility or frame rates; follow
[rendering](RENDERING.md) and [playtesting](PLAYTESTING.md).

Exports omit GUT, tools, tests, diagnostic scripts and reports. Exclude
ProtonScatter's editor-only `presets/` scenes and Shaker's samples in
`addons/shaker/data/resources/`; they reference upstream demo assets. Runtime
classes and notices remain included. Preserve Phantom Camera's headless updater
guard and HTTP response validation when updating that addon.

## GitHub workflow

[The Windows workflow](../.github/workflows/package.yml) runs one packaging job:
restore LFS and licensed assets, set up official Godot 4.7.2 and export templates
with `chickensoft-games/setup-godot@v2`, then verify, export and inspect the game.
The action uses `use-dotnet: false`, `include-templates: true` and its download
cache. Windows steps select the installed console executable and capture version
output before checking its exit code. A cold run downloads the release archives
and imports game assets.

Configure bucket-scoped R2 credentials, endpoint/object variables and
`PRIVATE_GAME_ASSETS_SHA256` as described in [asset setup](ASSET_SETUP.md). The
workflow checks the private bundle checksum and restores only catalog-required
paths. Credentials and downloaded private archives are not uploaded. Rebuild a
replacement bundle with `tools/bundle_private_assets.py` and update its R2 object
and checksum when licensed content changes. `KYLR_PUBLIC_API_URL` configures the
Windows client's public API endpoint.

A pushed `v*` tag publishes the verified ZIP and checksum directly to GitHub
Releases; tags containing a hyphen are prereleases. Manual dispatch uploads the
ZIP and checksum as a one-day Actions artifact without publishing. Logs print
errors with context in workflow output. Only the packaging job has release write
permission. A completed hosted workflow is required to claim hosted CI validation.

## Multiplayer services

[Cloud hosting](CLOUD_HOSTING.md) owns Render, Atlas and Edgegap configuration.
The manual multiplayer workflow tests the API and builds the private server
image. Its download stage installs checksum-pinned official Godot for Linux,
then imports restored assets and checks the server script. BuildKit caches
binary-download and import layers. Optional publication pushes an immutable
source-commit image tag and registers the Edgegap app version. Hosting credentials
never ship to clients.

## Terrain authoring

Terrain3D is used only by the [planetary terrain pipeline](library/PLANETARY_TERRAIN.md).
Game and server packages consume static map meshes and PBR textures, with no
Terrain3D native runtime. Package checks verify manifest resources and Windows
packages include its MIT notice under `licenses/terrain3d/LICENSE.txt`.
