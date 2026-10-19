"""Run an asset script with NVIDIA Cycles rendering when available.

Blender: --background --factory-startup --python models/nvidia_render.py
         -- models/<category>/<asset>/preview.py [script arguments]
Eevee renders on the graphics device; Cycles prefers NVIDIA OptiX, then CUDA.
"""
import runpy
import sys
from pathlib import Path
import bpy
from bpy.app.handlers import persistent

_reported = set()
_devices = None
_backend = None

@persistent
def configure_gpu(scene):
    global _devices, _backend
    prefs = bpy.context.preferences.addons['cycles'].preferences
    if _devices is None:
        _devices = []
        for candidate in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = candidate
                _devices = [d for d in prefs.get_devices_for_type(candidate)
                            if d.type == candidate]
                if _devices:
                    _backend = candidate
                    break
            except (TypeError, RuntimeError):
                continue
        for device in prefs.devices: device.use = device in _devices
    devices, backend = _devices, _backend
    if devices:
        scene.cycles.device = 'GPU'
        if backend == 'OPTIX': scene.cycles.denoiser = 'OPTIX'
    scene.render.use_persistent_data = True
    if scene.render.engine == 'CYCLES' and scene.render.engine not in _reported:
        print('[render GPU]', backend if devices else 'CPU', [d.name for d in devices], flush=True)
        _reported.add(scene.render.engine)

@persistent
def report_graphics_device(scene):
    if scene.render.engine != 'CYCLES' and scene.render.engine not in _reported:
        import gpu
        try:
            renderer = gpu.platform.renderer_get()
        except SystemError:
            return  # background context has not been initialized yet
        print('[render GPU]', scene.render.engine, renderer, flush=True)
        _reported.add(scene.render.engine)

if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    script = Path(args[0]).resolve()
    sys.argv = [sys.argv[0], '--', *args[1:]]
    bpy.app.handlers.render_pre.append(configure_gpu)
    bpy.app.handlers.render_post.append(report_graphics_device)
    runpy.run_path(str(script), run_name='__main__')
