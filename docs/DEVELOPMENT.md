# Development contracts

The parent workspace is the only Git root. `library/`, `engine/` and `game/`
are regular folders on `main`, with one commit and one remote. Do not initialize
component repositories or introduce submodules. Inspect existing changes before
editing. Preserve upstream engine/vendor notices and asset licenses.

Keep checked-in documentation, comments, configuration and generated metadata
free of machine-specific absolute paths. Use repository-relative paths and
discover executables through PATH or configurable environment variables. Keep
local executable overrides and diagnostic output outside source control.

Run game commands from `game/` using
`../engine/bin/godot.windows.editor.x86_64.console.exe`. SDKs, build dependencies
and diagnostic output stay in ignored `engine/.local/`. Do not use system Godot,
stock export templates.

Asset generators run from `library/` with Blender 5.2 headless:
`blender` resolved from PATH.
Python helpers outside Blender use `library/.venv/Scripts/python.exe`.
Change generators first, regenerate and validate there, inspect previews and
required round trips, then copy only runtime exports into `game/assets/`.
Keep sockets, collision companions, rig metadata and animation consumers in sync.
Generated library meshes, previews and animation targets are normally ignored.

Local Blender skills live in `library/.codex/skills/` and `game/.codex/skills/`;
use `.claude/skills/` only if the required `.codex` copy is absent. Load the
selected skill and required instructions; project contracts override generic defaults.
Read the [library guidelines](guidelines/library.md) and
[modelling contract](library/MODELLING.md) for model work.

The [game guidelines](guidelines/game.md) route each subsystem to its owning
contract. Update that contract when changing rules. Game modes are Instant Action
and Online Multiplayer; match types are DM, TDM and CTF. A robot is a player
character; a bot is an AI-controlled robot. Bot, traversal, map collision,
objective or movement-performance changes require the roster matrix and profiling
in [playtesting](PLAYTESTING.md). Headless tests do not establish visual or audible quality.

Keep the engine reusable and project-neutral. Game-specific behavior belongs in
`game/`; engine tests use generic fixtures. Read [engine guidelines](guidelines/engine.md).
