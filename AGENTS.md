# KYLR agent guide

The source is organized into `library/`, `engine/` and `game/` folders. Run Git
commands from this root; inspect and preserve existing changes before editing.

Read [development guidance](docs/DEVELOPMENT.md), then the relevant rules:

- [Game guidelines](docs/guidelines/game.md): gameplay, UI, effects, audio,
  networking and testing. [Gameplay](docs/GAMEPLAY.md), [rules](docs/RULES.md)
  and the [focused index](docs/gameplay/README.md) own game behavior.
- [Library guidelines](docs/guidelines/library.md) and
  [modelling contract](docs/library/MODELLING.md): scripted Blender assets,
  materials, animation, collision, export and handoff into the game.
- [Engine guidelines](docs/guidelines/engine.md): reusable, project-neutral
  engine implementation, capability checks and upstream/vendor conventions.
- [Build and release](docs/BUILD_AND_RELEASE.md): custom engine builds,
  dependencies, package validation and GitHub releases.

Discover local skills with
`rg --files --hidden library/.codex/skills game/.codex/skills -g SKILL.md`.
Read relevant skills before applying them; prefer `.codex` to `.claude` copies.
Most cover Blender disciplines, not general gameplay or CI work. Follow the
project's scripted headless Blender workflow and source generators.

Use `engine/bin/godot.windows.editor.x86_64.console.exe` for game runs,
imports and validation. Never substitute stock Godot. Run game tools from
`game/` and asset generators from `library/`. Keep builds, caches, SDKs,
reports and secrets out of Git. Read [the documentation index](docs/README.md)
for the owning contract before changing a subsystem. Document the current
implementation directly; omit development history, implementation comparisons,
inspiration sources and obsolete plans.
