# KYLR

A Godot robot arena shooter with **Instant Action** and **Online Multiplayer**.
Both offer DM, TDM, CTF, five-life Elimination and Gun Game on Skyfall and Faceoff
using the Tensor character. Online play uses authenticated accounts, matchmaking,
and dedicated authoritative servers hosted through Render and Edgegap.
Instant Action offers map, bot difficulty, robot count, goal score and time-limit
controls for every match type. See the [match rules](../docs/RULES.md).

## Requirements

- Git and PowerShell 7 for the commands below.
- **Official Godot 4.7.2 stable**, resolved through `GODOT` or PATH.
- A GPU compatible with Forward+ for playing and screenshot capture. The Windows project uses Vulkan; automated checks can run headless.
- Matching **official export templates** for building an executable.

Authored models, GUT tests, the LimboAI GDExtension, Phantom Camera and ProtonScatter are included in this repository. Install the separately licensed animations and sound effects using [asset setup](../docs/ASSET_SETUP.md) before importing the game. Generating retargeted animations requires Blender; running with prepared assets does not. Phantom Camera is enabled in `project.godot` and drives the menu preview and match cameras. ProtonScatter's runtime modifier stack places dropped Energy Cores on map colliders; its optional editor plugin can be enabled after the initial asset import. API keys are used only by local asset setup tools and are not required by the running game. See [third-party notices](THIRD_PARTY.md) for dependency and asset licenses.

The project defaults to Safe rendering-thread mode in every quality preset.
Graphics settings offer an experimental separate rendering thread toggle; Apply saves it for the next launch.
For a diagnostic override, pass `--render-thread safe` or `--render-thread separate` to the engine command.
See [PLAYTESTING.md](../docs/PLAYTESTING.md) for the loading and benchmark checks.

## Clone and import

Install Git LFS before cloning. Binary assets and bundled native addons use LFS.

```powershell
git lfs install
git clone https://github.com/vaibhavpandeyvpz/kylr.git KYLR
Set-Location .\KYLR\game

$Godot = (Get-Command godot_console -ErrorAction Stop).Source
& $Godot --version
& ./tools/check_local_assets.ps1
& $Godot --headless --path . --editor --import --quit
```

The clone command uses GitHub HTTPS. Install official Godot and its export templates using the [root setup instructions](../README.md#build-and-run-on-windows) before importing a fresh clone. If you already have a checkout, open PowerShell in its `game` directory instead of cloning again. All subsequent commands assume the current directory contains `project.godot` and `$Godot` points to the official Godot console executable. Set that variable again in each new terminal session.

The initial import generates the ignored `.godot/` cache and registers script classes and native extensions. Repeat the import after pulling changes to assets or addons, before running tests directly. The full verification script also performs this step.

## Graphics and validation

Low, Medium and High are raster presets; Custom retains individual settings.
High enables fixture illumination, shadows, ambient occlusion, bloom and 4× MSAA.
See [rendering](../docs/RENDERING.md) for the current graphics contract and
[playtesting](../docs/PLAYTESTING.md) for validation and performance checks.

## Run and edit

Run the game:

```powershell
& $Godot --path .
```

Open the editor:

```powershell
& $Godot --path . --editor
```

Choose **Instant Action** to configure a match, or **Online Multiplayer** to sign in and request a dedicated server. Use **F6** in the editor to run the current scene or **F5** to run the project. The main scene is `main.tscn`.

Default movement controls:

| Input | Movement |
| --- | --- |
| Hold WASD | Run at 6 m/s. |
| Hold Ctrl + movement | Sprint at 12 m/s while above 50 EP. |
| Hold Shift + movement | Walk at 3 m/s; overrides sprint. |
| Hold C + movement | Crouch and move at 2.5 m/s. |
| Press Space | Normal jump immediately. |
| Hold Q for two seconds, then release | Charged jump while above 50 EP. |

Spawn protection restricts movement to walking. At 50 EP or below, sprint requests fall back to running. A full 100 EP lasts 100 seconds of active play without a refill. Movement and action keys can be rebound in Settings. See [character animation coverage](../docs/ANIMATION_COVERAGE.md) for the current clip audit.

## Test

For an interactive weapon-effects sandbox, run:

```powershell
pwsh -File .\tools\run_weapon_effects_harness.ps1 -Godot $Godot
```

Or open `tools/weapon_effects_harness.tscn` and press **F6**. This standalone
scene has a 50 × 50 m ground, a stationary idle Tensor at the center and a
controlled Tensor starting 10 m away. The TPV Phantom Camera tracks both
from the side and expands its framing with their separation and jump height.
Weapons aim at the target automatically, independently of the side camera.
All travelling projectiles (rockets, EMP charges, lightning orbs and fireballs)
move at **1 m/s** in this harness. Change **Projectile Speed Mps** on the scene
root in the Inspector to adjust that speed. Effects, animations, audio and
player movement keep their normal timing; regular matches use normal speeds.

Use **WASD** to move relative to the target, **Ctrl** to sprint, **Shift** to
walk and **Space** to jump. **Mouse wheel** cycles all ten weapons; **1–7**
select them directly. **LMB** fires primary; **RMB** uses secondary (hold
**LMB + RMB** for scoped rifle fire). **H** switches body/head aim, **T**
toggles the target shield and **R** resets the two positions. **Esc** releases
the mouse; click to resume. **F10** exits. The target stays stationary, health
and ammo refill continuously, and the overlay reports range and accepted hits.
These sandbox conveniences do not alter normal match rules.

Hold **middle mouse** and drag to orbit the two robots. **Ctrl + wheel** zooms;
the unmodified wheel still cycles weapons. **V** cycles scene, weapon and impact
focus. **C** restores the side camera.
Use `-- --harness-flame-preview` to verify orbit/zoom and save side, oblique, raised and
impact close-up flame views under `reports/flame3d/`.

Append `-- --harness-weapon=flamethrower` when launching the scene directly
to start with that weapon selected; other weapon IDs work as well.

To verify all primary/secondary shots, movement, wheel cycling and camera
framing automatically:

```powershell
& $Godot --headless --fixed-fps 60 --path . tools/weapon_effects_harness.tscn -- --harness-smoke
```

Run that command without `--headless` to render the same probe and save
`reports/weapon-effects-harness.png`.

For the ground-mounted pulse gun, run:

```powershell
pwsh -File .\tools\run_pulse_gun_bench.ps1 -Godot $Godot
```

The fixture aims at a random Tensor's torso center, exactly 10 m from its
muzzle. **LMB** fires one pulse per press with the normal one-second cooldown;
holding never auto-fires. **R** replaces the target with random head, upper body
and paint. **RMB drag** orbits, the **wheel** zooms, and **1/2/3** frame the whole
bench, gun or target. **Esc/F10** exits. It uses the real 15 m/s projectile,
collision, sound and impact effects, with refilling target health.

```powershell
& $Godot --headless --fixed-fps 60 --path . tools/pulse_gun_bench.tscn -- --pulse-bench-smoke
```

Omit `--headless` for rendered captures in `reports/pulse-bench/`.

Run the complete automated verification:

```powershell
pwsh -File .\tools\verify.ps1 -Godot $Godot
```

This imports the project, runs GUT, exercises DM/TDM/CTF/Elimination/Gun Game with bots, and checks the transition to match results. It fails on engine/script errors, test failures, detected instance leaks, or missing expected match phases. Logs are written to `reports/verification/`, with a separate log per check.

Run only GUT after importing:

```powershell
& $Godot --headless --path . -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit
```

Run an individual headless match smoke test:

```powershell
& $Godot --headless --path . --fixed-fps 60 -- --smoke --type=CTF --robots=9 --duration=120
```

Exercise a short match through its results screen:

```powershell
& $Godot --headless --path . --fixed-fps 60 -- --smoke --limit-seconds=5 --duration=30
```

Game arguments belong **after** the standalone `--` separator:

| Argument | Meaning |
| --- | --- |
| `--smoke` | Automatically start a local match, print diagnostics, then quit. |
| `--type=DM` | Match type: `DM`, `TDM`, `CTF`, `ELIMINATION`, or `GUNGAME` (case-sensitive; default `DM`). |
| `--robots=10` | Total robots including the human-controlled slot; use 2–10. Default 10. |
| `--duration=40` | Simulation seconds before diagnostics and exit; default 32. Includes the opening sequence. |
| `--limit-seconds=5` | Override the active match time limit during a smoke run. |
| `--view=fpv` | Override the smoke run's camera preference with `fpv` or `tpv`, without saving it. |

Allow for resource preparation and the five-second deployment countdown when choosing a duration. `--fixed-fps 60` fixes the simulation timestep and disables real-time synchronization, so headless runs can finish faster than wall-clock time. Individual smoke commands print `SMOKE`, bot, and audio diagnostics; use `verify.ps1` for automated pass/fail checks. Headless checks do not validate rendered visuals or audible output.

For bot, traversal, or objective changes, run the full DM/TDM/CTF roster matrix and review its route and performance reports:

```powershell
pwsh -File .\tools\run_bot_matrix.ps1
```

The matrix uses at least 120 simulated seconds for every CTF roster; shorter CTF samples are insufficient to judge captures. The required scenarios, acceptance checks, and rendered profiling procedure are in the [playtesting guide](../docs/PLAYTESTING.md).

To watch a smoke match, omit `--headless` and `--fixed-fps 60`:

```powershell
& $Godot --path . -- --smoke --type=TDM --robots=10 --duration=40
```

## Performance checks

Use the rotating ten-weapon combat deck for short serial comparisons on both
maps. See [PLAYTESTING.md](../docs/PLAYTESTING.md#rendered-performance) for commands,
hardware selection, package build identity and frame-time interpretation. Profiling
and fixed-rate captures are development tools; measure exported release rendering
separately.

## Capture screenshots

These commands need a graphics device and automatically quit after capture. Each run overwrites `reports/preview.png`.

```powershell
New-Item -ItemType Directory -Force .\reports | Out-Null

# Main menu
& $Godot --path . -- --capture

# In-match view after the opening sequence
& $Godot --path . -- --smoke --capture

# Arena overview with HUD hidden
& $Godot --path . -- --smoke --capture --overview
```

## Build a Windows executable

Install matching official Godot 4.7.2 export templates with the root
`tools/prepare_godot.py --platform windows --templates` installer.

From the project directory, import and verify first, then export:

```powershell
pwsh -File .\tools\verify.ps1 -Godot $Godot
if ($LASTEXITCODE -ne 0) { throw 'Verification failed; export stopped.' }

New-Item -ItemType Directory -Force .\build\windows | Out-Null
& $Godot --headless --path . --export-release 'Windows Desktop' 'build/windows/KYLR.exe'
if ($LASTEXITCODE -ne 0) { throw 'Windows export failed.' }

& .\build\windows\KYLR.exe
```

For a debug export, replace `--export-release` with `--export-debug`. Distribute the **entire `build/windows/` directory**, including the `.pck` and native extension libraries, preserving their relative paths. The executable alone is insufficient. Builds are currently unsigned.

Run the exported game and manually check menu navigation, match start, controls, audio, results, and returning to the menu before distributing it. Passing headless verification does not certify the exported package.

## Tagged packages and GitHub Releases

Prepare a native Windows, macOS or Linux package with PowerShell 7:

```powershell
pwsh -File ./tools/package.ps1 -Godot $Godot -Version dev-local
```

Each invocation uses fresh staging under `build/package-*/<OS>/`, inspects
native binary dependencies, includes license notices, verifies the PCK and runs
an exported startup check. It writes
`build/KYLR-<OS>-<version>.zip` (Windows/macOS) or `.tar.gz` (Linux), plus a SHA-256 checksum, with logs under
`reports/packaging/`. Packages remain unsigned. These checks do not replace
rendered gameplay/audio, quality or performance qualification.

The root [release workflow](../.github/workflows/package.yml) downloads official
Godot on Windows, macOS and Linux. All three native builds must pass before a
`v*` release publishes their packages together. Manual dispatch on `main` uploads
artifacts; dispatch on a `v*` tag publishes a release. macOS uses a universal app
with ad-hoc signing and no notarization. See [build and release](../docs/BUILD_AND_RELEASE.md)
for the hosted workflow and rendered validation procedures.

## Troubleshooting and project layout

- **Unknown LimboAI classes or missing resources:** keep bundled assets/addons
  together and repeat the official Godot import command.
- **Export template errors:** install matching official Godot 4.7.2 export templates.
- **Verification failure:** inspect the named log in `reports/verification/`.

| Directory | Contents |
| --- | --- |
| `scripts/` | Gameplay, AI, UI and presentation. |
| `data/`, `assets/`, `shaders/` | Runtime definitions, exported assets and shaders. |
| `addons/`, `tests/`, `tools/` | Dependencies, automated tests and authoring/verification tools. |
| `docs/` | Gameplay, design and production contracts. |
| `reports/`, `build/`, `.godot/` | Generated output, ignored by Git. |

Runtime models retain authored material slots. Architecture and weapons use
authored flat PBR finishes; deliberate image finishes include regolith and
screens. Edit generators in the sibling library and follow its modelling guide
for regeneration and handoff. Start implementation work with
[AGENTS.md](AGENTS.md), [GAMEPLAY.md](../docs/GAMEPLAY.md) and [RULES.md](../docs/RULES.md).

Inspect inventory and first-person presentation at landscape and portrait sizes
with `& $Godot --path . --fixed-fps 60 -s res://tools/preview_inventory.gd`.
Captures go to `reports/inventory/` with isolated preference saves. This checks
presentation, not real-time FPS.
