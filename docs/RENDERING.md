# Rendering

## Graphics presets

Ultra requests the custom engine's opaque path tracer, DLSS Ray Reconstruction
and optional half-size internal rendering (960x540 for 1920x1080 output).
Disabling upscaling retains native-resolution RR. DLSS is the only custom RT
denoiser. Unsupported hardware/runtime retains raster rendering with a disabled
RT toggle and an explanation. Frame Generation is not integrated; FPS counts
rendered frames.

High uses native-resolution raster rendering with 4x MSAA. High and Ultra enable
fixture illumination and shadow casting by default. Authored ambient/raster GI
preferences remain in every preset; opaque path tracing does not consume raster
GI buffers. The independent reflection-map policy remains in Preferences.
Separate rendering is experimental and off by default in every preset.

The engine component provides a generic Godot fork, not a stock-Godot addon. Engine
features, fixtures and technical validation belong in `engine/`; game presets,
assets and integration checks belong here. Preserve stock Godot capabilities.

## Integration contract

- Use the consuming project's persistent Streamline identity. Do not borrow
  another application's numeric ID. Verify the identity in the packaged runtime.
- Feed color, depth, motion, reflectance, normal/roughness, specular hit distance
  and pre-transparency color at the primary reconstruction pass. Keep graph/native
  callback dependencies and resource lifetimes valid through evaluation.
- Match jitter, motion scaling, transforms, exposure and depth convention to the
  tagged resources. Tag hardware depth as
  `kBufferTypeDepth` with reversed-depth constants.
- Reset history at scene/view discontinuities and readiness changes. Verify mip
  bias/primary texture gradients, moving geometry, transparent effects, skinned
  surfaces and first-frame activation rather than relying on static screenshots.
- Drain viewport work before IDs are reused; release SDK resources before Vulkan
  teardown. Check repeated matches, resizing, fullscreen changes and clean exit.
- Package only pinned production runtime DLLs with signatures, hashes and
  redistribution notices. Match custom engine export templates to the editor.
