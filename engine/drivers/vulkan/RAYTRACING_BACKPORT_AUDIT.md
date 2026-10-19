# Upstream ray-tracing review

Reviewed upstream `godotengine/godot` master at
`4d10419cacd6d3009976e8f9fd3abd970fd58018` (2026-10-15, 4.8 beta), against
`4.7.2-stable` and this fork's existing NVIDIA renderer. The existing upstream
remote was fetched and its shallow history completed; no master checkout or
wholesale merge was performed.

| Change | Disposition |
| --- | --- |
| [d16b7e1a99](https://github.com/godotengine/godot/commit/d16b7e1a9987b532fefcb09e6fd63255d41cbad1), merged by [PR 124370](https://github.com/godotengine/godot/pull/124370) | Backported the two acceleration-structure descriptor writes to index by `writes_amount`, consistent with skipped immutable samplers. This was absent locally. |
| [PR 122051](https://github.com/godotengine/godot/pull/122051), commit `a5d71d7a66c6f4746ffc8540e7746482750c2413` | RT stage-bit masks, ray-query extension/features and the unknown-index sentinel were already handled locally. Restored its local-struct/`memcpy` instance construction, retaining this fork's cached BLAS address. The existing RD layer already batches instance records in CPU memory, so no new FPS gain is claimed. |
| Texture streaming, screen-space contact shadows and broad renderer changes | Not imported as a blanket upgrade. These change independent contracts and do not establish a denoiser-quality fix. |
| [D3D12 RT PR 118654](https://github.com/godotengine/godot/pull/118654) and [non-uniform indexing PR 117166](https://github.com/godotengine/godot/pull/117166) | Open at review time. Not treated as merged or production-qualified; this fork already carries NVIDIA-specific bindless material handling. |

## Validation and remaining coverage

`misc/scripts/probe_ray_query.gd` reads actual GPU results for an indexed
triangle, two translated TLAS instances with different custom IDs and masks,
and a deliberately masked miss. It requires a graphical Vulkan invocation with
validation enabled. It also advances main-renderer frames after local compute
device teardown. Its first successful geometry readback exposed a separate
integration error: local Vulkan device destruction called global Streamline
shutdown. Local devices now bypass Streamline's device-creation proxy and do
not publish capabilities, reinitialize plugins or shut down the presentation
device's SDK context.

This script does **not** exercise the immutable-sampler/skipped-write descriptor
case: that native shader-creation path is not exposed by the current scripting
API. The upstream patch, source comparison and ordinary RT regressions must not
be described as a direct GPU regression test of that specific binding layout.
Record current build and validation results before release; none of these
changes establishes image-quality, cross-vendor or performance qualification.

## Repeated uploads across frame boundaries

`misc/scripts/probe_unconsumed_skeleton.gd` updates a 15-bone native skeleton
without a skinning draw consuming its buffer. Before the fix, Vulkan
synchronization validation reports a 720-byte transfer write-after-write hazard
in both Safe and Separate rendering. This is independent of the path tracer.

Resource tracker rollover clears the previous command index while retaining
resource usage. Repeating the same write usage in the next submission must
still emit a memory dependency. The graph now includes retained previous-frame
stages when deciding whether a repeated write needs a barrier. It does not add
a CPU wait or a device-wide idle.

## Optional SDK private-data feature

A controlled Streamline 2.12 / DLSS 310.7 runtime test exposed
`vkCreatePrivateDataSlot-privateData-04564` during device initialization.
The SDK calls the core entry point when available; availability does not imply
that `VkPhysicalDevicePrivateDataFeatures::privateData` was enabled.

The driver now queries this core feature on Vulkan 1.3-capable devices and
enables it when supported. The same primitive-scene test no longer reports the
private-data VUID. It still reports two image-layout errors during the first SR
evaluation, so the newer SDK set is not qualified or adopted. Supplying explicit
neutral optional SR mask textures did not remove those errors; that experiment
was reverted. No validation messages are suppressed.

## Per-light shadow enablement

The inherited opaque path tracer always traced visibility rays. It never
uploaded `Light3D.shadow_enabled`, so disabling shadows had no effect for
directional, omni, spot or area lights. The same issue affected lights authored
without shadows, including transient effect lights.

`RT_LightData` now uses one reserved 32-bit slot for this boolean. Its 112-byte
std430 stride is unchanged and remains checked by the C++ static assertion.
Both directional and positional gathering populate the field. The shared light
evaluator skips visibility traversal only when that individual light disables
shadows; angular/range/BRDF attenuation remains active. This applies to pipeline
shadow rays and inline ray queries. It does not change the light's energy or
make a global shadow switch. Scenes that want shadows must explicitly request
them, consistent with the existing Light3D property and its default.

`misc/scripts/probe_rt_light_shadows.gd` verifies On/Off/On against a matte floor
and occluder, keeping a separate unoccluded control sample. The original editor
leaves the occluded sample black in all three phases for every light type.
The corrected editor restores light only during Off, then restores the shadow
on re-enablement, while the unoccluded sample stays stable. An additional mixed
red/blue pair verifies opposite shadow settings simultaneously and after
swapping them; this checks per-light behavior and the SSBO array stride.

Run `misc/scripts/check_rt_light_shadows.ps1 -OutputDirectory <fresh-directory>`.
It creates its own minimal Forward+ project without application assets or
scripts, uses the custom editor and synchronization validation, and retains
probe/wrapper/runtime/binary hashes. `-RenderThread safe|separate` and
`-QueryShadows` select the tested paths. The four combinations pass on the
tested Windows Vulkan device, with 15 captures each and clean shutdown.
The output project, reports and local SDKs are generated artifacts.

This verifies the boolean shadow control, not all Light3D shadow properties,
denoiser quality, cross-device compatibility or a measured FPS improvement.

## Forward-pointer optimizer compatibility

The optional re-spirv optimizer does not support `OpTypeForwardPointer`.
Physical-storage-buffer shaders can legitimately contain this declaration.
The Vulkan driver now detects it at instruction boundaries before invoking
re-spirv, preserves the original module, and leaves specialization to Vulkan.
The existing external-compiler preservation rule remains in place. This is an
unsupported-optimizer fallback, not removal of a shader capability or a change
to ray-tracing output. No FPS gain is claimed.

`misc/scripts/probe_spirv_forward_pointer.gd` compiles a recursive physical
buffer reference, traverses two nodes, and verifies a non-default specialization
constant: 40 + 2 must produce 42. The descriptors also declare the physical-node
reads to the RD graph so uploads are synchronized. A baseline reproduced the
unsupported message with the correct result. The updated editor and packaged
release retain the result without that message, validation errors or exit leaks.
The packaged script differs only by its release main-loop class declaration;
templates retain their normal restriction on source/path overrides.