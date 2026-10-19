# DLSS feature lifecycle validation

`verify_dlss_feature_lifecycle.py` exercises SR, RR, SR and RR on the same
viewport. Each phase must query the corresponding feature, successfully evaluate
the native SDK, and produce its new expected target colour. RR additionally
requires native frame counters and exact input/output dimensions. SR must clear
RR metadata. The fixture does not qualify visual quality or performance.

Pass `--engine`, `--output` (a new directory) and `--validation-layers` (the
directory containing `VkLayer_khronos_validation.json` and its DLL). Optional
`--runtime-manifest` accepts a separately pinned production runtime for isolated
SDK comparisons. It never changes the shipping runtime. The verifier hashes the
executable, runtime DLLs, validation layer, scripts and runtime manifest and
rejects mutations during the run. Validation errors, synchronization hazards,
script errors, leaks and incomplete phases remain failures even when images
look correct. Failure manifests preserve completed phase evidence separately.
Use `--resolution 1920x1080` to repeat at 1080p output and 960x540 input; the
default is 640x360 output. The fixture and verifier both enforce the requested
output size, native RR dimensions and central colour-sample location.

## Current qualification limits

The cleaned-source editor v714 with pinned Streamline 2.10.0 fails synchronization
and image-layout validation in the SR phases (v717). Earlier v710/v712 reproduce
the same errors. All four phases render fresh colours and actually evaluate
their requested features; that is insufficient for acceptance.

An isolated Streamline 2.14.1 production runtime, independently matched against
the release archive digest, also fails (v716). Newer debug labels identify the
affected images as `nv.ngx.dlss.resource` and `nv.ngx.dlssd.resource`, rather than
the application's tagged colour/depth/motion images. The newer runtime additionally
requests `VK_NV_low_latency2` without the required present-id extension in the
current device setup. This runtime has not been adopted. v715 used an incorrect
validation-layer directory and is invalid; the verifier now rejects that path
before launch.

The subsequent 2.14.16 release, published 16 October 2026, also fails the same
isolated comparison (v720): four synchronization hazards, eight image-layout
errors and one missing-extension-dependency error. All phases complete with
successful SDK evaluation and fresh colour. Its archive SHA256 is verified
against GitHub release metadata before extraction. Neither newer-runtime result
is a complete SDK migration: both use the existing host integration and compiled
headers. They demonstrate that replacing runtime DLLs alone does not qualify the
upgrade. The shipping runtime remains unchanged.

The present-ID dependency is now handled by the host. Streamline presentation
devices optionally request `VK_KHR_present_id`, query `presentId`, and enable the
feature only when supported. No presentation IDs are synthesized by the engine.
The v721 editor builds successfully. Its isolated newer-runtime repeat v722
confirms the missing-extension error is gone, but still fails on four SDK-internal
synchronization hazards and eight image-layout errors. Pinned-runtime v723
retains its prior four synchronization/four image-layout failures, with fresh
output in all phases and no new error category. Neither result is acceptance.

[NVIDIA's changelog](https://github.com/NVIDIA-RTX/Streamline/blob/main/changelog.txt)
documents a post-2.10 Vulkan auto-exposure feature-creation fix. It motivated the
isolated comparison, but does not establish that the remaining errors are fixed.
Do not suppress SDK diagnostics, add unrelated broad barriers, disable exposure,
or weaken acceptance checks to obtain a passing run. Godot's average-luminance
texture is not a valid DLSS exposure multiplier; a manual-exposure path would
need a correct renderer exposure conversion and model-specific validation.

## Model isolation

The optional `--sr-preset K|L|M` argument is diagnostic, not a change to engine
defaults. It records the requested preset and keeps every lifecycle/validation
gate intact. Quality and performance acceptance remain false even if it passes.

v727 supplied renderer-derived exposure through a tracked 1x1 compute texture,
including the renderer's pre-exposure factor; the default model still failed.
v728 with SR K and renderer-derived exposure passed all four phases. Crucially,
the paired v729 with SR K and ordinary SDK auto-exposure also passed. The
conversion was therefore not the fix and has been removed, with its source and
evidence archived locally. Editor v730 rebuilds the cleaned implementation.
Explicit SR L v731 and SR M v732 reproduce the default's four synchronization
and four layout errors. This isolates a model-dependent failure in the tested
SDK/driver/host combination; it does not prove a particular private allocation's
purpose or identify the responsible component conclusively.

Cleaned-source repeat v733 with SR K passes all four transitions. Full-HD default
v734 reproduces the errors; full-HD SR K v735 passes all four transitions with
successful native SR/RR evaluations, fresh colours, correct dimensions and clean
shutdown. All use pinned 2.10.0. RR's preset remains untouched in these comparisons.

The current engine default is unchanged. A model's clean lifecycle result is
not evidence that its moving-image quality and performance meet release needs.
Any proposed model-policy change needs those comparisons before adoption.

The fixture also accepts `--rr-preset D|E`, independently of the SR request.
Both requested presets are recorded and checked against the capture report;
neither overrides engine defaults outside the isolated fixture. Full-HD v776
with SR K and RR E passes all four SR/RR transitions, with fresh colours,
successful native evaluations, no Vulkan validation errors and clean shutdown.
This establishes lifecycle correctness for that tested combination, not overall
image-quality or performance acceptance.
