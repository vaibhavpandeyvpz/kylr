class_name ArenaVoice
extends Node
var player
var local := false
var ambience := false
var speech := false
var active := false
var cue_id := ""
var serial := 0
var loop_key := ""
var profile: Dictionary
var priority := 0.0
var point := Vector3.ZERO
var emitter: WeakRef
var emitter_offset := Vector3.ZERO

var age := 0.0
var delay := 0.0
var pending := false
var releasing := false
var envelope := 1.0
var occlusion := 0.0
var target_occlusion := 0.0
var low_transmission := 1.0
var high_transmission := 1.0
var target_low_transmission := 1.0
var target_high_transmission := 1.0
var filter: AudioEffectLowPassFilter
var bus_name := ""
var bus_slot := 0

func follow(source: Node3D, origin: Vector3):
	emitter = weakref(source)
	emitter_offset = source.to_local(origin)

func update_emitter():
	if emitter == null: return
	var source = emitter.get_ref()
	if is_instance_valid(source) and source.is_inside_tree():
		point = source.eye() if source is ArenaRobot else source.to_global(emitter_offset)
	else:
		emitter = null

func configure(index: int,near_field: bool,ambient_field := false,speech_field := false):
	local=near_field
	ambience=ambient_field
	speech=speech_field
	bus_slot=index
	player=AudioStreamPlayer.new() if local else AudioStreamPlayer3D.new()
	add_child(player)
	player.finished.connect(stop)
	if not local:
		bus_name=ArenaMix.voice_bus(index,ambience,speech,"Ambience" if ambience else "Voices" if speech else "World")
		filter=AudioServer.get_bus_effect(AudioServer.get_bus_index(bus_name),0)
		player.attenuation_filter_cutoff_hz=20500
		player.attenuation_model=AudioStreamPlayer3D.ATTENUATION_DISABLED
		player.max_db=0
		player.max_distance=0
		player.doppler_tracking=AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED

func start(id: String,stream: AudioStream,settings: Dictionary,position: Vector3,importance: float,propagation_delay: float,pitch: float,key := "",distance := 0.0):
	stop()
	serial += 1
	cue_id=id
	loop_key=key
	profile=settings
	point=position
	priority=importance
	active=true
	releasing=false
	age=0
	occlusion=0
	target_occlusion=0
	low_transmission=1.0
	high_transmission=1.0
	target_low_transmission=1.0
	target_high_transmission=1.0
	envelope=0.0 if key!="" else 1.0
	player.stream=stream
	player.pitch_scale=pitch
	if local:
		player.bus=settings.bus if settings.bus!="World" else "Local"
	else:
		var route: String=settings.bus if settings.bus in ["Ambience","Voices","Announcer","Critical"] else "World"
		bus_name=ArenaMix.voice_bus(bus_slot,ambience,speech,route)
		filter=AudioServer.get_bus_effect(AudioServer.get_bus_index(bus_name),0)
		player.bus=bus_name
		player.global_position=point
		filter.cutoff_hz=18000
	player.volume_db=level_db(distance,0.0)
	delay=propagation_delay
	pending=delay>0
	if not pending: player.play()

func update(dt: float,duck: float,distance := 0.0):
	if not active: return
	age+=dt
	if pending:
		delay-=dt
		if delay<=0:
			pending=false
			player.play()
	envelope=move_toward(envelope,0.0 if releasing else 1.0,dt/0.06)
	if releasing and envelope<=0: stop(); return
	var blend := 1-exp(-dt*8)
	occlusion=lerpf(occlusion,target_occlusion,blend)
	low_transmission=lerpf(low_transmission,target_low_transmission,blend)
	high_transmission=lerpf(high_transmission,target_high_transmission,blend)
	if not local:
		player.global_position=point
		var spectral_ratio := clampf(high_transmission/maxf(low_transmission,0.01),0.05,1.0)
		filter.cutoff_hz=18000.0*pow(spectral_ratio,1.5)
	player.volume_db=level_db(distance,duck)

func level_db(distance: float, duck: float) -> float:
	var distance_db := 0.0 if local else AudioCues.distance_attenuation_db(profile,distance)
	return float(profile.gain)+float(profile.get("playback_gain",AudioCues.PLAYBACK_GAIN_DB))+distance_db+linear_to_db(maxf(low_transmission,0.01))+linear_to_db(maxf(envelope,0.001))+duck

func stop():
	emitter=null
	active=false
	pending=false
	loop_key=""
	if player:
		player.stop()
		player.stream=null

func _exit_tree(): stop()
