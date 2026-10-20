# KYLR

![Five Tensor variants with authored weapons and combat effects in a lunar outpost](docs/media/hero-showcase.png)

*Authored game assets posed and rendered in Blender.*

A robot arena shooter with fast movement, ten weapons and lunar battlegrounds.
Gameplay is heavily inspired by the **Unreal Tournament** games and their
**Secret Level** episode. Instant Action supports Deathmatch, Team Deathmatch,
Capture the Flag, five-life Elimination, and Gun Game on Skyfall and Faceoff.
Online Multiplayer uses authenticated accounts and authoritative dedicated
servers for the same match types.

**100% prompt / vibe coded.** Development started with **Claude**, then moved to
**ChatGPT / Codex** to bring image generation into the asset creation workflow.
Game code, scripted Blender models, effects and tools are developed through that
prompt-driven process.[^ai-tools]

- **Custom engine:** built on **Godot 4.7.2 stable**, with hardware ray-traced
  lighting, shadows and reflections, **NVIDIA DLSS Ray Reconstruction** and
  optional DLSS upscaling on supported hardware. Raster presets remain available.
- **Spatial audio:** [Spatio](docs/SPATIO.md) combines positional sound,
  material-aware obstruction, filtered transmission, sound travel delay and
  map-zone reverb.
- **Full multiplayer matchmaking and authoritative servers:** authenticated
  accounts, automatic match allocation and dedicated servers for DM, TDM, CTF,
  Elimination and Gun Game,
  powered by [Render](https://render.com/) and [Edgegap](https://edgegap.com/).
- **Combat feedback:** local kill confirmations, rapid-kill accolades and voiced
  match announcements, plus spatial kill quips in ten robot voices with matching
  killfeed dialogue. Grenade, rocket and EMP hits can earn credit for a later
  fall when they are the victim's last accepted hit that life.
- **Player customisation:** five head variants, 12 primary and 12 secondary armor
  colors, and victory emotes. Preview your robot in 3D and save your online
  loadout to your account.
- **Maps designed in Figma:** explore the
  [KYLR map designs](https://www.figma.com/community/file/1693957204725961135/kylr-maps?fuid=962370705244141890).
- **Open source:** KYLR's original game and library work is **Apache 2.0 licensed**.
  The engine, bundled dependencies and separately licensed assets retain their
  applicable licenses.

See the [in-game cinematic gallery](docs/CINEMATICS.md) for five scenes on each map.

This is a single repository on `main`:

| Folder | Contents |
| --- | --- |
| [game/](game/README.md) | Godot project, runtime assets, scripts, services and tests |
| [engine/](engine/README.md) | Custom Godot source, including the NVIDIA RTX integration |
| [library/](library/AGENTS.md) | Scripted Blender asset generators, animation sources and audio |
| [docs/](docs/README.md) | Shared rules, design contracts, development and release guidance |
| [tools/](tools/README.md) | Dependency preparation and Windows build orchestration |

## Build and run on Windows

Install Git with Git LFS, PowerShell 7, Python 3.12 and Visual Studio 2026 C++ build tools
with a Windows SDK. Clone this repository normally; no submodule initialization
or other source checkout is needed.
Install the [separately licensed assets](docs/ASSET_SETUP.md) before the first
game import. Engine compilation can run before asset installation.

```powershell
git lfs install
git clone https://github.com/vaibhavpandeyvpz/kylr.git KYLR
Set-Location KYLR
python -m venv engine/.local/build-venv
& ./engine/.local/build-venv/Scripts/python.exe -m pip install -r tools/requirements-build.txt
./tools/prepare_windows_dependencies.ps1
./engine/misc/scripts/build_windows.ps1 -Target editor
./engine/misc/scripts/build_windows.ps1 -Target template_release
$Godot = (Resolve-Path engine/bin/godot.windows.editor.x86_64.console.exe).Path
& ./game/tools/check_local_assets.ps1
& $Godot --headless --path game --editor --import --quit
& $Godot --path game
```

Use the custom engine for every import, test and export. Raster rendering is
available without RT support; the game disables unsupported RT controls.
Blender is needed for asset authoring, not for running with prepared game assets.
Before the first game import, follow [licensed asset setup](docs/ASSET_SETUP.md)
to install locally retargeted Mixamo animations and Epidemic
Sound effects. These files are excluded from the public source checkout.
See [game setup and controls](game/README.md) and
[asset modelling](docs/library/MODELLING.md).

## Verify and release

```powershell
pwsh -File game/tools/verify.ps1 -Godot $Godot
pwsh -File game/tools/package_windows.ps1 -Godot $Godot -Version dev-local
```

The [release workflow](.github/workflows/package.yml) builds the custom engine
first, then verifies and exports the game. A pushed `v*` tag publishes the
verified Windows package and checksums as a GitHub release. Manual runs build
artifacts without publishing. See [build and release](docs/BUILD_AND_RELEASE.md).

## Host multiplayer

Run the account API on Render, store accounts in MongoDB Atlas and host private
dedicated-server images on Edgegap. The [multiplayer workflow](.github/workflows/multiplayer.yml)
verifies the backend and builds the custom Linux engine/server image; optional
publication registers an immutable Edgegap app version. Configure the public
API origin in client builds. See [hosting setup](docs/CLOUD_HOSTING.md) for secrets,
network access, free-tier capacity limits and live connectivity checks.

## Contributing

**Pull requests are welcome!** Help make KYLR the best open-source Godot FPS game
ever. Contributions to gameplay, maps, weapons, visuals, audio, accessibility,
multiplayer, performance, tests and documentation are all welcome.

Start with [the contributor guide](AGENTS.md) and
[development guidance](docs/DEVELOPMENT.md). Keep PRs focused, explain the player
experience or problem they improve, and include relevant test results and
screenshots or clips for visual changes. Use the custom engine for validation
and keep separately licensed assets and local credentials out of your PR.

## Godot addon credits

| Addon | Role |
| --- | --- |
| [LimboAI](https://github.com/limbonaut/limboai) | Drives bot behavior trees. |
| [Phantom Camera](https://github.com/ramokz/phantom-camera) | Controls menu and gameplay cameras. |
| [ProtonScatter](https://github.com/HungryProton/scatter) | Generates and projects dropped Energy Core positions. |
| [GUT](https://github.com/bitwes/Gut) | Runs automated gameplay and integration tests. |

Licenses and dependency details are in [third-party notices](game/THIRD_PARTY.md).

## License

KYLR's original game and library code, tools, documentation and original assets
are distributed under the [Apache License 2.0](LICENSE), except where a file or
asset carries separate terms. See [NOTICE](NOTICE) for the project notice.
Godot and bundled dependencies retain their own licenses; see
[engine licensing](engine/LICENSE.txt) and [game notices](game/THIRD_PARTY.md).
Mixamo animations and Epidemic Sound recordings are separately licensed local
assets, as described in [asset setup](docs/ASSET_SETUP.md).

[^ai-tools]: KYLR can be considered a perfect example of what frontier AI models,
    Godot and Blender can achieve when combined together.
