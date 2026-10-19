# Opaque particle depth in traced viewports

Traced viewports draw particles through the raster overlay because their
per-particle transforms are not represented by the current TLAS. Routing every
particle material through the transparent color pass also disables ordinary
opaque depth writes. Opaque and alpha-clipped particles can consequently shade
overlapping fragments that a normal raster depth pass would reject.

The correction is enabled by default for single-view DLSS rendering with MSAA
disabled. `GODOT_RT_OPAQUE_PARTICLE_DEPTH=0` restores the previous path for
diagnostic comparisons. It retains
the raster particle overlay, material shader, geometry and particle counts.
Eligible opaque/cutout materials get opaque blending and normal depth writes,
without assuming that they participated in a raster depth prepass. Blended,
screen-reading, depth-disabled/inverted and instance-faded materials retain
their existing path. The new pipeline state has its own cache-key field and
hash, so it cannot alias an ordinary transparent or prepassed opaque pipeline.

The temporary particle depth provides mutual raster occlusion. Before DLSS, the
renderer restores traced opaque depth so reconstruction depth, normals and
motion continue to describe the same traced scene. A native
`RT_OPAQUE_PARTICLE_DEPTH active=1` acknowledgement means an eligible surface
actually used the corrected path; requesting the environment variable alone is
insufficient evidence.

Raw tracing, other upscalers, MSAA and multiview retain their existing particle
path until separately verified.

The supported configuration was checked against raster reference output for
opaque/cutout overlap, foreground/background cover and instance fading, at
native and half resolution with Vulkan synchronization validation and clean
shutdown. The separate-thread path was also checked at half resolution. A
consuming application's 40-case effects suite passed with successful native
DLSS evaluations for every capture. These checks do not establish universal
temporal quality or application FPS. Those still require full-effect application
benchmarks and visual assessment. Captures that omit effects do not qualify FPS.

Run `check_rt_particle_depth.ps1 -OutputDirectory <fresh-directory>
-ValidationLayerPath <layer-directory> -Scale 0.5` from PowerShell, then
`python misc/scripts/compare_rt_particle_depth.py <fresh-directory>
--output <fresh-result.json>`. Repeat with `-Scale 1` and, where supported,
`-RenderThread separate`. Each run captures a raster reference, the original
RT path (a negative control), and the candidate. The fixture requires successful
native DLSS evaluations, not just an enabled setting. Its temporary project uses
a fresh Streamline project identity; shipping applications need their own identity.
The comparison covers static overlap, cutout holes, fading and foreground cover;
it does not establish moving-effect quality or application FPS.
