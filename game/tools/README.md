# Development tools

Run from `game/` with official Godot 4.7.2, resolved through `GODOT` or PATH.
[PLAYTESTING.md](../../docs/PLAYTESTING.md) owns validation procedure and measurement
rules. [README.md](../README.md) owns import, play, build and export setup.
Tools and their helpers are development-only and excluded from shipping exports.
Generated reports/packages belong in ignored `reports/` and `build/`.

## Primary entry points

| Purpose | Entry point |
| --- | --- |
| Import, GUT, DM/TDM/CTF and results flow | `verify.ps1` |
| Apply reviewed weapon damage, cadence, range and speed values | `apply_weapon_balance.py` |
| Physical 15-case roster acceptance, one map | `run_roster_validation.ps1` |
| Difficulty/duration sweeps and charged jumps | `run_bot_matrix.ps1` |
| Ten-weapon combat-deck comparisons | `run_arena_stress.ps1` |
| All-preset full-match samples | `run_graphics_matrix.ps1` |
| Configurable rendered match matrix | `run_rendered_matrix.ps1` |
| Isolated diagnostic release package | `pack_rendered_profile.gd` |
| Native Windows/macOS/Linux package and inspection | `package.ps1` |

Use fresh report/runtime names. Run renderer measurements serially on the
intended GPU. Keep validation, synchronous timings and feature-isolation trials
separate from normal gameplay measurements. Verify active features, actual
resolution and package hashes; never interpret a fixed-rate capture as FPS.

`apply_weapon_balance.py` reads `docs/gameplay/WEAPON_BALANCE.csv`. Its
`range_m` is maximum reach; optional `full_damage_range_m` defines where linear
damage falloff begins. Flamethrower primary uses 8 m full damage and 10 m maximum.

## Graphics and effects

`run_weapon_effects_harness.ps1` opens the interactive real-weapon sandbox.
`preview_original_fields.gd`, `preview_surface_marks.gd`,
`preview_energy_surface.gd` and `probe_effect_texture_imports.gd` check effects,
fields, hit marks and texture imports. `run_armor_overlay_probe.ps1` checks
foreground occlusion. `run_loading_lifecycle_probe.ps1` checks the menu, map loading,
repeat loads and shutdown. These graphical checks require image inspection.

## Profiling and authoring helpers

The fifteen [cinematic scenes](cinematics/README.md) stage five compositions per
map across Ramparts, Skyfall and Faceoff, using the actual arena renderer,
actors and gameplay effects. `library/tools/render_hero_showcase.py`, run with
the library Python environment, captures those scenes plus three ten-robot
portrait renders and installs compressed WebP media for the README and gallery.
`capture_map_previews.gd` refreshes the player-free arena photographs.
`capture_map_selection.gd -- --output=res://reports/<fresh-name>` captures both
real setup screens at native 1920×1080 High using isolated preferences.

`capture_script_profile.gd` is the loopback debugger receiver. Start it before
`profile_rendered_combat.gd` with `--remote-debug tcp://127.0.0.1:6018` and
`-- --script-profile=1`. Its records include instrumentation overhead.
`summarize_script_profile.py`, `summarize_gpu_stages.py` and
`summarize_visual_profile.py` summarize those diagnostic logs.

The remaining `audit_*`, `inspect_*`, UI/weapon `preview_*`, movement probes,
icon/contact-sheet renderers and audio import/preparation scripts support
repeatable authoring and checks. Keep the owning contract in `docs/` beside the
feature; do not add dated test transcripts to it.

## Online and packaging helpers

`verify_online.py`, `verify_online_docker.py`, `verify_service_recovery.py`,
`start_online.ps1`, `start_online_native.py` and `account_backup.py` are documented
in [ONLINE.md](../../docs/ONLINE.md) and [ONLINE_PROTOCOL.md](../../docs/ONLINE_PROTOCOL.md).
`verify_online.py --type DM|TDM|CTF` uses real MongoDB and independent Godot
clients to check admission, combat, a late join and round replacement. Pass
`--mongo` or set `MONGO_TEST_URI`; probes create and remove their own database.
Keep the online client/server/UI probes, credential checks and impairment helper.
Runtime packaging depends on `inspect_package.gd`, `write_licenses.gd`,
`godot.ps1` and Windows-only `windows_binary_dependencies.ps1`.

## Retention policy

Keep regression tests in `tests/`, reusable entry points and required helpers.
Remove completed A/B experiments, duplicate one-off previews and dead feature
switches when their replacement is verified. Keep the current rendering contract in `../../docs/RENDERING.md`.
Local reports, screenshots, diagnostic PCKs and stale package archives may be
removed when no process uses them. Retain a useful latest baseline rather than
keeping every tuning iteration. Never purge source assets, notices, prompts,
SDKs, stock engine tests or build dependencies as diagnostic clutter.

`capture_map_previews.gd` reads camera frames from `data/maps/previews.json` and captures five player-free views per map at native 1920×1080, High raster lighting. Run with the official editor using `--path . -s res://tools/capture_map_previews.gd`; PNGs go to ignored `reports/map-previews/`. Run the root `tools/install_map_previews.py` with the library Python environment to compress them into 1280×720 WebP at the manifest paths before game import. Optional `--map=faceoff` and `--shot=5` arguments select individual captures.
