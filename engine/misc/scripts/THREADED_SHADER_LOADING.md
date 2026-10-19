# Threaded shader loading regression

Resource loaders can exhaust the general worker pool while holding shader-version
locks and waiting for compilation queued in that same pool. ShaderRD compilation
uses an independent named pool so those dependencies can progress. Named pools
also leave script languages before language shutdown.

Create a temporary project using Forward+, with
`threading/worker_pool/max_threads=1` and
`rendering/shader_compiler/shader_cache/enabled=false`. Keep shader caching disabled
for verification so a previous compilation cannot conceal the dependency cycle.

Run the editor with this project's `--path` and the absolute path to
`run_threaded_shader_loading.gd` as `--script`. First prepare the binary resources
headlessly with `-- --prepare --directory=<absolute fixture directory>`. Then run
graphically with `-- --directory=<same directory>`. Use an external timeout because
the regression can block the main thread, preventing a script timer from firing.

The node-based `probe_threaded_shader_loading.gd` can also be the script on a main
scene in a release PCK. This avoids enabling unsafe CLI path overrides in release
templates. Include an empty `.godot/global_script_class_cache.cfg` (`list=[]`) in a
minimal fixture package. Prepare and pack the same 16 meshes for both executables.

The standalone before/after fixture reproduced a 40-second timeout on the earlier
binary and completed in about 5.2 seconds on the fixed build, with Vulkan validation,
unchanged inputs and a clean exit. These timings describe this loading fixture;
they do not establish general startup speed, visual quality or game FPS.
