# Primary ray texture footprints

Implicit `texture()` lookups in hit shaders do not have fragment derivatives and
sample the base mip. The primary triangle hit now computes analytic screen-space
derivatives from its position/UV edges and the current camera projection. It
differentiates the perspective divide at the hit and inverts the triangle-to-pixel
Jacobian. The footprint uses the internal ray-launch resolution. Material UV
scale and local/world triplanar transforms are applied before `textureGrad()`.
Offsets do not change the footprint. Raster material sampling is unchanged.

Generated StandardMaterial3D/ORMMaterial3D sampling uses the footprint for ordinary
UV textures, normal maps, triplanar projections and detail textures. The fallback
material evaluator also uses it. Nearest filtering without mipmaps retains its
existing sampler behavior. The frame has no extra rays or denoising pass.

Spatial shaders can opt into explicit filtering using these read-only built-ins:

| Built-in | Meaning |
| --- | --- |
| `RAY_HIT_DERIVATIVES_VALID` | True only for a supported primary triangle footprint. False in raster shaders. |
| `RAY_HIT_POSITION_DDX`, `RAY_HIT_POSITION_DDY` | World-space hit-position change per internal pixel. |
| `RAY_HIT_UV_DDX`, `RAY_HIT_UV_DDY` | Raw mesh UV1 change per internal pixel, before vertex/material transforms. |

The vector built-ins are zero outside supported hits. Consumers must check the
valid flag, transform gradients consistently with their coordinates, and use
their original sampling path otherwise. Arbitrary ShaderMaterial `texture()`
calls are not automatically differentiated. Shader code must explicitly use
`textureGrad()` to opt in.

## Scope still requiring work

- Secondary ray cones/differentials and procedural hit footprints are not
  implemented here. They retain their previous sampling behavior.
- Alpha-test/visibility any-hit shaders retain their previous sampling behavior.
- Height-map/parallax traversal and point coordinates are unchanged. Derivatives
  of parallax-adjusted UVs are not reconstructed.
- Ordinary UV2 sampling still follows the existing ray-tracing UV2 path, which
  aliases UV1. This change does not implement a separate UV2 attribute stream.
- The analytic formula supports orthographic projection, but the existing ray
  generator does not correctly construct orthographic rays. Orthographic rendered
  output is not qualified by the perspective-camera fixture.

`GODOT_RT_PRIMARY_TEXTURE_GRADIENTS=0` disables the footprint for an A/B diagnostic;
normal execution enables it. This switch is not a substitute for capability or
quality checks. Scene support and denoiser quality remain separate requirements.

## Render check

`probe_rt_texture_footprint.gd` uses a red base mip and green smaller mips, with
unshaded materials and no denoiser, AA or reconstruction. Its `--mode=on`, `off`
and `raster` cases cover near/far views, nearest sampling, mirrored/scaled UVs,
compressed geometry, transformed triplanar materials, oblique cameras and UV1/UV2
detail shader generation. Use a fresh `--output=<absolute directory>` with a
Vulkan build; `off` additionally requires the environment switch above. Passing
these cases verifies mip selection, not complete image quality or game FPS.
