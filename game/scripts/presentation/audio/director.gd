class_name SpatialAudioDirector
extends Node
const WORLD_LIMIT := 24
const LOCAL_LIMIT := 8
const AMBIENCE_LIMIT := 9
const SPEECH_LIMIT := 10
static var profile_ticks := false
static var tick_costs: Dictionary = {}
static var profile_callbacks := 0
static var profile_acoustic_samples := 0

static func record_profile(stage: String, elapsed: int) -> void:
	tick_costs[stage] = int(tick_costs.get(stage,0)) + elapsed

var game
var voices: Array[ArenaVoice] = []
var streams: Dictionary = {}
var loops: Dictionary = {}
var loop_retry: Dictionary = {}
var last: Dictionary = {}
var clock := 0.0
var acoustic_cursor := 0
var acoustic_time := 0.0
var critical_hold := 0.0
var events: Array = []
var last_started_voice: ArenaVoice
var metrics := {"started":0,"culled":0,"stolen":0,"rays":0,"peak":0,"peak_db":-80.0}

func _ready():
	if ArenaMix.room==null: ArenaMix.configure()

func listener_position() -> Vector3:
	if is_instance_valid(game) and is_instance_valid(game.local_robot) and is_instance_valid(game.local_robot.listener) and game.local_robot.listener.is_inside_tree(): return game.local_robot.listener.global_position
	return Vector3.ZERO

func cue(id: String,point := Vector3.ZERO,local := false,emitter: Node3D = null) -> bool:
	if game is ArenaMatch and game.replicating and game.authority:
		# Discrete muzzle reports already follow replicated shot counters.
		if not Arsenal.WEAPONS.has(id) and id not in ["lightning_gun_secondary", "flamethrower_secondary"]:
			game.present({"kind":"audio","cue":id,"point":point,"near":local,"emitter":emitter.robot_id if emitter is ArenaRobot else -1})
		return false
	var profile := AudioCues.profile(id)
	var identity := str(emitter.get_instance_id()) if emitter!=null else str(point.snapped(Vector3.ONE))
	var key := id+":"+identity+":"+str(local)
	if clock-float(last.get(key,-1000))<float(profile.cooldown): return false
	last[key]=clock
	return play_cue(id,point,local,profile)

func cue_following(id: String, point: Vector3, emitter: Node3D) -> bool:
	if not is_instance_valid(emitter) or not cue(id,point,false,emitter): return false
	last_started_voice.follow(emitter,point)
	return true

func play_cue(id: String,point: Vector3,local: bool,profile: Dictionary,key := "") -> bool:
	var distance := listener_position().distance_to(point)
	if not local and distance>=float(profile.far): metrics.culled+=1; return false
	var importance := AudioCues.importance(profile,distance,local)
	var voice := acquire(local,id,int(profile.limit),importance,profile.bus=="Ambience",profile.bus=="Voices")
	if voice==null: metrics.culled+=1; return false
	var asset: String=profile.get("loop_asset",profile.asset) if key!="" else profile.asset
	if key=="" and profile.has("variants"):
		var variants: Array=profile.variants
		asset=String(variants[randi() % variants.size()])
	var stream := resolve_stream(asset,key!="")
	if stream==null: return false
	var pitch := float(profile.get("pitch_scale",1.0))*randf_range(1-float(profile.pitch),1+float(profile.pitch))
	voice.start(id,stream,profile,point,importance,0.0 if local or key!="" else minf(distance/343.0,0.25),pitch,key,distance)
	last_started_voice=voice
	if key!="": loops[key]=voice
	if profile.bus=="Critical": critical_hold=0.6
	metrics.started+=1
	metrics.peak=maxi(metrics.peak,active_count())
	events.append({"kind":"start","time":clock,"id":id,"asset":asset,"point":point,"distance":distance,"gain":profile.gain,"loop_key":key})
	return true

func acquire(local: bool,id: String,limit: int,importance: float,ambience := false,speech := false) -> ArenaVoice:
	var matching: Array[ArenaVoice]=[]
	var candidates: Array[ArenaVoice]=[]
	var free: ArenaVoice
	for voice in voices:
		if voice.local!=local or voice.speech!=speech or (not local and voice.ambience!=ambience): continue
		candidates.append(voice)
		if not voice.active: free=voice
		elif voice.cue_id==id: matching.append(voice)
	if matching.size()>=limit: candidates=matching; free=null
	elif free!=null: return free
	elif candidates.size()<(SPEECH_LIMIT if speech else LOCAL_LIMIT if local else AMBIENCE_LIMIT if ambience else WORLD_LIMIT):
		var voice := ArenaVoice.new()
		add_child(voice)
		voice.configure(voices.size(),local,ambience,speech)
		voices.append(voice)
		return voice
	var weakest: ArenaVoice
	for voice in candidates:
		if weakest==null or voice.priority<weakest.priority or (is_equal_approx(voice.priority,weakest.priority) and voice.age>weakest.age): weakest=voice
	if weakest==null or importance<weakest.priority: return null
	if weakest.loop_key!="": loops.erase(weakest.loop_key)
	weakest.stop()
	metrics.stolen+=1
	return weakest

func set_loop(key: String,id: String,point: Vector3,enabled: bool,local := false,playback_speed := 1.0):
	if game is ArenaMatch and game.replicating and game.authority: return
	if loops.has(key):
		var voice: ArenaVoice=loops[key]
		if not voice.active or not enabled or voice.cue_id!=id:
			events.append({"kind":"stop","time":clock,"loop_key":key})
			voice.releasing=true
			loops.erase(key)
		else:
			voice.point=point
			voice.player.pitch_scale=playback_speed
			return
	if not enabled:
		loop_retry.erase(key)
		return
	if clock<float(loop_retry.get(key,-1)): return
	if not play_cue(id,point,local,AudioCues.profile(id),key): loop_retry[key]=clock+0.25
	else:
		loops[key].player.pitch_scale=playback_speed
		loop_retry.erase(key)

func resolve_stream(id: String,looping: bool) -> AudioStream:
	var key := id+("/loop" if looping else "")
	if streams.has(key): return streams[key]
	var path := "res://assets/audio/"+id+".wav"
	var stream: AudioStream=load(path) if ResourceLoader.exists(path) else fallback(id)
	if looping and stream is AudioStreamWAV:
		stream=stream.duplicate()
		stream.loop_mode=AudioStreamWAV.LOOP_FORWARD
		stream.loop_begin=0
		stream.loop_end=int(stream.get_length()*stream.mix_rate)
	streams[key]=stream
	return stream

func fallback(_id: String) -> AudioStream: return null

func active_count() -> int:
	var count := 0
	for voice in voices:
		if voice.active: count+=1
	return count

func _physics_process(dt):
	var started := Time.get_ticks_usec() if profile_ticks else 0
	clock+=dt
	critical_hold=maxf(0,critical_hold-dt)
	var listener := listener_position()
	for voice in voices:
		if not voice.active: continue
		voice.update_emitter()
		var distance := listener.distance_to(voice.point)
		voice.priority=AudioCues.importance(voice.profile,distance,voice.local)
		if not voice.local and distance>=float(voice.profile.far):
			if voice.loop_key!="": loops.erase(voice.loop_key)
			voice.releasing=true
		var duck := -5.0 if critical_hold>0 and not voice.local else 0.0
		voice.update(dt,duck,distance)
	if profile_ticks:
		record_profile("voices", Time.get_ticks_usec()-started)
	metrics.peak_db=maxf(metrics.peak_db,maxf(AudioServer.get_bus_peak_volume_left_db(0,0),AudioServer.get_bus_peak_volume_right_db(0,0)))
	while not events.is_empty() and clock-events[0].time>6: events.pop_front()
	acoustic_time-=dt
	if acoustic_time<=0:
		acoustic_time=0.05
		update_acoustics()
	if profile_ticks:
		record_profile("physics_total", Time.get_ticks_usec()-started)
		profile_callbacks += 1

func update_acoustics():
	if game==null or game.local_robot==null: return
	var started := Time.get_ticks_usec() if profile_ticks else 0
	var listener := listener_position()
	var rays := 0
	var space: PhysicsDirectSpaceState3D = game.get_world_3d().direct_space_state
	for attempt in voices.size():
		if rays+Spatio.RAYS_PER_SAMPLE>Spatio.RAYS_PER_TICK: break
		acoustic_cursor=(acoustic_cursor+1)%voices.size()
		var voice := voices[acoustic_cursor]
		if not voice.active or voice.local: continue
		var acoustics := Spatio.sample(space,listener,voice.point)
		voice.target_occlusion=acoustics.blocked
		voice.target_low_transmission=acoustics.low
		voice.target_high_transmission=acoustics.high
		rays+=acoustics.rays
	metrics.rays+=rays
	var wet := 0.04
	var room_size := 0.7
	var local_point: Vector3=game.map.play_transform.affine_inverse()*listener
	for zone in game.map.config.get("audio_zones",[]):
		var bounds := AABB(MapCatalog.vector(zone.min),MapCatalog.vector(zone.max)-MapCatalog.vector(zone.min))
		if bounds.has_point(local_point): wet=zone.wet; room_size=zone.room_size
	ArenaMix.room.wet=lerpf(ArenaMix.room.wet,wet,0.15)
	ArenaMix.room.room_size=lerpf(ArenaMix.room.room_size,room_size,0.15)
	if profile_ticks:
		record_profile("acoustics", Time.get_ticks_usec()-started)
		profile_acoustic_samples += 1

func _exit_tree():
	for voice in voices: voice.stop()
	loops.clear()
	loop_retry.clear()
	streams.clear()
