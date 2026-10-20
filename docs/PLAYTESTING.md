# Playtesting and performance

Use the sibling custom engine for every import, test and capture. Commands run
from `game/`; `$Godot` is the console executable defined in the README.
Generated results belong in ignored `reports/`, not in source documentation.
Keep generated measurements in ignored reports; document verification procedures here.

## Functional verification

Run `pwsh -File tools/verify.ps1 -Godot $Godot` after integration changes. It
imports resources, runs GUT, exercises DM/TDM/CTF/Elimination/Gun Game and checks the results flow.
Inspect warnings as well as failures. Headless checks cannot establish rendered
appearance, audio quality or real-time FPS.

## Bot and traversal matrix

Behavior-tree, equipment-policy and resource-targeting changes also require a
baseline/current CPU comparison with the same custom engine, map, seed,
difficulty and ten-robot roster. Warm the simulation, run repeated serial trials
without concurrent builds or matrix jobs, and report average, p95, p99 and
maximum decision CPU time per physics frame alongside whole-frame costs.
Inspect spikes as well as the mean. Headless CPU diagnostics do not establish
rendered FPS or qualify the 16.67 ms rendering target.

Changes to AI, traversal, map collision/fixtures, objectives or movement cost
require DM, TDM, CTF, Elimination and Gun Game at **2, 4, 6, 8 and 10 robots on both maps**. Use the
physical match controller, not teleports in place of traversal. Every CTF case
runs for at least **120 simulated seconds**. Repeat chance-dependent results
with additional seeds and inspect objective progress, not just exit codes.

```powershell
foreach ($map in @('skyfall','faceoff')) {
    ./tools/run_roster_validation.ps1 -Map $map -ReportPrefix review -Godot $Godot
}
```

The runner requires a fresh report prefix and records hashes and activity.
For difficulty sweeps, configurable durations and the physical charged-jump
check, use `tools/run_bot_matrix.ps1 -Map faceoff`. It defaults to Skyfall;
repeat for each map. Fixed-rate/headless throughput is a functional diagnostic.

Review each robot's starting elevation, roof exit, distance, stopped time,
intent, route edge, jumps, drops, portals, pads, pickups, repairs, kills and
captures. Reproduce a failed seed with:

```powershell
& $Godot --headless --fixed-fps 60 --profiling --path . -s res://tools/profile_bot_routes.gd -- CTF 10 120 trace 123 faceoff
```

Check these behaviors:

- DM seeks fights; TDM advances into opposing territory; CTF attacks, carries,
  extracts, recovers and defends. Critical resources may interrupt an intent;
  bots otherwise pursue their decision without switching goals every tick.
- Pickups and repair targets are useful and reachable. Pressure plates do not
  toggle repeatedly while a robot stands on them.
- Portal routes deliberately enter and emerge from paired endpoints. Other
  routes avoid unintended triggers. Test crowded exits and both directions.
- Roof spawns exit through physical drops, portals or validated jumps. Charged
  jumps obey the weapon-independent EP/charge rules. Pads land on supported
  continuations; no maneuver becomes indefinite airborne steering.
- Separation prevents stacking at doors, roofs, repairs and pickups. Blocked
  robots reroute without stepping off edges or attacking through walls.

`probe_charged_jump.gd` and `probe_knockback.gd` exercise real movement and
collision; their unit-test counterparts cover rules and boundary conditions.

## Rendered performance

Use the ten-robot, ten-weapon rotating-camera combat deck for quick comparisons.
It includes infinite health/ammo, live fighting/dodging and the full surrounding
map. Keep gameplay, fixture illumination/shadows and preset settings intact.

```powershell
./tools/run_arena_stress.ps1 -Quality 2,3 -PresetLighting -GPUIndex 0 -ExpectedGPU NVIDIA -Repack -ReportName review -RuntimeDirectory reports/performance/release-review
```

For Ultra alone, `tools/run_dlss_benchmark.ps1` also verifies native DLSS RR
execution and actual internal/output dimensions. `-DisableUpscaling` retains
native-resolution RR. Use a fresh report/runtime name and `-Repack` after changes.
The all-preset/full-match runner is `tools/run_graphics_matrix.ps1`; it requires
`tools/pack_rendered_profile.gd` to prepare its default diagnostic package first.

Measure one renderer job at a time, after builds and imports finish. Pin the
NVIDIA GPU on this machine and reject a different reported adapter. Record
source revisions, package/binary hashes, GPU/CPU, preset, lighting, resolution,
internal scale, render thread, VSync, warmup, duration and combat coverage.
Compare like settings and use repeated serial trials. Report average FPS,
p50/p95/p99/max frame times and budget misses; an average can hide severe stalls.
The 60 FPS objective is **16.67 ms per rendered frame** and remains unqualified.
Do not infer FPS from headless, fixed-rate, frozen-world or disabled-feature runs.

Keep synchronous timing, GPU validation, inline timers and material/draw
isolation in separate diagnostic runs. These perturb costs or remove graphics.
`capture_script_profile.gd`, `summarize_script_profile.py`,
`summarize_gpu_stages.py` and `summarize_visual_profile.py` retain the reusable
profiling path; see [tools](../game/tools/README.md) for entry points.

## Loading, visuals and lifecycle

Use `run_loading_lifecycle_probe.ps1` for menu, repeated matches and shutdown,
and `run_renderer_startup_probe.ps1` for visibility/readiness at scene reveal.
Both require graphical validation prerequisites; review the captured images.
Loading holds simulation/audio until readiness rather than hiding a running match.

Use `run-rt-effects-probe.ps1` for the 43 effect cases in raster/RT and all
presets. Review early/peak/tail, foreground occlusion, rapid reuse, Reduced
Motion, bloom off, vertical fire, fixture lighting and RT transitions. The
interactive weapon sandbox remains available for direct FPV/TPV checks.

Manually exercise settings Apply/Revert, unsupported-device explanations,
800x600 through 1080p/portrait layouts, controller/keyboard focus, menu/match/
results transitions, death/respawn, audio, and exported gameplay. For online
verification use [ONLINE_PROTOCOL.md](ONLINE_PROTOCOL.md). Renderer behavior is
described in [RENDERING.md](RENDERING.md).
