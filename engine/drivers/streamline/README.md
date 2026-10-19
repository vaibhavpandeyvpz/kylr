# Streamline integration

Streamline is optional. Vulkan support, DLSS Super Resolution, Ray Reconstruction,
Reflex, NIS and Frame Generation are separate capabilities. Query the feature
actually needed; SR support alone does not establish RR support.

## Application identity

Configure identity in the consuming application's project settings, before
native renderer initialization:

- `rendering/streamline/application_id`: an NVIDIA-assigned numeric application
  ID, when the application has one. Default `0` selects the engine/project path.
- `rendering/streamline/project_id`: the consuming project's persistent unique
  GUID. Generate it once for that project and retain it across builds.

With no numeric ID, initialization supplies `EngineType::eCustom`, the Godot
engine version and the project's GUID, using the Streamline 2.10 identity
interface. Do not borrow another application's assigned ID. An empty GUID can
leave SR available while RR reports unsupported; do not treat that as complete
feature support. Confirm capabilities and successful evaluation with the actual
shipping project identity and libraries. Identity configuration does not replace
NVIDIA's applicable distribution, testing or registration requirements.

## Native resource ownership

Streamline evaluations are RD graph callbacks. Their input reads, output writes,
native layouts and frame tokens must match the recorded frame. SR/RR resources
are tagged through their immediate evaluation; present-time consumers require
longer lifetimes and a separate audit.

Before destroying a DLSS viewport context, queued callbacks and GPU work finish
through `RenderingDevice::flush_and_wait()`. Used SR/RR/NIS feature resources are
then released through `slFreeResources`, before RD textures are destroyed and
the viewport ID is reused. This explicit teardown stall is not a per-frame
synchronization strategy. Global `slShutdown` remains before device destruction.

The Windows interposer is resolved relative to the executable, verified with
the SDK's dual-signature helper before loading, and loaded with restricted DLL
search flags. Missing libraries leave optional features unavailable. An invalid
signature is rejected; do not add a release bypass.

Only the presenting Vulkan device owns the global Streamline plugin context.
RenderingDevice's local compute devices use native Vulkan device creation and
must not republish capabilities, reinitialize plugins or invoke global SDK
shutdown. Destroying one must leave main-renderer frame tokens and reconstruction
usable. The current RD initialization convention gives local devices one frame
and presenting devices at least two; the driver uses that distinction for these
ownership decisions.

## Qualification

Source correctness, successful SDK calls, Vulkan validation, image quality,
latency and performance are distinct gates. In particular, existing Frame
Generation code is not evidence that a consumer has integrated its HUD-less/UI
buffers, swapchain transitions or menu/loading/pause handling. Test each exposed
feature on supported hardware with production runtime libraries and retain
binary, SDK, probe and library provenance.

`runtime_manifest.json` pins the Streamline 2.10.0 production archive, twelve
Windows runtime libraries and their redistribution notices. The archive digest
was verified against the official release asset before fingerprinting its
`bin/x64` files; development directories are excluded. Distributors should
check these fingerprints and NVIDIA signatures before staging libraries, then
verify the copied files. A matching local SDK directory alone is not an
independent production-runtime pin. Updating the manifest requires renewed
runtime, image-quality and deployment qualification.

## Matrix convention regression

Godot applies matrices to column vectors. Streamline's SDK helpers apply row
vectors and place affine translation in the final row. `sl_convert_matrix`
therefore transposes the mathematical transform: each Godot column becomes a
Streamline row. Copying mathematical rows unchanged is not a correct conversion
merely because Streamline stores its matrices in row-major order.

Run `misc/scripts/check_streamline_matrices.ps1` with MSVC and Python available.
The script extracts the exact production conversion helper and compiles a
generic probe against the vendored Streamline headers. It checks a camera's
origin, the SDK rigid inverse and an asymmetric reverse-Z perspective
projection. Outputs pin the source, probe and header hashes. Optional path
arguments support other dependency locations. Numerical correctness does not
replace rendered jitter, motion-vector, reconstruction or lifecycle validation.

## Ray Reconstruction material guide

The specular-albedo guide uses `EnvBRDFApprox2` from the matching Streamline
2.10 Ray Reconstruction guide, section 4.2.1. Linear material roughness is
squared for that approximation. Preserve low and colored reflectance; do not
double the guide or impose a dielectric 0.04 floor on every material channel.
The linear guide is bounded to [0, 1] for storage. Its shader retains the
upstream MIT notice. Diffuse guide handling is independent of this calculation.

Correct material inputs alone do not guarantee sharp shadows or stable
reflections. Validate these in motion, at each exposed internal resolution,
against a converged reference; an SDK-documented formula is not itself an
image-quality acceptance result.

## Asynchronous material readiness

`misc/scripts/check_rt_unshaded.ps1` creates an independent primitive scene and
records spatial constancy after 24, 120 and 360 frames, with earlier diagnostic
captures. It supports native/half-resolution RR and raw tracing,
optional studio lighting and a lit-to-unshaded material replacement. It pins
source/runtime hashes and uses Vulkan synchronization validation. With
`-EngineVerbose`, the RR test also rejects repeated history resets between
frames 120 and 360. Source inspection or this fixture alone does not qualify
all scene transitions, moving effects, reflections or performance.
