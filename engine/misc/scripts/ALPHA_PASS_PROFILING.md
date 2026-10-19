# Transparent-pass shader isolation

Set `GODOT_GPU_PROFILE_ALPHA_FILTER=1` before launching a diagnostic process to
enable Forward+ transparent color-pass draw isolation. Ordinary launches leave
it disabled. `GODOT_GPU_PROFILE_ALPHA_MASK` is a semicolon-separated list of
case-sensitive shader-path globs to omit, such as `res://effects/*`. A leading
`!` exempts a matching path. An empty mask restores every draw.

The renderer reads the mask once per transparent pass, so a diagnostic harness
can alternate omitted groups with restored baselines in one live scene. This
does not hide nodes, stop simulation, change materials, remove ray-tracing
geometry, or change the gathered light set. It omits matching raster alpha draws
after material selection. Keep these diagnostic variables out of normal launches.

Each affected pass prints `GPU_ALPHA_FILTER mask=... skipped_elements=...`.
The count describes render-list elements, including repeated elements; it is
not a particle count, pixel count or direct measure of GPU cost. Generated
shaders without a path cannot be assigned to a file-prefix group. Confirm that
the intended mask actually omits elements and that restored baselines omit none.

Pair this with `--gpu-profile` and marked capture windows. Native printed timings
average a preceding interval. Exclude intervals crossing phase boundaries and
use both neighboring restored baselines. Live combat continues to vary, so a
single comparison does not establish a repeatable shipping FPS gain. A diagnostic
phase that omits graphics never qualifies visual completeness or performance.
