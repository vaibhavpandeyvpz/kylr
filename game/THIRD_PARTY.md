# Runtime and development dependencies

- Godot 4.7.2 and its bundled Jolt Physics, ENet, glTF/FBX importers, and AStar3D: engine-maintained runtime subsystems.
- Microsoft Visual C++ x64 runtime 14.51.36247: the three required release CRT DLLs are bundled application-local for Streamline, verified by pinned hashes and Microsoft signatures. Prepare from the stable Visual Studio redist directory with `tools/prepare_windows_vc_runtime.ps1`; the original redistribution notice is retained under `licenses/engine-rtx/MSVC`. Redistribution is subject to the installed Visual Studio terms and [Microsoft's distributable-files list](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution). The supported Windows baseline is Windows 10 or newer. Runtime updates require a pin update and renewed deployment validation.
- GUT 9.6.1, MIT, https://github.com/bitwes/Gut: automated Godot integration and rule tests. License retained in `addons/gut`.
- LimboAI 1.8.1, MIT, https://github.com/limbonaut/limboai/releases/tag/v1.8.1: official GDExtension package for Godot 4.6+, tested here with Godot 4.7.2. Behavior trees and native debugging are bundled in `addons/limboai`; game-specific tasks live in `scripts/ai/tasks`.
- Phantom Camera v0.11.0.3, MIT, https://github.com/ramokz/phantom-camera/releases/tag/v0.11.0.3: live 3D camera hosting, view priority, and transitions. License retained in `addons/phantom_camera/LICENSE`.
- Inter, Rajdhani SemiBold and Rajdhani Bold, SIL Open Font License 1.1, from https://github.com/google/fonts. Font files and licenses are retained in `assets/ui/fonts`.
- Google Material Symbols (shield, health and safety, bolt, flag, timer, skull), Apache License 2.0, from https://github.com/google/material-design-icons. SVGs and the license are retained in `assets/ui/icons/material_symbols`; the SVG root fill is white so Godot can tint each icon at runtime.
- Epidemic Sound weapon and world effects: separately licensed downloads and trimmed mono game cues. Source audio, prepared WAVs and import metadata are excluded from Git. Runtime paths remain in `assets/audio/catalog.json`; local download and installation instructions are in [asset setup](../docs/ASSET_SETUP.md). Each developer uses their own credentials and applicable license.

Models and collider meshes are authored in the project. The original regolith albedo was generated with OpenAI Imagegen without third-party image inputs; its periodic PBR maps and generator are included in `library/textures/lunar_surface/`. Mixamo animation sources and retargeted clip binaries are separately obtained/generated local assets, excluded from Git. The repository retains animation catalogs, the [download specification](../library/animations/downloads.json), and retargeting code; [asset setup](../docs/ASSET_SETUP.md) lists the required downloads. Runtime code reads prepared local files without contacting Mixamo or Epidemic Sound.

Effect meshes and procedural data textures are authored in `library/`. Three original combustion/dust color flipbooks were created with
OpenAI Imagegen without third-party image inputs; bitmap sources and prompt
records are retained in the library. Runtime shaders and compositions are under
`shaders/original/` and `scripts/presentation/vfx/original/`. Combat
shaders are separate assets. Bullet marks use an original seeded procedural
shader instead of a bitmap atlas. Asset licenses apply independently to sounds, animations and textures.

The custom RTX engine uses Streamline 2.10.0 (MIT source integration, with
separately licensed NVIDIA binary runtimes). The Windows package retains the
Streamline and third-party notices, plus the supplied DLSS, NIS and Reflex
license files under `licenses/engine-rtx`. The packager verifies pinned production
runtime hashes and NVIDIA signatures. Capability and runtime availability remain
separate from image-quality, performance and deployment qualification.
