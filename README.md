# KYLR

**Jump the gap. Steal the flag. Keep moving.**

[![Download](https://img.shields.io/github/v/release/vaibhavpandeyvpz/kylr?label=Download)](https://github.com/vaibhavpandeyvpz/kylr/releases/latest)
[![Desktop builds](https://github.com/vaibhavpandeyvpz/kylr/actions/workflows/package.yml/badge.svg)](https://github.com/vaibhavpandeyvpz/kylr/actions/workflows/package.yml)
[![Multiplayer](https://github.com/vaibhavpandeyvpz/kylr/actions/workflows/multiplayer.yml/badge.svg)](https://github.com/vaibhavpandeyvpz/kylr/actions/workflows/multiplayer.yml)
[![Godot 4.7.2](https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

KYLR is an open-source robot arena shooter with fast movement, ten weapons and
three very different worlds to fight in. Play against bots, compete online,
or open the project and make it your own.

**[Download & Play](https://github.com/vaibhavpandeyvpz/kylr/releases/latest)** ·
[Explore the arenas](docs/CINEMATICS.md) ·
[Build your own](#make-it-yours) ·
[Contribute](#join-in)

![Ten robot configurations and all ten weapons across Ramparts, Skyfall and Faceoff](docs/media/hero-showcase.webp)

## Three worlds. Different ways to win.

| Arena | Setting | The fight |
| --- | --- | --- |
| **Ramparts** | Martian lake valley | Cross the lake on thruster-powered platforms, time the rotating junction, and push onto rocky island strongholds. |
| **Skyfall** | Lunar crater | Fight across stacked floating decks, bridges and portals. Use the launch routes; the lunar ground below is lethal. |
| **Faceoff** | Volcanic world | Breach outpost buildings and cross burnt terrain broken by flowing lava pits. A charged jump can open a route around an opponent. |

[See the cinematic gallery](docs/CINEMATICS.md) for encounters from every map.
The arenas' layouts are also available in [Figma](https://www.figma.com/community/file/1693957204725961135/kylr-maps?fuid=962370705244141890).

## Pick a fight

- **Five match types:** Deathmatch, Team Deathmatch, Capture the Flag,
  five-life Elimination and Gun Game.
- **Movement with options:** sprint, use normal or charged jumps, ride moving
  platforms, take a jump pad or speed ramp, and cut through portals.
- **Ten weapons:** pistol, rifle, minigun, flak cannon, grenade launcher,
  rocket launcher, bio rifle, lightning gun, flamethrower and EMP gun.
- **Your robot, your look:** five heads, six upper-body assemblies, separate
  primary and secondary armor colors, and victory emotes.
- **Combat you can read and hear:** weapon impacts, armor feedback, kill
  confirmations, voiced callouts and spatial sound that responds to distance,
  walls and the arena around you.

**Instant Action** lets you choose the map, bot difficulty, robot count, score
limit and time limit. **Online Multiplayer** supports authenticated accounts,
matchmaking and authoritative dedicated servers.

## Download and play

1. Open the **[latest release](https://github.com/vaibhavpandeyvpz/kylr/releases/latest)**.
2. Download the package for **Windows, Linux or macOS**, then extract the complete archive.
3. Launch KYLR and choose **Instant Action** for a match with bots or **Online Multiplayer**.

Release packages include the prepared game assets. You do not need Godot or
Blender to play. [Controls and setup](game/README.md) cover the details.

## Make it yours

Change a weapon's behavior. Build another arena. Create a robot assembly.
KYLR keeps the Godot game, scripted Blender library and asset handoff tools in
one repository, so you can follow a feature from its source model to the game.

| Start here | What you can change |
| --- | --- |
| [Weapon data](game/data/weapons/catalog.json) | Weapon profiles, ammunition and firing behavior. |
| [Map sources](library/models/maps) | Layouts, terrain, native fixtures and platform motion. |
| [Tensor robot](library/models/characters/tensor) | Character geometry, materials and interchangeable assemblies. |
| [Bot data](game/data/ai) | Difficulty, tactics and behavior trees. |
| [Game scripts](game/scripts) | Movement, combat, presentation, UI and networking. |
| [Gameplay contracts](docs/GAMEPLAY.md) | The rules connecting all of those pieces. |

Use **official Godot 4.7.2** for the game and matching export templates for
builds. **Blender 5.2** is needed only when regenerating model or animation assets.
Git LFS is required for the repository's binary assets.

The public checkout includes KYLR's original models, textures, tools and code.
Mixamo animation binaries and Epidemic Sound recordings are **separately licensed**
and must be installed locally before importing the source project. Follow
[asset setup](docs/ASSET_SETUP.md); downloading a release is the quickest way to play.

<details>
<summary><strong>Windows source quick start</strong></summary>

Install Git LFS, PowerShell 7 and Python 3.12, then clone:

```powershell
git lfs install
git clone https://github.com/vaibhavpandeyvpz/kylr.git KYLR
Set-Location KYLR
```

Restore the [separately licensed assets](docs/ASSET_SETUP.md), then prepare Godot
and open the game:

```powershell
python tools/prepare_godot.py --platform windows --templates
$env:GODOT = (Resolve-Path .local/godot/godot_console.exe).Path
& ./game/tools/check_local_assets.ps1
& $env:GODOT --headless --path game --editor --import --quit
& $env:GODOT --path game
```

See [game setup](game/README.md) and [build instructions](docs/BUILD_AND_RELEASE.md)
for other platforms and existing Godot installations.

</details>

### Build and test

From the repository root with Godot configured:

```powershell
pwsh -File game/tools/verify.ps1 -Godot $env:GODOT
pwsh -File game/tools/package.ps1 -Godot $env:GODOT -Version dev-local
```

The desktop workflow builds Windows x64, Linux x64 and universal macOS packages.
[Build and release](docs/BUILD_AND_RELEASE.md) explains validation, export
requirements and publishing.

### Run your own multiplayer services

KYLR's backend combines an account API, MongoDB, matchmaking and dedicated game
servers. The project includes deployment workflows for Render, Atlas and Edgegap.
[Hosting setup](docs/CLOUD_HOSTING.md) covers service configuration, credentials
and server publication.

## Join in

New arenas, weapon tuning, robot designs, performance improvements, accessibility,
playtesting and documentation all help. Pick something you would enjoy playing
or building, then start with [the contributor guide](AGENTS.md).

For code or visual changes, describe the player-facing result and include the
relevant checks, screenshots or clips. [The documentation index](docs/README.md)
points to each subsystem's source and contracts.

## Built with

- [Godot](https://godotengine.org/) — game engine and desktop exports.
- [LimboAI](https://github.com/limbonaut/limboai) — bot behavior trees.
- [Phantom Camera](https://github.com/ramokz/phantom-camera) — gameplay and menu cameras.
- [Shaker](https://github.com/Eneskp3441/Shaker) — local impact shake.
- [Terrain3D](https://github.com/TokisanGames/Terrain3D) — authored planetary landforms.
- [ProtonScatter](https://github.com/HungryProton/scatter) — dropped Energy Core placement.
- [GUT](https://github.com/bitwes/Gut) — automated gameplay and integration tests.

## License

KYLR's original code, tools, documentation and authored assets are
**[Apache 2.0 licensed](LICENSE)**, except where separate terms apply.
Godot, addons and separately licensed assets retain their own licenses.
See [NOTICE](NOTICE), [third-party notices](game/THIRD_PARTY.md) and
[asset setup](docs/ASSET_SETUP.md).
