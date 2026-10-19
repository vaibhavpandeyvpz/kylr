# Concurrent audio bus routing

`AudioServer::set_bus_send` must hold the audio driver lock while changing the
send name. The mixer holds that lock while looking up the target bus. Without
it, the name can change between the map membership check and access, inserting
a null bus pointer and crashing `_mix_step` when it reads `index_cache`.
The sample-driver callback stays outside the lock, matching other bus setters.

Run the generic silent-PCM stress case with a threaded Dummy driver:

```sh
python misc/scripts/run_audio_bus_routes.py --engine /absolute/path/to/godot --output /fresh/evidence/directory --driver Dummy --seconds 20
```

On Windows, repeat with `--driver WASAPI`. The fixture alternates between a
valid bus and a nonexistent target, exercising the mixer's Master fallback.
It checks routing count, observed mixer progress, restoration of bus count,
exit status, error/leak logs and unchanged executable/probe hashes. Generated
audio samples are all zero. This does not qualify audible output or FPS.

On Windows x86-64, the unmodified reference crashed with access violation in
0.75 seconds using Dummy, without a graphical renderer. The synchronized build
passed two Dummy runs and one WASAPI run, each lasting 15 seconds and changing
routes 4,452,352 times. Active-playback and queued-stop early-exit probes also
passed. This establishes a regression fix for the routing race, not a solution
to unrelated presentation stalls or universal platform qualification.
