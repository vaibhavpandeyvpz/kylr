class_name ArenaMix
extends RefCounted
static var room: AudioEffectReverb
static var dynamics: AudioEffectCompressor

static func ensure_bus(name: String, send := "Master") -> int:
	var index := AudioServer.get_bus_index(name)
	if index<0:
		AudioServer.add_bus()
		index=AudioServer.bus_count-1
		AudioServer.set_bus_name(index,name)
	AudioServer.set_bus_send(index,send)
	return index

static func configure(reduced_range := false):
	for bus in ["Effects","Music","Interface","Announcer"]: ensure_bus(bus)
	for bus in ["World","Local","Critical","Voices"]: ensure_bus(bus,"Effects")
	ensure_bus("Ambience","World")
	if room==null:
		room=AudioEffectReverb.new()
		room.wet=0.04
		room.dry=1
		room.room_size=0.7
		AudioServer.add_bus_effect(AudioServer.get_bus_index("World"),room)
		dynamics=AudioEffectCompressor.new()
		AudioServer.add_bus_effect(AudioServer.get_bus_index("Effects"),dynamics)
		var music_duck := AudioEffectCompressor.new()
		music_duck.sidechain="Critical"
		music_duck.threshold=-26
		music_duck.ratio=6
		music_duck.attack_us=5000
		music_duck.release_ms=250
		AudioServer.add_bus_effect(AudioServer.get_bus_index("Music"),music_duck)
		# Speech ducks the bed for the recording's actual duration, including barks.
		for speech_bus in ["Announcer","Voices"]:
			var speech_duck := music_duck.duplicate() as AudioEffectCompressor
			speech_duck.sidechain=speech_bus
			AudioServer.add_bus_effect(AudioServer.get_bus_index("Music"),speech_duck)
		var limiter := AudioEffectLimiter.new()
		limiter.ceiling_db=-1.0
		AudioServer.add_bus_effect(0,limiter)
	dynamics.threshold=-24 if reduced_range else -12
	dynamics.ratio=4 if reduced_range else 2
	dynamics.gain=6 if reduced_range else 0
	dynamics.attack_us=3000
	dynamics.release_ms=180
