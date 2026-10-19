# Retired opaque particle reconstruction-guide prototype

Removed from the renderer after the motion experiments remained unqualified.
The environment variable below no longer enables a rendering path. This page
records the historical design and evidence; its commands are not current usage.

`GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES=1` is an experimental alternative to the
separate transparency layer. It is off by default. The two experiments are
mutually exclusive. This path currently requires single-view DLSS RR, MSAA off,
frame generation off, and eight color attachments. Unsupported configurations
retain the existing rendering path.

Eligible opaque/cutout particles retain their existing raster color and depth
behavior. Additional attachments write diffuse/specular albedo, world normal and
roughness, motion vectors, opaque color before transparency, and a dedicated R32F
opaque-guide depth. Other alpha-pass surfaces cannot overwrite those guides.
The dedicated depth starts with traced depth; only eligible opaque particles
update it. It is restored to the SDK's depth attachment after compositors, keeping
depth-writing transparent materials from corrupting reconstruction guides.

Unshaded particles have zero reflective base color/specular, with the same 0.04
diffuse-guide floor used by the traced path. Lit particles use the same BRDF-guide
approximation as the traced path. The raster path does not trace a secondary
reflection distance for particles and currently stores the miss sentinel -1;
glossy particle behavior remains unqualified. This does not make particles part
of the acceleration structure or add their indirect lighting/reflections to it.

Run the temporal verifier with `--opaque-particle-guides --capture-inputs
--resolution 1920x1080`, and repeat with `--reverse-motion`. Actual depth and
velocity must match the projected surface. Actual unshaded-particle material
guides are sampled and checked. `--ghost-writes-depth` makes the submitted ghost
control explicitly draw last and write ordinary depth: ordinary and opaque-guide
depth must differ while the opaque guides still describe the visible target.
The final priority matters because particle AABBs affect alpha sorting; otherwise
the ghost can prevent the target drawing, invalidating a target-depth assertion.

v692 passes the forward full-HD fixture, including material/depth/velocity
readbacks and deliberate-ghost controls. Worst particle p95 residual is 0.02353,
worst pixel 0.03137. Reverse v693 fails on the first moving frame (p95 0.36471).
The dedicated-depth version v696 proves the depth-writing control and readback
checks but still fails reverse first-motion quality (p95 0.35686). No threshold,
guard, or history-reset requirement was weakened. Neither result is production
acceptance or an FPS measurement.

Initial v689 failed a shader-variant collision between mutually exclusive
experimental modes; the declarations now guard that combination. v691 rejected
the observer's assumptions about hardware depth format; the observer now records
the actual depth format and accepts legitimate sampled depth formats without
changing depth tolerance. v695's first depth-writing control could occlude the
target before it rendered; its ordering was corrected for v696.

Before adoption, investigate the remaining first-motion residual, GPU simulation
motion (the current fixture moves the emitter), lit/metallic/cutout/overlapping
particles, viewport/mode transitions and the full application. Keep the ordinary
path as default while qualification remains incomplete.

Context creation previously queried SR optimal settings even for RR. Contexts now
query the requested feature and are recreated on SR/RR feature changes. The
full-HD v703 capture proves actual RR evaluation at supported half resolution
through the corrected query; its existing particle trail remains. The RR-specific
query also rejects 45% input in v702. Do not infer arbitrary-scale support from
the viewport property or claim a performance result when native evaluations stop.

The subsequent current-colour bias experiment is rejected and removed. Actual
R32F and R8 mask readbacks correctly identified newly revealed background, but
neither format improved reverse first-motion quality (v708/v711). NVIDIA's
[DLSS programming guide](https://github.com/NVIDIA/DLSS/blob/main/doc/DLSS_Programming_Guide_Release.pdf),
31 March 2026, section 3.15, states that current-colour bias is unsupported by
the latest models and should not be used. Do not restore that experiment or
select a legacy model solely to obtain a passing diagnostic.
