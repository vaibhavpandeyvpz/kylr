# Build and release

This is one repository. Work from its root unless a command explicitly changes
directory. `engine/` contains the custom Godot 4.7.2 source; `game/` contains
the project and uses its matching editor and export template. Library authoring
does not run during packaging. Authored model exports are tracked; separately
licensed retargeted animations and sound effects must be installed
locally before import using [asset setup](ASSET_SETUP.md).

## Git LFS

Binary assets, fonts and bundled native addons use Git LFS. Install Git LFS and
run `git lfs install` before cloning. After a clone made without LFS, run
`git lfs pull` from the repository root before importing or building.
The workflow checks out LFS content in engine and game jobs. Licensed downloads,
SDKs, credentials and build products remain ignored rather than stored in LFS.

## Windows prerequisites and dependencies

Install PowerShell 7, Python 3.12 and stable Visual Studio 2026 C++ tools with
the Windows SDK. The engine build helper discovers the installation with
`vswhere` and loads its x64 developer environment. It accepts
`-VisualStudioPath`, `-Python` and `-Jobs` overrides and also works from an
independent engine source checkout.

```powershell
python -m venv engine/.local/build-venv
& ./engine/.local/build-venv/Scripts/python.exe -m pip install -r tools/requirements-build.txt
./tools/prepare_windows_dependencies.ps1
./engine/misc/scripts/build_windows.ps1 -Target editor
./engine/misc/scripts/build_windows.ps1 -Target template_release
```

Dependency preparation downloads Streamline 2.10.0 from the URL in
`engine/drivers/streamline/runtime_manifest.json` if it is not already staged.
It verifies the archive SHA-256, production DLL hashes/NVIDIA signatures and
notice hashes, then copies runtimes beside the engine binaries. It does not use
development/watermarked binaries. `-SDKArchive` accepts an already downloaded
archive. SDK files remain ignored under `engine/.local/`.

Microsoft CRT 14.51.36247 files must match the existing deployment pins and
Microsoft signatures. The preparation script finds them under the stable VS
redist directory, or accepts `-VCRuntimeSource`. It fails clearly if the exact
pin is unavailable; updating runner images must never silently change shipped
native dependencies. Refresh the pin and repeat package validation deliberately.

## Game verification and packaging

```powershell
$Godot = (Resolve-Path engine/bin/godot.windows.editor.x86_64.console.exe).Path
pwsh -File game/tools/verify.ps1 -Godot $Godot
pwsh -File game/tools/package_windows.ps1 -Godot $Godot -Version dev-local
```

The verifier imports, runs GUT, exercises DM/TDM/CTF and checks the results
flow. Packaging uses the custom release template, verifies native dependencies,
copies licenses, inspects PCK contents, smoke-tests the exported executable and
writes a manifest and SHA-256 checksum. Artifacts are in `game/build/`; logs
remain under `game/reports/`. Ship the complete ZIP, not only its executable.
Windows builds are unsigned. Headless checks do not qualify rendered appearance,
audio, hardware compatibility or frame rates; [rendering contract](RENDERING.md)
and [playtesting](PLAYTESTING.md) remain separate requirements.

## GitHub workflow

Configure bucket-scoped R2 credentials, the endpoint/object repository variables
and `PRIVATE_GAME_ASSETS_SHA256` for the private prepared-asset bundle described in
[asset setup](ASSET_SETUP.md). The workflow verifies the bundle's checksum and
restores only the paths required by this checkout's catalogs before game import.
Downloaded asset archives and API credentials are not uploaded as CI artifacts.

[The active root workflow](../.github/workflows/package.yml) has three dependent
stages: **engine → game → release**. The engine stage runs editor and release
template builds on separate `windows-2025-vs2026` runners; the game stage waits
for both and merges their artifacts. Each compiler uses the available runner CPUs.
Target-specific SCons object caches are restored across runs, keyed by engine
source and build-tool inputs with a compatible-target fallback. The cache is
bounded to 3 GiB per target and excludes local SDKs, secrets and game assets.
Release optimization and runtime checks remain enabled. Game-only edits reuse
compiled engine objects; engine edits rebuild affected dependencies.

The first build on an empty cache still compiles the complete engine. Free runner
CPU allocation, cache eviction and linking prevent a fixed one-hour guarantee;
check cold and warm hosted timings separately. For local cache reuse, the Windows
build helper accepts `-CachePath` and `-CacheLimitGiB`. The engine artifact carries the editor, matching release
template, verified runtimes and SDK notices to the game job. No stock Godot
installer or component repository checkout is used. Only the release job gets
`contents: write`; it downloads the verified package, rechecks its checksum and
publishes an existing `v*` tag. Tags containing a hyphen become prereleases.
Manual dispatch builds downloadable artifacts without publishing a release.

The workflow must complete on GitHub before its hosted execution is considered
verified. Local script checks and package tests are not a hosted CI run.

## Multiplayer services

[Cloud hosting](CLOUD_HOSTING.md) defines Render/Atlas configuration and the
manual multiplayer workflow, which builds a custom Linux engine and private
Edgegap server image. BuildKit persists intermediate engine layers in the GitHub
Actions cache and uses four compiler jobs on the Linux runner. Game-only changes
reuse the engine layer; engine source changes require recompilation. The image
is loaded locally for validation before optional publication. Set `KYLR_PUBLIC_API_URL` as a repository variable to
configure the Windows client endpoint during packaging. The backend and game
server never share their hosting credentials with clients.
