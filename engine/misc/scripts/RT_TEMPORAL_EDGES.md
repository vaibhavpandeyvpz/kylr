# Temporal silhouette diagnostic

Run `python misc/scripts/verify_rt_temporal_edges.py --engine <editor-exe>
--validation-layers <layer-directory> --output <fresh-directory> --scale 0.5`.
Repeat with `--projection orthographic`, `--scale 1`, or
`--render-thread separate` when qualifying those configurations. Each run uses
a fresh Streamline project identity and pinned production runtime hashes.

Use `--resolution 1920x1080` to exercise full-HD output (960x540 input at
scale 0.5). The default 640x360 fixture remains useful for isolating artifacts;
neither resolution replaces the other. Both retain the same three-output-pixel
guard and trail threshold. Actual viewport and native reconstruction dimensions
must match the requested resolution.

The fixture moves a camera past a stationary lit quad, translates a lit quad,
and translates an opaque unshaded GPU particle. It covers a complete 32-phase
half-resolution jitter cycle, aligned after native material readiness. A
positive foreground contrast check rejects empty output. Native RR evaluations
must continue during motion without repeated history resets.

For each step, the oracle examines pixels inside the previous silhouette,
excluding a three-output-pixel guard around the current silhouette. It compares
these vacated pixels against the uniform background captured before adding the
target. The maximum per-frame 95th-percentile RGB difference must remain at or
below 0.05. A raster reference must pass. A deliberately submitted translucent
ghost must fail for at least 12 frames in each case, proving that the oracle
detects visible residual color. The guard and threshold are fixed diagnostics,
not universal perceptual quality standards.

`--capture-inputs` additionally samples actual RT depth and motion buffers at
the foreground and at a separate, unobstructed background point. A small compute
shader copies the values to a readback buffer; source textures do not need a
transfer-read flag. The verifier checks expected projected depth within 0.00001
and UV velocity within 0.0001. The particle's guide samples intentionally expect
background data: the current raster-overlay path does not produce its own RT
guides. These readbacks synchronize work and cannot qualify FPS.

`--sharpening 0` isolates the optional sharpening pass. It does not select a new
denoiser or remove materials. Engine/process/runtime hashes remain frozen, and
validation errors or exit leaks fail capture. Reports preserve the verifier
source, project, captured probe, representative PNGs and per-frame metrics.

The initial orthographic v657 result was invalidated by image review: it did not
require visible foreground, and the old pinhole ray generation almost entirely
missed the target. The visibility check now rejects that result. The subsequent
orthographic correction uses per-pixel near-plane origins, parallel ray
directions, and the SDK's orthographic flag; v662 passes the strengthened checks.

Perspective v660 still detects residual color for camera and particle motion.
Disabling sharpening (v661) does not eliminate it. Diagnostic sign reversals
(v663/v664) make it worse and were removed from ordinary engine code. The native
jitter convention agrees with the positive clip-space offset in NVIDIA's
[Vulkan reference vertex shader](https://github.com/nvpro-samples/vk_streamline/blob/main/shaders/scene.vert).
The pinned SDK 2.10 RR guide accepts hardware or linear depth; hardware depth is
not by itself an integration omission.

The full-HD v670 capture uses 1920x1080 output and 960x540 input. Camera and
lit-object motion pass; the particle case still exceeds the fixed threshold in
one of 32 frames (worst per-frame p95 difference 0.06275). Raster passes and the
submitted ghost is detected in all 32 frames of every case. Sampled depth and
velocity guides meet their tolerances, with 34 native evaluations and no resets
per case. This localizes a remaining moving-overlay defect; it is not an FPS or
full-scene acceptance result. The lower-resolution perspective failure remains
recorded separately. The corrected orthographic v669 capture passes.

Experiment v674 includes all raster overlays in the optional color-before-
transparency guide, following the pinned SDK's suggested diagnostic. It leaves
the measured full-HD residuals unchanged. The experimental renderer path was
removed; its source and verifier are preserved with the local capture. This
does not test the SDK's separate premultiplied transparency-layer input.

This fixture does not qualify camera rotation, vertical movement, skinning,
textured silhouettes, specular reprojection, the full application, performance
or every supported platform. A captured or narrowly passing result must not be
presented as blanket production acceptance.

## RR model comparison

`--rr-preset default|D|E` records an explicit diagnostic request through the
existing Streamline API. It does not change the engine default. The wrapper
checks both the fixture acknowledgement and saved report, while retaining native
evaluation counters, guide readbacks, raster and submitted-ghost controls and
the original threshold. Requested presets are not a claim about driver overrides.

On pinned SDK 2.10.0, full-HD v736 (forward) and v737 (reverse) with requested RR
E pass all three motion cases. Worst particle p95 residual is 0.00392 forward
and 0.0 reverse. Raster controls pass; submitted ghosts are detected in all 32
frames of each case. Synchronization validation and shutdown are clean. Both
particle integration experiments remain disabled. This is a promising diagnostic
improvement over the default-model residual, not full application or FPS approval.

The newer SDK's RR responsivity mask is not a substitute input for this comparison:
its integration guide states that it is compatible only with RR F. No such mask
was added to the D/E path.

## Super Resolution comparison

The separate transparency-layer and opaque-particle material-guide native
experiments have been removed. Historical experimental captures remain evidence
of rejected approaches, not supported renderer options.

`--super-resolution --sr-preset K` disables path tracing and tests the raster
Super Resolution path at the same output/input dimensions. Native diagnostics
count successful SR evaluations and resets independently of RR. Foreground
particle guide expectations use the raster surface rather than a traced backdrop.

SR input readbacks run on the render thread after the completed draw, followed
by `RenderingServer.force_sync()`, without advancing another frame. This observes
the decoded motion vectors submitted to the SDK. The earlier v746 attempt
sampled the compositor's pre-decode sentinel and correctly failed input checks;
it is not evidence of incorrect SDK motion inputs. RR retains its original
sampling stage. These synchronized captures cannot measure performance.

Full-HD SR K forward v747 and reverse v748 pass all three motion cases, native
evaluation/reset continuity, depth/motion readback tolerances and clean Vulkan
synchronization/shutdown. Raster controls pass, and the deliberate ghost is
detected in all 32 frames of each case. Worst per-frame p95 excess is 0.0 forward
and 0.00392 reverse. The existing 0.05 threshold remains unchanged. These tests
do not establish the broader quality or performance of a shipping model policy.

RR E forward regression v753 on the shared SR-capable fixture also passes at
full-HD output with input readbacks enabled. Camera/object p95 excess is 0.0;
particle p95 is 0.00392. Native continuity, raster and deliberate-ghost controls,
synchronization validation and shutdown pass. This confirms the RR sampling
stage still works after the SR observer refactor, within the fixture's scope.

After removal of both rejected native particle experiments, full-HD RR E
forward/reverse v763/v764 and SR K forward v765 pass native continuity, guide
readback tolerances, raster and deliberate-ghost controls, synchronization and
shutdown. RR particle p95 excess is 0.00392 forward and 0.0 reverse; SR K p95 is
0.0 in all three cases. Removed experimental flags now fail argument validation
before starting a renderer job. The ordinary opaque-particle depth path remains.

The fixture's obsolete layer/material-guide readback branches have also been
removed. Its compute readback now contains only the requested depth and motion
samples; SR still reads after the completed draw. Full-HD RR E regression v777
passes with camera/object p95 excess 0.0 and particle p95 excess 0.00392. The
deliberate ghost is detected in all 32 frames of each case, with clean native
continuity, validation and shutdown. No trail or input tolerance was relaxed.

The verifier now rejects a requested input capture when every sample omits its
inputs, as well as partially missing captures. Negative checks reject absent
inputs, incorrect depth/velocity, invisible foreground, wrong dimensions and
the wrong feature. Both SR and RR preset requests must match the capture report.
Full-HD SR K v778 passes with these stricter checks enabled: p95 excess is 0.0
in all three cases, and all 32 deliberate-ghost frames are detected per case.
Depth/motion readbacks, native continuity, synchronization and shutdown pass.
