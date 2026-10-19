# Transform descriptor validation

Forward+ refreshes invalid transform descriptors before binding them, including
particle, MultiMesh and skeleton buffers replaced by earlier rendering work.
The renderer now avoids repeating that validity lookup when the same descriptor
is already bound in the current draw list. Each new pass starts with no cached
binding, and changing descriptors still performs the original validation and
refresh. This is a draw-list-local optimization, not a cache across frames.

`probe_transform_descriptors.gd` renders repeated surfaces sharing a skeleton
transform descriptor, including opaque and transparent materials, alongside
MultiMesh and GPU particle geometry. Four phases replace skeleton bindings and
grow/shrink instance and particle counts through 4, 64, 2 and 32. Each phase
requires visible red opaque and blue transparent skinned geometry; matching
empty captures cannot pass. The runner also requires each phase's image to
change, checks finite HDR output and compares reference/candidate HDR channels
with an absolute tolerance of 0.0005. Both Safe and Separate rendering run with
Vulkan synchronization validation. Adapter text is supplied by the caller.

For example, from the engine repository, with a Python runtime available:

```powershell
python misc/scripts/run_transform_descriptors.py `
  --reference build/reference/godot.windows.editor.x86_64.exe `
  --candidate build/candidate/godot.windows.editor.x86_64.exe `
  --validation-layer sdk/validation/Bin `
  --expected-gpu "NVIDIA" --output captures/transform-descriptors
```

Use a fresh output directory. The runner freezes the probe source and copies
executables/DLLs into isolated runtime directories so adjacent application PCKs
cannot affect the fixture. It supports release templates with command-line path
overrides disabled by registering the fixture's main loop in an adjacent minimal
project. Reports retain executable/runtime hashes and all HDR comparisons.

The local qualification run passes all eight comparisons byte for byte, with
successful process exits and no reported runtime errors, Vulkan validation
errors or exit leaks. This is correctness evidence for the exercised raster
paths. It is not a game FPS measurement, a complete RT qualification, or a claim
of universal hardware/driver compatibility. The additional Forward+ timestamp
markers separate shadow list preparation, instance uploads and draw submission
when timestamp capture is enabled; profiling overhead must remain separate from
release performance acceptance.
