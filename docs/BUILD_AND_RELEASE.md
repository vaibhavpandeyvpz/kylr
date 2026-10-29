# Build and release

The game uses official Godot 4.7.2 stable and matching official export templates.
Windows, macOS, Linux and Android packages use prebuilt binaries. Blender authoring does
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

[The packaging workflow](../.github/workflows/package.yml) uses one desktop matrix with
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

A pushed `v*` tag starts the matrix.
Tagged builds stamp the checkout's project version from the tag without `v`.
Windows file/product versions use `MAJOR.MINOR.PATCH.0`; macOS short/build versions
use `MAJOR.MINOR.PATCH`. Prerelease/build suffixes remain in the project version,
archive name and manifest. These generated settings are not committed back.
The Android job uses `android-actions/setup-android@v4`, Temurin JDK 25 through
`actions/setup-java@v6`, Android platform 36 and build-tools 36.0.0. It builds
an ARM64 release APK from the official template, signs it and verifies its
certificate, v2/v3 signatures, 16 KB library alignment, release manifest and
payload. Android does not require Gradle or the NDK for this prebuilt export.

One release job waits for the three desktop builds and the Android build,
downloads their artifacts, verifies SHA-256 checksums and publishes all packages
together to GitHub Releases, including the signed APK, Android manifest and
checksums alongside the desktop archives. Only that job has release write permission. Tags
containing a hyphen are prereleases. Manual dispatch on `main` builds downloadable
artifacts; dispatch on a `v*` tag also publishes a release. Rerunning an old run
uses its original workflow revision; start a new run after workflow changes.
A completed hosted matrix is required to claim validation on all three OSes.

## Multiplayer services

[Cloud hosting](CLOUD_HOSTING.md) owns Render, Atlas and Edgegap configuration.
The manual multiplayer workflow runs one API/publication test suite against
MongoDB on Ubuntu 22.04, then builds the private server image once. The API runner
uses that image's 6.8 kernel because MongoDB 8.0 rejects the newer Ubuntu kernels
on the 24.04 runners; see [the runner compatibility issue](https://github.com/actions/runner-images/issues/15005).
The download stage installs
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

## Android APKs and signing

The Android preset targets ARM64 and includes the LimboAI Android library. It
is a device-validation target included in the platform release workflow.
Install the matching official Godot 4.7.2 Android export
templates and configure the Android SDK and Java SDK in Godot Editor Settings.
From `game/`, create `build/android/` and run:

```powershell
& $env:GODOT --headless --path . --export-debug Android build/android/KYLR.apk
```

Install the debug APK on a phone with Android platform tools. Validate menus,
multitouch, both game modes, audio, rendering, performance and device safe areas
on actual hardware before treating Android as a supported release. A signed
APK is suitable for sideloading; these checks do not qualify phone performance
or configure Google Play distribution.

Set `JAVA_HOME` to JDK 25 and `ANDROID_HOME` to the Android SDK directory. From
`game/`, generate a release key once:

```powershell
./tools/create_android_signing_key.ps1
```

The default destination is the ignored workspace `.local/android-signing/`
directory. It contains `kylr-release.p12`, `keystore-password.txt`,
`keystore.base64.txt`, a public `certificate.pem`, and `GITHUB-SETUP.txt`.
The key is RSA-3072 with a 10,000-day validity and the alias `kylr-release`.
The generator protects the directory, uses a cryptographically random password
and refuses to replace existing material. Back up the key and password securely;
reuse this certificate for app updates. Base64 is another copy of the private
keystore, not encryption. Keep all signing material out of Git and artifacts.

In GitHub repository **Settings → Secrets and variables → Actions → Secrets**,
add these repository secrets by copying the complete file contents:

| Secret | Local file under `.local/android-signing/` |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | `keystore.base64.txt` |
| `ANDROID_KEYSTORE_PASSWORD` | `keystore-password.txt` |

The workflow defaults to alias `kylr-release`. If using a different key alias,
set the public Actions repository variable `ANDROID_KEY_ALIAS`. Existing R2
asset secrets and endpoint variables remain required. CI decodes the keystore
only into the runner's temporary directory, passes passwords through environment
variables and removes the temporary keystore even when a build fails. Missing
signing secrets fail the Android job and prevent a partial release.

To build a signed phone APK locally from `game/`:

```powershell
$signing = Resolve-Path ../.local/android-signing
$env:ANDROID_KEYSTORE_PATH = Join-Path $signing kylr-release.p12
$env:ANDROID_KEYSTORE_PASSWORD = [IO.File]::ReadAllText((Join-Path $signing keystore-password.txt))
try {
    ./tools/package_android.ps1 -Version dev-device -VersionCode 1
} finally {
    Remove-Item Env:ANDROID_KEYSTORE_PASSWORD
}
```

Output is `game/build/KYLR-Android-arm64-<version>.apk` with a public manifest
and `.apk.sha256` checksums. The `Android Release` preset exports unsigned;
the packaging script aligns, signs and verifies it, then restores the original
export preset bytes. No signing credentials are saved in Godot's presets.
Tag builds use the tag version without `v` as Android's version name and the
workflow run number as its positive, increasing version code. Choose a higher
`-VersionCode` for local updates over an already-installed build. A debug-signed
installation with the same package name must be uninstalled before installing
the release-signed APK; subsequent releases reuse the release key.

The `Android Emulator` preset exports x86-64 for native execution on x86-64
Android virtual devices; it uses the same official Android template archive.
Export it to `build/android/KYLR-x86_64.apk`. Run emulator profiles in landscape
with host GPU rendering enabled. Emulator measurements describe the host and
virtual device rather than physical phone performance.

`tools/profile_android.ps1 -Matrix -Name android-matrix -Rebuild` generates the
current map catalog × Low/Medium/High × 2/4/6/8/10-robot matrix. It defaults to
15 seconds of warmup and 60 seconds of wall-clock sampling per case. Run with
the visible landscape emulator already booted. The Android Profile Release
preset uses the release engine and LimboAI library; the debug preset provides
file handoff between runs. Diagnostic release signing uses the local Godot
debug keystore and never configures store signing.

Reports under `game/reports/performance/` retain configuration, APK hashes,
device identity, frame percentiles, one-second-window minimum FPS, physics
update rate, render resolution and CPU counters. Matrix acceptance runs disable
stage and GPU timestamp instrumentation. Use a separate Config JSON with
`"costs":true` for CPU-stage/GPU diagnostics; timer-heavy instrumentation can
distort emulator timings. Instrumented and rendering-disabled isolation cases
are diagnostics and cannot pass the rendered FPS gate. Short
samples are screening runs, not sustained performance qualification. Build,
installation, script errors and incomplete matrices invalidate the run.
