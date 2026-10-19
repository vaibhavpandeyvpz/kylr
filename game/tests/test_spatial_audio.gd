extends GutTest
var audio: ArenaAudio

class ListenerFixture extends Node3D:
	var listener := Node3D.new()
	func _ready(): add_child(listener)

class MapFixture extends RefCounted:
	var play_transform := Transform3D.IDENTITY
	var config := {"audio_zones":[]}

class WorldFixture extends Node3D:
	var phase := "Active"
	var robots: Array = []
	var local_robot := ListenerFixture.new()
	var map := MapFixture.new()
	var audio: ArenaAudio
	func _ready(): add_child(local_robot)

class RepairMapProbe extends ArenaMap:
	func repair_geometry_valid(_fixture: Dictionary) -> bool: return true
	func repair_contains(_fixture: Dictionary, _robot) -> bool: return true

func before_each():
	audio=ArenaAudio.new()
	add_child(audio)

func after_each():
	audio.free()
	await wait_seconds(0.12)

func test_priority_stealing_reserves_local_capacity_and_culls_far_sources():
	var quiet := AudioCues.profile("walk")
	quiet.priority=10
	quiet.limit=32
	for index in SpatialAudioDirector.WORLD_LIMIT:
		assert_true(audio.play_cue("bed_"+str(index),Vector3(0,0,-10),false,quiet))
	assert_eq(audio.active_count(),SpatialAudioDirector.WORLD_LIMIT)
	assert_true(audio.cue("low_energy",Vector3.ZERO,true))
	assert_eq(audio.active_count(),SpatialAudioDirector.WORLD_LIMIT+1)
	assert_true(audio.cue("rifle",Vector3(0,0,-4)))
	assert_eq(audio.metrics.stolen,1)
	assert_false(audio.cue("walk",Vector3(0,0,-100)))
	assert_lte(audio.voices.size(),SpatialAudioDirector.WORLD_LIMIT+SpatialAudioDirector.LOCAL_LIMIT)

func test_world_distance_uses_one_smooth_attenuation_curve():
	var profile := AudioCues.profile("rifle")
	var near_distance: float = profile.near
	var far_distance: float = profile.far
	assert_eq(AudioCues.distance_attenuation_db(profile,near_distance),0.0)
	assert_almost_eq(AudioCues.distance_attenuation_db(profile,(near_distance+far_distance)*0.5),-15.0,0.001)
	assert_eq(AudioCues.distance_attenuation_db(profile,far_distance),AudioCues.FAR_ATTENUATION_DB)
	assert_true(audio.play_cue("rifle",Vector3(0,0,-near_distance),false,profile))
	var voice: ArenaVoice = audio.last_started_voice
	assert_eq(voice.player.attenuation_model,AudioStreamPlayer3D.ATTENUATION_DISABLED)
	assert_eq(voice.player.max_distance,0.0)
	var near_level: float = voice.player.volume_db
	voice.update(0.1,0.0,(near_distance+far_distance)*0.5)
	assert_almost_eq(voice.player.volume_db,near_level-15.0,0.001)
	voice.target_occlusion=1.0
	voice.target_low_transmission=0.48
	voice.target_high_transmission=0.16
	voice.update(0.5,0.0,near_distance)
	assert_lt(voice.filter.cutoff_hz,5000.0)
	assert_gt(voice.player.volume_db,near_level-7.0)

func test_all_weapon_shots_and_impacts_use_unity_source_gain_before_spatial_attenuation():
	AudioCues.profile("pistol")
	for id in AudioCues.profiles:
		var profile := AudioCues.profile(id)
		if not String(profile.asset).begins_with("weapons/"): continue
		assert_eq(profile.gain, 0.0, id + " has no extra gain reduction")
		assert_eq(profile.playback_gain, 0.0, id + " has no hidden boost")
		assert_true(audio.play_cue(id, Vector3.ZERO, false, profile))
		var voice := audio.last_started_voice
		assert_almost_eq(voice.player.volume_db, 0.0, 0.001, id + " retains source level nearby")
		voice.update(0.1, 0.0, profile.far)
		assert_almost_eq(voice.player.volume_db, AudioCues.FAR_ATTENUATION_DB, 0.001, "Distance still controls level")
		voice.stop()

func test_machinery_beds_keep_their_voices_during_combat():
	var ambience := AudioCues.profile("thruster_bed")
	for index in SpatialAudioDirector.AMBIENCE_LIMIT:
		assert_true(audio.play_cue("thruster_bed",Vector3(index,0,-10),false,ambience,"thruster_"+str(index)))
	var ambience_voices := audio.voices.duplicate()
	var quiet := AudioCues.profile("walk")
	quiet.priority=10
	quiet.limit=SpatialAudioDirector.WORLD_LIMIT
	for index in SpatialAudioDirector.WORLD_LIMIT:
		assert_true(audio.play_cue("world_"+str(index),Vector3(0,0,-10),false,quiet))
	assert_true(audio.cue("rifle",Vector3(0,0,-4)))
	for voice in ambience_voices:
		assert_true(voice.active)
		assert_true(voice.ambience)
	assert_eq(audio.metrics.stolen,1)

func test_reduced_dynamic_range_restores_quiet_detail():
	ArenaMix.configure(true)
	assert_eq(ArenaMix.dynamics.gain,6.0)
	ArenaMix.configure(false)
	assert_eq(ArenaMix.dynamics.gain,0.0)

func test_cooldowns_are_per_emitter_and_loops_release_without_restarting():
	var a := Node3D.new()
	var b := Node3D.new()
	add_child_autofree(a)
	add_child_autofree(b)
	assert_true(audio.cue("pistol",Vector3.ZERO,false,a))
	assert_false(audio.cue("pistol",Vector3.ZERO,false,a))
	assert_true(audio.cue("pistol",Vector3.ZERO,false,b))
	audio.set_loop("beam","lightning_gun",Vector3.ZERO,true)
	var voice: ArenaVoice=audio.loops.beam
	assert_eq(audio.events[-1].asset,"weapons/shots/lightning_gun_primary")
	var starts: int=audio.metrics.started
	audio.set_loop("beam","lightning_gun",Vector3(1,0,0),true)
	assert_eq(audio.metrics.started,starts)
	assert_eq(voice.point,Vector3(1,0,0))
	assert_eq(voice.player.stream.loop_mode,AudioStreamWAV.LOOP_FORWARD)
	audio.set_loop("beam","lightning_gun",Vector3.ZERO,false)
	voice.update(0.1,0)
	assert_false(voice.active)
	assert_false(audio.loops.has("beam"))

func test_curated_walk_loop_tracks_gait_speed_and_stops_without_ground_travel():
	for id in ["walk", "land", "jump_pad_launch", "barricade_open", "barricade_close", "portal_enter", "portal_exit", "pickup_item", "pickup_weapon", "pickup_ammo", "reload", "repair_weld", "repair_start_stop", "repair_ready", "thruster_bed", "interface"]:
		var path: String = "res://assets/audio/" + AudioCues.profile(id).asset + ".wav"
		assert_true(ResourceLoader.exists(path), id + " uses a packaged curated clip")
	var point := Vector3.ZERO
	for gait in [1.0, ArenaTuning.RUN_MULTIPLIER, ArenaTuning.SPRINT_MULTIPLIER]:
		audio.set_loop("walker", "walk", point, true, true, gait)
		assert_almost_eq(audio.loops.walker.player.pitch_scale, gait, 0.001)
	audio.set_loop("walker", "walk", point, false)
	assert_false(audio.loops.has("walker"))

func test_barricade_uses_distinct_open_and_close_cues():
	var world := WorldFixture.new()
	add_child_autofree(world)
	world.audio=audio
	audio.game=world
	var arena := ArenaMap.new()
	autofree(arena)
	arena.game=world
	var node := Node3D.new()
	add_child_autofree(node)
	var fixture := {"node":node,"point":Vector3(3,0,4),"open":false,"elapsed":2.0}
	arena.set_barricade(fixture,true)
	assert_true(fixture.open)
	assert_eq(audio.events[-1].id,"barricade_open")
	assert_eq(audio.events[-1].point,fixture.point)
	arena.set_barricade(fixture,false)
	assert_false(fixture.open)
	assert_eq(audio.events[-1].id,"barricade_close")
	assert_eq(audio.events[-1].point,fixture.point)

func test_repair_shield_plays_stop_recording_when_welding_ends():
	var world := WorldFixture.new()
	add_child_autofree(world)
	world.audio=audio
	audio.game=world
	var arena := RepairMapProbe.new()
	autofree(arena)
	arena.game=world
	var node := Node3D.new()
	add_child_autofree(node)
	var robot := ArenaRobot.new()
	autofree(robot)
	robot.ah=35
	var fixture := {"id":"audio_probe","node":node,"point":Vector3(3,0,4),"occupant":robot,"elapsed":5.9,"cooldown":0.0}
	world.robots.append(robot)
	robot.repair=fixture
	arena.tick_repair(fixture,0.2)
	assert_eq(audio.events[-1].id,"repair_start_stop")
	assert_eq(audio.events[-1].point,fixture.point)
	assert_eq(robot.ah,100.0)
	assert_eq(robot.ep,ArenaTuning.MAX_EP)

func test_occlusion_uses_world_collision_and_clears_when_wall_opens():
	var world := WorldFixture.new()
	add_child_autofree(world)
	audio.game=world
	var wall := StaticBody3D.new()
	world.add_child(wall)
	wall.position=Vector3(0,0,-2)
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size=Vector3(4,4,0.5)
	collider.shape=shape
	wall.add_child(collider)
	await get_tree().physics_frame
	await get_tree().physics_frame
	assert_true(audio.cue("rifle",Vector3(0,0,-4)))
	var voice := audio.voices[0]
	audio.update_acoustics()
	assert_eq(voice.target_occlusion,1.0)
	assert_almost_eq(voice.target_low_transmission,Spatio.MATERIALS.concrete.x,0.001)
	assert_almost_eq(voice.target_high_transmission,Spatio.MATERIALS.concrete.y,0.001)
	voice.update(0.1,0)
	assert_lt(voice.filter.cutoff_hz,18000.0)
	wall.set_meta("spatio_material","glass")
	audio.update_acoustics()
	assert_almost_eq(voice.target_low_transmission,Spatio.MATERIALS.glass.x,0.001)
	assert_gt(voice.target_high_transmission,Spatio.MATERIALS.concrete.y)
	wall.free()
	await get_tree().physics_frame
	audio.update_acoustics()
	assert_eq(voice.target_occlusion,0.0)
	assert_eq(voice.target_low_transmission,1.0)

func test_spatio_materials_and_ray_budget_are_bounded():
	assert_eq(Spatio.RAYS_PER_TICK % Spatio.RAYS_PER_SAMPLE,0)
	assert_eq(Spatio.material_for_name("SK_BarricadePanel","maps"),"metal")
	assert_eq(Spatio.material_for_name("GlassWall","maps"),"glass")
	assert_gt(Spatio.MATERIALS.glass.y,Spatio.MATERIALS.concrete.y)
	var world := WorldFixture.new()
	add_child_autofree(world)
	var sample := Spatio.sample(world.get_world_3d().direct_space_state,Vector3.ZERO,Vector3(0,0,-4))
	assert_eq(sample.rays,Spatio.RAYS_PER_SAMPLE)
	assert_eq(sample.low,1.0)
	assert_eq(sample.high,1.0)

func test_acoustic_ear_rays_remain_independent_and_contacts_stay_live():
	var world := WorldFixture.new()
	add_child_autofree(world)
	var wall := StaticBody3D.new()
	world.add_child(wall)
	wall.position = Vector3(0,0,-0.3)
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.15,4,0.05)
	collider.shape = shape
	wall.add_child(collider)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var space := world.get_world_3d().direct_space_state
	var sample := Spatio.sample(space,Vector3.ZERO,Vector3(0,0,-4))
	assert_eq(sample.rays,3)
	assert_almost_eq(sample.blocked,1.0/3.0,0.001,"Only the centre ear ray hits the narrow near-listener wall")
	assert_almost_eq(sample.low,(2.0+Spatio.MATERIALS.concrete.x)/3.0,0.001)
	assert_almost_eq(sample.high,(2.0+Spatio.MATERIALS.concrete.y)/3.0,0.001)
	wall.position.x = 1.0
	await get_tree().physics_frame
	sample = Spatio.sample(space,Vector3.ZERO,Vector3(0,0,-4))
	assert_eq(sample.blocked,0.0,"Moving geometry must affect the next acoustic sample")
	assert_eq(sample.low,1.0)
	assert_eq(sample.high,1.0)

func test_inline_audio_profile_does_not_duplicate_voice_or_acoustic_updates():
	var world := WorldFixture.new()
	add_child_autofree(world)
	audio.game = world
	assert_true(audio.cue("rifle",Vector3(0,0,-4)))
	var voice := audio.voices[0]
	var previous_profile := SpatialAudioDirector.profile_ticks
	var previous_costs := SpatialAudioDirector.tick_costs.duplicate()
	var previous_callbacks := SpatialAudioDirector.profile_callbacks
	var previous_samples := SpatialAudioDirector.profile_acoustic_samples
	SpatialAudioDirector.tick_costs.clear()
	SpatialAudioDirector.profile_callbacks = 0
	SpatialAudioDirector.profile_acoustic_samples = 0
	SpatialAudioDirector.profile_ticks = true
	audio.acoustic_time = 1.0
	audio._physics_process(0.01)
	assert_almost_eq(voice.age,0.01,0.0001,"The normal voice callback executes once")
	assert_eq(SpatialAudioDirector.profile_callbacks,1)
	assert_eq(SpatialAudioDirector.profile_acoustic_samples,0)
	audio.acoustic_time = 0.0
	var rays_before: int = audio.metrics.rays
	audio._physics_process(0.01)
	assert_almost_eq(voice.age,0.02,0.0001)
	assert_eq(SpatialAudioDirector.profile_callbacks,2)
	assert_eq(SpatialAudioDirector.profile_acoustic_samples,1)
	assert_eq(audio.metrics.rays-rays_before,Spatio.RAYS_PER_SAMPLE)
	assert_gte(SpatialAudioDirector.tick_costs.physics_total,SpatialAudioDirector.tick_costs.voices)
	SpatialAudioDirector.profile_ticks = previous_profile
	SpatialAudioDirector.tick_costs = previous_costs
	SpatialAudioDirector.profile_callbacks = previous_callbacks
	SpatialAudioDirector.profile_acoustic_samples = previous_samples

func test_weapon_report_and_surface_impact_have_separate_origins():
	for weapon in ["pistol","rifle","minigun","rocket_launcher","emp_gun"]:
		var shot_path: String="res://assets/audio/"+AudioCues.profile(weapon).asset+".wav"
		assert_true(ResourceLoader.exists(shot_path),weapon+" has a packaged muzzle report")
	for weapon in ["rifle","minigun","rocket_launcher","emp_gun"]:
		var hit_path: String="res://assets/audio/"+AudioCues.profile("hit_"+weapon).asset+".wav"
		assert_true(ResourceLoader.exists(hit_path),weapon+" has a packaged impact")
	for weapon in ["lightning_gun","flamethrower"]:
		for id in [weapon,"hit_"+weapon]:
			var loop_path: String="res://assets/audio/"+AudioCues.profile(id).asset+".wav"
			assert_true(ResourceLoader.exists(loop_path),id+" has a packaged continuous loop")
	assert_true(ResourceLoader.exists("res://assets/audio/weapons/hits/shield.wav"))
	var pistol_variants: Array=AudioCues.profile("hit_pistol").variants
	assert_eq(pistol_variants.size(),3)
	for variant in pistol_variants:
		var path: String="res://assets/audio/"+String(variant)+".wav"
		assert_true(ResourceLoader.exists(path))
		assert_lt((load(path) as AudioStream).get_length(),0.8)
	var world := WorldFixture.new()
	add_child_autofree(world)
	world.audio=audio
	audio.game=world
	var shooter := Node3D.new()
	var surface := StaticBody3D.new()
	world.add_child(shooter)
	world.add_child(surface)
	var muzzle := Vector3(1,1,-2)
	var collision := Vector3(-4,2,-9)
	assert_true(audio.cue("rifle",muzzle,true,shooter))
	var combat := ArenaCombat.new(world)
	combat.play_impact("rifle",collision,surface,false,shooter)
	assert_eq(audio.events.size(),2)
	assert_eq(audio.events[0].point,muzzle)
	assert_eq(audio.events[1].point,collision)
	assert_eq(audio.events[1].id,"hit_rifle")
	assert_eq(audio.events[1].asset,"weapons/hits/rifle")
	assert_true(audio.voices[0].local)
	assert_false(audio.voices[1].local)
	assert_eq(audio.voices[1].point,collision)
	var victim := ArenaRobot.new()
	autofree(victim)
	victim.protection=0
	var armor_point := Vector3(-3,1,-7)
	var shield_point := Vector3(-2,1,-6)
	combat.play_impact("rifle",armor_point,victim,false,shooter)
	audio.clock += 0.1
	victim.sh=100
	combat.play_impact("rifle",shield_point,victim,true,shooter)
	assert_eq(audio.events[2].id,"hit_rifle")
	assert_eq(audio.events[2].point,armor_point)
	assert_eq(audio.events[3].id,"hit_rifle")
	assert_eq(audio.events[3].point,shield_point)
	victim.protection=1
	combat.play_impact("rifle",shield_point,victim,true,shooter)
	assert_eq(audio.events[4].id,"hit_shield")
	assert_eq(audio.events[4].asset,"weapons/hits/shield")
	var second_shooter := Node3D.new()
	world.add_child(second_shooter)
	combat.play_impact("rifle",Vector3(5,1,-9),surface,false,second_shooter)
	assert_eq(audio.events.size(),6,"Separate shooters can strike one large map surface in the same tick")
	combat.play_impact("rocket_launcher",Vector3(5,1,-10),surface,false,second_shooter)
	assert_eq(audio.events[-1].id,"hit_rocket_launcher")

func test_orb_secondary_audio_is_discrete_and_uses_separate_shot_and_hit_sources():
	var world := WorldFixture.new()
	add_child_autofree(world)
	world.audio = audio
	audio.game = world
	var shooter := Node3D.new()
	var surface := StaticBody3D.new()
	world.add_child(shooter)
	world.add_child(surface)
	var combat := ArenaCombat.new(world)
	for weapon in ["flamethrower", "lightning_gun"]:
		var cue := Arsenal.shot_cue(weapon, true)
		assert_true(audio.cue(cue, Vector3.ZERO, true, shooter))
		assert_eq(audio.events[-1].asset, "weapons/shots/" + weapon + "_secondary")
		assert_eq(audio.events[-1].loop_key, "")
		combat.play_impact(weapon, Vector3(0, 0, -3), surface, false, shooter, true)
		assert_eq(audio.events[-1].id, "hit_" + weapon + "_secondary")
		assert_eq(audio.events[-1].asset, "weapons/hits/" + weapon + "_secondary")
		assert_eq(audio.events[-1].point, Vector3(0, 0, -3))
		assert_eq(audio.loops.size(), 0)
		for id in [cue, "hit_" + weapon + "_secondary"]:
			assert_false(AudioCues.profile(id).loop)
			var stream := audio.resolve_stream(AudioCues.profile(id).asset, false) as AudioStreamWAV
			assert_not_null(stream)
			assert_eq(stream.mix_rate, 48000)
			assert_false(stream.stereo)
			assert_eq(stream.loop_mode, AudioStreamWAV.LOOP_DISABLED)

func test_continuous_contacts_follow_target_and_go_silent_on_invulnerability():
	var world := WorldFixture.new()
	add_child_autofree(world)
	world.audio=audio
	audio.game=world
	var combat := ArenaCombat.new(world)
	var shooter := ArenaRobot.new()
	var victim := ArenaRobot.new()
	autofree(shooter)
	autofree(victim)
	shooter.robot_id=7
	victim.protection=0
	for weapon in ["lightning_gun","flamethrower"]:
		shooter.equipped=weapon
		var point := Vector3(2,1,-4)
		combat.update_contact(shooter,{"collider":victim,"position":point})
		var key := "contact_7"
		assert_true(audio.loops.has(key))
		assert_eq(audio.events[-1].asset,"weapons/hits/"+weapon+"_primary")
		assert_eq(audio.loops[key].point,point)
		victim.protection=1
		combat.update_contact(shooter,{"collider":victim,"position":point})
		assert_false(audio.loops.has(key))
		var count := audio.events.size()
		combat.play_impact(weapon,point,victim,true,shooter)
		assert_eq(audio.events.size(),count,"Protected targets make no continuous hit or shield sound")
		victim.protection=0
		combat.update_contact(shooter,{"collider":victim,"position":point})
		combat.update_contact(shooter,{})
		assert_false(audio.loops.has(key))

func test_rocket_impact_stops_only_its_matching_launch_report():
	assert_true(audio.cue("rocket_launcher",Vector3.ZERO,true))
	var first: ArenaVoice=audio.last_started_voice
	var projectile := ArenaProjectile.new()
	autofree(projectile)
	projectile.launch_voice=weakref(first)
	projectile.launch_voice_serial=first.serial
	projectile.stop_launch_report()
	assert_false(first.active)
	audio.clock += 0.1
	assert_true(audio.cue("rocket_launcher",Vector3.ZERO,true))
	var second: ArenaVoice=audio.last_started_voice
	assert_eq(first,second,"The voice pool may reuse a finished launch voice")
	projectile.stop_launch_report()
	assert_true(second.active,"A recycled voice belongs to a different shot")
