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

The verifier imports, runs GUT, exercises all five match types and checks the results
flow. Packaging uses the custom release template, verifies native dependencies,
copies licenses, inspects PCK contents, smoke-tests the exported executable and
writes a manifest and SHA-256 checksum. Artifacts are in `game/build/`; logs
remain under `game/reports/`. Ship the complete ZIP, not only its executable.
Windows builds are unsigned. Headless checks do not qualify rendered appearance,
audio, hardware compatibility or frame rates; [rendering contract](RENDERING.md)
and [playtesting](PLAYTESTING.md) remain separate requirements.

Exclude ProtonScatter's editor-only `presets/` scenes from exported packages.
They reference upstream demo assets that are not vendored. Runtime scatter
scripts, modifiers and their licenses remain included.

Phantom Camera's vendored editor updater skips network checks with the headless
display driver. Its response handler accepts only successful HTTP 200 array
responses and validates release tags before reading them. Preserve these local
guards when updating the addon so API error responses cannot break imports.

## GitHub workflow

Configure bucket-scoped R2 credentials, the endpoint/object repository variables
and `PRIVATE_GAME_ASSETS_SHA256` for the private prepared-asset bundle described in
[asset setup](ASSET_SETUP.md). The workflow verifies the bundle's checksum and
restores only the paths required by this checkout's catalogs before game import.
Downloaded asset archives and API credentials are not uploaded as CI artifacts.
The editor job restores and validates private assets before compilation. The
private installer requires every runtime weapon animation family and sound cue;
package inspection checks that all catalog resources survived export. Build a
replacement private ZIP with `tools/bundle_private_assets.py` and update both
the R2 object variable and checksum secret when its contents change.

[The active root workflow](../.github/workflows/package.yml) builds the release
export template and editor on separate `windows-2025-vs2026` runners in parallel.
The template job uploads only `godot.windows.template_release.x86_64.exe`, compressed
and retained for one day. The editor stays on its runner for game import,
verification, packaging and publication. That runner prepares its own verified
native runtimes and notices; these do not need transfer artifacts.

The packaging job waits for the template from the same workflow run, fails if its
build fails, then downloads it into `engine/bin`. A retry can reuse that run's
existing template artifact; if it has expired, rerun all jobs. Each compiler uses
available runner CPUs. Separate SCons object caches, bounded to 3 GiB per target,
are keyed by engine/build-tool inputs with a compatible-target fallback. Game-only
changes reuse compiled engine objects; engine changes rebuild affected dependencies.
Local SDKs, secrets and game assets are excluded from these compiler caches.

The first build on an empty cache still compiles the complete engine. Free runner
CPU allocation, cache eviction and linking prevent a fixed one-hour guarantee;
check cold and warm hosted timings separately. For local cache reuse, the Windows
build helper accepts `-CachePath` and `-CacheLimitGiB`. Release optimization and
package validation remain enabled; no stock engine is substituted.

The packaging job checks the package checksum and publishes an existing `v*` tag
directly to GitHub Releases. Tags containing a hyphen become prereleases. Tagged
packages are not also uploaded as Actions artifacts. Manual dispatch provides the
complete playable ZIP and checksum as a one-day downloadable artifact without
publishing a release. Logs are printed in the workflow output instead of being
stored as separate artifacts. Verification failures print the engine exit code
and every error match with surrounding lines from the complete log before its
tail, so early import errors remain visible after long asset-import progress.
Only the packaging job has `contents: write`;
Actions read permission permits the same-run template lookup and download.

If artifact upload reports a storage quota error, compilation may already have
succeeded. Remove unneeded artifacts from completed runs across the owning account
or review the account's Actions storage budget. Shorter retention applies to new
uploads and does not remove existing artifacts. GitHub's storage accounting can
take 6–12 hours to update. Keep compiler caches when clearing artifacts so the
next build can reuse compiled objects.

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
