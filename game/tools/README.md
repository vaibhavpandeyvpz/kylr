# Development tools

Run from `game/` with the custom Godot console executable in `../engine/bin/`.
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
| Ultra native/upscaled RR comparison | `run_dlss_benchmark.ps1` |
| All-preset full-match samples | `run_graphics_matrix.ps1` |
| Configurable rendered match matrix | `run_rendered_matrix.ps1` |
| Isolated diagnostic release package | `pack_rendered_profile.gd` |
| Windows redistributable and inspection | `package_windows.ps1` |
| Custom engine/editor/template build | `build-godot-rt.cmd` |

Use fresh report/runtime names. Run renderer measurements serially on the
intended GPU. Keep validation, synchronous timings and feature-isolation trials
separate from normal gameplay measurements. Verify active features, actual
resolution and package hashes; never interpret a fixed-rate capture as FPS.

`apply_weapon_balance.py` reads `docs/gameplay/WEAPON_BALANCE.csv`. Its
`range_m` is maximum reach; optional `full_damage_range_m` defines where linear
damage falloff begins. Flamethrower primary uses 8 m full damage and 10 m maximum.

## Graphics and effects

- `run_weapon_effects_harness.ps1` opens the interactive real-weapon sandbox.
  `run-rt-effects-probe.ps1` reuses it for 43 raster/RT capture cases and supports
  all graphics presets. `-CoreOnly` checks early dropped-core visibility with
  shield/armor overlays in raster and RT. `render_vfx_catalog.gd` captures the original burst catalog.
- `preview_original_fields.gd`, `preview_surface_marks.gd` and
  `probe_effect_texture_imports.gd` check persistent fields, seeded bullet marks,
  mip chains and GPU data preservation. Keep original atlas source
  files in the library; they are required assets, not disposable test output.
- `run_renderer_startup_probe.ps1` and `run_loading_lifecycle_probe.ps1` check
  first-visible content, repeated loads, menu return and shutdown.
- `run-nvidia-rt-test.ps1` / `run-nvidia-rt-soak.ps1` exercise the generic native
  fixture; `run-rt-settings-probe.ps1` checks saved controls.
- `run_shadow_quality_probe.ps1` / `compare_shadow_quality.gd` and
  `run_arena_quality_probe.ps1` / `compare_arena_quality.py` compare captured
  shadows/arena views with comparison rendering. They are quality diagnostics.
- `run_streamline_security_probe.ps1` checks native runtime trust/fallback.
  `run_armor_overlay_probe.ps1`, `probe_rt_specular_guide.gd`,
  `probe_rt_temporal.gd`, `probe_reflection_lighting.gd` and `probe_sky_clock.gd`
  retain targeted rendering regressions that unit tests cannot observe.

## Profiling and authoring helpers

The ten [cinematic scenes](cinematics/README.md) stage five compositions per map
with the actual arena renderer, actors and gameplay effects.
`capture_map_previews.gd` refreshes the player-free arena photographs.
`capture_map_selection.gd -- --output=res://reports/<fresh-name>` captures both
real setup screens at native 1920×1080 Ultra using isolated preferences.

`capture_script_profile.gd` is the loopback debugger receiver. Start it before
`profile_rendered_combat.gd` with `--remote-debug tcp://127.0.0.1:6018` and
`-- --script-profile=1`. Its records include instrumentation overhead.
`summarize_script_profile.py`, `summarize_gpu_stages.py` and
`summarize_visual_profile.py` summarize those diagnostic logs.
`run_gpu_frame_capture_probe.py` exercises bounded native GPU captures.

The remaining `audit_*`, `inspect_*`, UI/weapon `preview_*`, movement probes,
icon/contact-sheet renderers and audio import/preparation scripts support
repeatable authoring and checks. Keep the owning contract in `docs/` beside the
feature; do not add dated test transcripts to it.

## Online and packaging helpers

`verify_online.py`, `verify_online_docker.py`, `verify_service_recovery.py`,
`start_online.ps1`, `start_online_native.py` and `account_backup.py` are documented
in [ONLINE.md](../../docs/ONLINE.md) and [ONLINE_PROTOCOL.md](../../docs/ONLINE_PROTOCOL.md).
`verify_online.py --type DM|TDM|CTF` uses real MongoDB and independent custom-engine
clients to check admission, combat, a late join and round replacement. Pass
`--mongo` or set `MONGO_TEST_URI`; probes create and remove their own database.
Keep the online client/server/UI probes, credential checks and impairment helper.
Runtime packaging depends on `inspect_package.gd`, `write_licenses.gd`,
`windows_engine_runtime.ps1` and `prepare_windows_vc_runtime.ps1`.

## Retention policy

Keep regression tests in `tests/`, reusable entry points and required helpers.
Remove completed A/B experiments, duplicate one-off previews and dead feature
switches when their replacement is verified. Keep the current rendering contract in `../../docs/RENDERING.md`.
Local reports, screenshots, diagnostic PCKs and stale package archives may be
removed when no process uses them. Retain a useful latest baseline rather than
keeping every tuning iteration. Never purge source assets, notices, prompts,
SDKs, stock engine tests or build dependencies as diagnostic clutter.

`capture_map_previews.gd` reads camera frames from `data/maps/previews.json` and captures five player-free views per map at native 1920×1080, Ultra lighting with DLSS Ray Reconstruction and no upscaling. Run with the custom editor using `--path . -s res://tools/capture_map_previews.gd`; PNGs go to ignored `reports/map-previews/`. Run the root `tools/install_map_previews.py` with the library Python environment to compress them into 1280×720 WebP at the manifest paths before game import. Optional `--map=faceoff` and `--shot=5` arguments select individual captures.
