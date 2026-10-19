# Conservative ray-tracing light index experiment

`GODOT_RT_LIGHT_GRID=1` opts into a world-space cell index for the existing
importance-sampled light set. The default remains full enumeration while
performance, lifecycle and full-scene qualification are in progress. The index
does not increase the renderer's current 64-light upload limit.

Each cell stores two 32-bit membership words. Directional and unbounded lights
remain global. Finite lights populate every cell overlapping their range's
bounding box, with an additional cell of padding. Power-of-two cell widths and
a bounded coordinate-precision budget keep the index conservative. Unsupported
counts, extreme coordinates and allocation failures fall back to enumeration;
they must never silently remove lighting.

Set bits are visited in ascending original light-index order. Removed lights
have zero sampling support at the hit position, so the remaining target weights,
random-number consumption and full-enumeration selection PDF are preserved.
This is broad-phase rejection, not a random candidate subset or reservoir reuse.
The byte payload is cached per viewport and refreshed when gathered lights
change. It is released with that viewport's other ray-tracing buffers.

## Deterministic transport fixture

Run `python misc/scripts/verify_rt_light_grid.py --engine <editor-console-exe>
--validation-layers <layer-directory> --output <fresh-directory> --render-thread
safe`, then repeat with a fresh output directory and `--render-thread separate`.
The fixture uses 64 mixed lights, diffuse/metal surfaces and three bounces with
DLSS active. A fresh fixture project identity and native SDK evaluation counters
are required; a configured DLSS setting alone does not prove successful evaluation.
The fixture reads raw HDR transport before reconstruction, rather than using
the denoised display image to establish equivalence.

`GODOT_RT_LIGHT_GRID_CAPTURE=1` exposes opt-in metadata on the render buffers:
the RT frame index and viewport-owned native light/index buffer RIDs. The probe
reads those buffers on the render thread. Production rendering does not publish
this metadata. The fixture prewarms compilation and aligns fresh viewports to
the same global 32-phase jitter position; raw captures use RT frame 192. Both
the RNG frame and actual projection jitter must match or the verifier rejects
the comparison. The earlier v620 attempt did not align jitter and is not an
equivalence pass, despite clean captures and validation.

The independent CPU oracle checks the actual uploaded cell masks against light
ranges at random positions, light centers and range boundaries. The GPU transport
files must match byte for byte and contain finite, nonblack HDR color. A deliberately
omitted directional light must both fail the CPU oracle and change at least 1%
of raw GPU pixels, proving that the renderer consumes the submitted masks. An
additional in-memory missing-bit control exercises finite-light local-cell
rejection. Executable, source, project and pinned production runtime hashes stay
frozen during capture; synchronization diagnostics and exit leaks fail the run.

`--zero-indirect` additionally assigns zero indirect energy to 32 of the 64
lights. The verifier checks the actual uploaded light buffer for that count;
direct energy remains enabled, and the same transport, oracle, missing-light
controls and native reconstruction checks still apply. Baseline v780 passes
with 13,197 oracle positions and clean synchronization/shutdown.

An early-return candidate for these zero-weight indirect light proposals builds
in v781 and passes the within-build oracle in v782. However, its cross-build raw
HDR comparison differs at 7 of 57,600 normal-capture pixels (maximum absolute
difference 0.00024414); the omitted-directional control differs at two pixels
(maximum 0.00048828). Uploaded lights, grid, RNG frame and projection jitter
match. The cause of the small differences is not established. The candidate is
reverted, no performance gain is claimed, and byte-equivalence is not waived.
Restored-source editor v783 builds successfully. Its v784 control passes all
fixture checks and matches all nine baseline raw/light/grid binary files byte
for byte, confirming restoration of the tested rendering behaviour.

The v621 Safe and v622 Separate fixtures pass 13,197 positions and exact raw
equivalence. Their submitted negative controls change 54.0% of raw pixels; the
CPU oracle detects both negative controls. Those earlier fixtures omitted the
project identity and did not assert native SDK evaluations, so they prove raw
transport correctness only. They do not establish active DLSS API use, full-scene
quality or FPS qualification. The index remains disabled by default pending the
remaining qualification and repeatable application performance measurements.

Use an editor executable for this source-project fixture. Release templates built
without path overrides reject `--path`; the v624 direct-template attempt fails
for that reason before rendering. That attempt is not a release-runtime pass.
Validate normal packaged release applications separately.
