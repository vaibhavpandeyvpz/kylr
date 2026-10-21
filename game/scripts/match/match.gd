class_name ArenaMatch
extends Node3D
signal message(text: String)
signal completed
signal damage_taken(source: Vector3, amount: float)
signal local_elimination(event: Dictionary)

const KILL_CHAIN_WINDOW := 10.0
const KILL_ACCOLADES := {2:"Double Kill",3:"Triple Kill",4:"Mega Kill",5:"Champion",6:"Death Bringer"}
var kill_chains: Dictionary = {}
var match_type := "DM"
var map_id := "skyfall"
var gravity_multiplier_override := 0.0
var gravity_multiplier := 1.0
var gravity := ArenaTuning.GRAVITY
var difficulty := 1
var bot_roles: BotTeamRoles
var count := 10
var goal := 25
var time_limit := 900.0
var phase := "Waiting"
var async_scene_loading := false
var initialization_complete := false
var loading_hold := false
var elapsed := 0.0
var countdown := 0.0
var authority := true
var online := false
var replicating := false
var local_name := "Pilot"
var local_robot
var robots: Array = []
var map: ArenaMap
var combat: ArenaCombat
var effects: ArenaEffects
var audio: ArenaAudio
var callouts: ArenaCallouts
var rng := RandomNumberGenerator.new()
var team_colors: Array[Color] = []
var team_scores := [0,0]
var team_reached := [0.0,0.0]
var flags: Array = []
var drops: Array = []
var corpses: Array = []
var death_view_remaining := 0.0
var local_death_corpse: Node3D
var local_fall_death := false
var fall_camera_stop := Vector3.INF
var camera: Camera3D
var camera_rig: ArenaCameraRig
var first_person: FirstPersonRig
var third_person := false
var hit_marker := 0.0
var feed_events: Array[Dictionary] = []
var result: Dictionary = {}
var fov := 60.0
var camera_snap := true
var on_ready: Callable
const ARENA_RISE_SECONDS := 4.0
const MAP_ASSEMBLY_START_SECONDS := 2.0
const MAP_ASSEMBLY_SECONDS := 5.0
const SPAWN_REVEAL_SECONDS := 4.0
const OPENING_SECONDS := 5.0
var map_assembly_started := false
var map_assembly_finished := false
var loadout_started := false
var spawn_reveal_started := false
var reduced_motion := false
var presentation_events: Array[Dictionary] = []
var presentation_last: Dictionary = {}
var fixture_lighting_enabled := false
var fixture_shadows_enabled := true

func _enter_tree() -> void:
	get_tree().node_added.connect(configure_emissive_only_light)

func configure_emissive_only_light(node: Node) -> void:
	if node is Light3D and not node is DirectionalLight3D and is_ancestor_of(node):
		if node.get_meta("fixture_light",false):
			FixtureLighting.configure(node,fixture_lighting_enabled,fixture_shadows_enabled)
			return
		# Retain pack animation targets, but only the global key illuminates geometry.
		node.light_cull_mask=0
		node.shadow_enabled=false

func present(event: Dictionary):
	if not replicating or not authority: return
	if event.kind == "damage":
		var key := "%s/%s" % [event.attacker,event.victim]
		if elapsed-float(presentation_last.get(key,-100.0)) < 0.1: return
		presentation_last[key] = elapsed
	presentation_events.append(event)
	if presentation_events.size() > 512: presentation_events.pop_front()

## Called only after an authoritative projectile contact accepts damage.
func impact_at(victim: ArenaRobot, cause: String, point: Vector3, radius := 0.0) -> void:
	if cause not in ["rocket_launcher","grenade_launcher","emp_gun"]: return
	var strength := 0.65 if cause=="emp_gun" else ImpactShake.blast_strength(point,victim.body_shape.global_position,radius)
	impact_feedback(victim.robot_id,cause,strength)

func impact_feedback(victim_id: int, cause: String, strength: float, replicated := false) -> void:
	if not is_finite(strength) or strength<=0: return
	strength=minf(strength,1.0)
	if not replicated: present({"kind":"impact_shake","victim":victim_id,"cause":cause,"strength":strength})
	if local_robot==null or local_robot.robot_id!=victim_id or camera_rig==null or reduced_motion or phase!="Active": return
	camera_rig.impact_shake.trigger(cause,strength)

static func shuffle_roster(values: Array, setup_rng: RandomNumberGenerator = null) -> void:
	if setup_rng == null:
		values.shuffle()
		return
	for index in range(values.size()-1,0,-1):
		var other := setup_rng.randi_range(0,index)
		var item = values[index]
		values[index] = values[other]
		values[other] = item

func _ready():
	configure_gravity(MapCatalog.find(map_id))
	rng.randomize()
	var setup_rng: RandomNumberGenerator = null
	if has_meta("profile_roster_seed"):
		setup_rng = RandomNumberGenerator.new()
		setup_rng.seed = int(get_meta("profile_roster_seed"))
	var colors: Array[Color] = [Color("ecb846"),Color("689649"),Color("3878b4"),Color("b74740")]
	shuffle_roster(colors,setup_rng)
	team_colors = [colors[0],colors[1]]
	combat = ArenaCombat.new(self)
	# Body-only visibility queries need only a boolean, not a result Dictionary.
	# Keep the generic combat helper's legacy default for custom/mocked ray users.
	combat.native_clear_rays = ClassDB.class_has_method("PhysicsDirectSpaceState3D", "ray_intersects")
	effects = ArenaEffects.new()
	effects.game = self
	effects.gravity = gravity
	add_child(effects)
	audio = ArenaAudio.new()
	audio.game=self
	add_child(audio)
	callouts = ArenaCallouts.new()
	callouts.game = self
	add_child(callouts)
	map = ArenaMap.new()
	map.game = self
	add_child(map)
	if not map.loading_complete: await map.scene_loaded
	camera_rig = ArenaCameraRig.new()
	add_child(camera_rig)
	camera = camera_rig.camera
	for t in 2:
		var flag := Assets.model("gameplay","ctf_flag")
		add_child(flag)
		var base := map.flag_base(t)
		var home: Vector3 = base.home
		flag.position = home
		tint_flag_cloth(flag,team_colors[t])
		flag.visible = false
		var flag_state := {"home":home,"point":home,"state":"home","carrier":-1,"node":flag,"falling":false,"fall_velocity":0.0,"capture_area":base.trigger,"base_effect":base.effect}
		flags.append(flag_state)
		var animator := Assets.find(flag,"AnimationPlayer") as AnimationPlayer
		if animator: animator.animation_finished.connect(flag_animation_finished.bind(flag_state))
	await get_tree().physics_frame
	await get_tree().physics_frame
	if not online:
		var heads_a := Arsenal.HEADS.duplicate()
		var heads_b := Arsenal.HEADS.duplicate()
		shuffle_roster(heads_a,setup_rng)
		shuffle_roster(heads_b,setup_rng)
		var names := [local_name,"Kestrel","Relay","Vector","Sable","Flux","Torque","Cipher","Helix","Rook"]
		var teams := local_roster_teams(count)
		for i in count:
			var team: int = teams[i]
			var robot = add_robot(i,names[i],team,i == 0,heads_a[i / 2] if team == 0 else heads_b[i / 2])
			robot.hide()
			robot.collision_layer = 0
			if i == 0:
				local_robot = robot
				robot.listener.make_current()
				var fp:=FirstPersonRig.new()
				first_person = fp
				fp.robot=robot
				fp.camera=camera
				add_child(fp)
			if async_scene_loading: await get_tree().process_frame
		if async_scene_loading: await begin_countdown_async()
		else: begin_countdown()
	if on_ready.is_valid(): on_ready.call()
	initialization_complete=true

func local_roster_teams(total: int) -> Array[int]:
	var offset := rng.randi_range(0,1)
	var teams: Array[int] = []
	for i in total: teams.append((i + offset) % 2)
	return teams

func configure_gravity(map_config: Dictionary) -> void:
	gravity_multiplier = maxf(0.1, gravity_multiplier_override if gravity_multiplier_override > 0.0 else float(map_config.get("gravity_multiplier", 1.0)))
	gravity = ArenaTuning.GRAVITY * gravity_multiplier

func jump_release_height(base_height: float) -> float:
	# Fixed launch impulse: weaker gravity gives a higher cutoff and coast.
	return base_height / gravity_multiplier

func tint_flag_cloth(flag: Node3D, color: Color) -> void:
	for mesh in flag.find_children("*", "MeshInstance3D", true, false):
		for surface in mesh.mesh.get_surface_count():
			var source := mesh.get_active_material(surface) as StandardMaterial3D
			if source == null or Assets.material_role(source.resource_name) != "M_Flag": continue
			var cloth := source.duplicate() as StandardMaterial3D
			cloth.albedo_color = Color(color,0.75)
			cloth.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			cloth.emission_enabled = true
			cloth.emission = color
			mesh.set_surface_override_material(surface,cloth)

func flag_animation_finished(clip: StringName, flag: Dictionary) -> void:
	var name := String(clip)
	if flag.state == "carried" and (name == "stow" or name.ends_with("/stow") or name.ends_with("|stow")):
		Assets.play(flag.node,"flutter",true)
	elif flag.state != "carried" and (name == "deploy" or name.ends_with("/deploy") or name.ends_with("|deploy")):
		Assets.play(flag.node,"wave",true)

func reset_flag_home(flag: Dictionary) -> void:
	flag.state = "home"
	flag.carrier = -1
	flag.falling = false
	flag.fall_velocity = 0.0
	var surface := SurfacePlacement.below(get_world_3d(),flag.home,map.config.fall_boundary)
	flag.point = surface.position if not surface.is_empty() else flag.home
	SurfacePlacement.ground_mount(flag.node,Assets.socket(flag.node,"GroundMount"),flag.point)
	Assets.play(flag.node,"deploy")

func drop_carried_flag(flag: Dictionary, position: Vector3, outside_play: bool) -> void:
	if outside_play:
		reset_flag_home(flag)
		if callouts: callouts.publish("Flag returned home after leaving the arena.","Announcer",flags.find(flag),true)
		return
	var surface := SurfacePlacement.below(get_world_3d(),position,map.config.fall_boundary)
	if surface.is_empty():
		reset_flag_home(flag)
		if callouts: callouts.publish("Flag returned home.","Announcer",flags.find(flag),true)
		return
	var local_point: Vector3 = map.play_transform.affine_inverse() * surface.position
	var bounds: Dictionary = map.config.navigation
	if local_point.x < bounds.min_x - 1.0 or local_point.x > bounds.max_x + 1.0 or local_point.z < bounds.min_z - 1.0 or local_point.z > bounds.max_z + 1.0:
		reset_flag_home(flag)
		if callouts: callouts.publish("Flag returned home.","Announcer",flags.find(flag),true)
		return
	flag.state = "dropped"
	flag.carrier = -1
	flag.point = surface.position
	flag.falling = true
	flag.fall_velocity = 0.0
	flag.node.global_basis = Basis.IDENTITY
	if callouts: callouts.publish("Flag dropped.","Announcer",flags.find(flag),true)

func add_robot(id: int,nick: String,team: int,human: bool,head: String,upper_body := "default"):
	var robot := ArenaRobot.new()
	robot.arena_match = self
	robot.robot_id = id
	if callouts and (not replicating or authority): callouts.assign_voice(robot)
	robot.display_name = nick
	robot.team = team
	robot.human = human
	robot.head = head
	robot.upper_body = upper_body
	robot.tint = team_colors[team] if not MatchTypes.individual(match_type) else Color.from_hsv(fmod(id * 0.17,1.0),0.45,0.65)
	add_child(robot)
	robots.append(robot)
	return robot

func begin_countdown():
	_prepare_countdown()
	# Human-only online matches do not need the bot traversal graph.
	if not online: map.build_navigation()
	_finish_countdown()

func begin_countdown_async() -> void:
	_prepare_countdown()
	if not online: await map.build_navigation_async()
	_finish_countdown()

func _prepare_countdown() -> void:
	phase = "Countdown"
	map.reset_repairs()
	countdown = 0
	map.start_assembly()
	map.start_map_assembly()
	map.assembly.seek(MAP_ASSEMBLY_SECONDS,true)
	map.assembly.pause()
	map.start_loadout()

func _finish_countdown() -> void:
	map_assembly_started = true
	map_assembly_finished = true
	loadout_started = true
	spawn_reveal_started = true
	for flag in flags:
		reset_flag_home(flag)
		flag.node.visible = match_type == "CTF"
	for robot in robots: spawn_robot(robot)

func zone_spawn_time(_team: int) -> float:
	return 0.0
func spawn_robot(robot):
	if robot.eliminated(): return
	var valid: Array = []
	for spawn in map.spawns:
		if not MatchTypes.individual(match_type) and spawn.team != robot.team: continue
		if not spawn_geometry_safe(spawn): continue
		var blocked := false
		for other in robots:
			if other != robot and other.alive and (other.position.distance_to(spawn.point) < 1.2 or (other.spawn_remaining>0 and other.spawn_fixture.point==spawn.point)): blocked = true
		if not blocked: valid.append(spawn)
	if valid.is_empty():
		robot.respawn_time = 0.25
		robot.alive = false
		return
	robot.spawn_fixture = valid[rng.randi_range(0,valid.size()-1)]
	robot.position = robot.spawn_fixture.mount.global_position
	robot.spawn_remaining = robot.spawn_fixture.get("duration", 104.0 / 30.0)
	robot.spawn_started = false
	robot.spawn_reload_remaining = 0.0
	robot.slow_remaining = 0.0
	robot.slow_multiplier = 1.0
	for status in robot.get_children():
		if status is ProjectileStatus: status.queue_free()
	if robot.brain: robot.brain.reset()
	robot.last_safe = robot.position
	robot.velocity = Vector3.ZERO
	robot.lift_target = -INF
	robot.lift_from_pad = false
	robot.ramp_stage=0;robot.ramp_time=0;robot.ramp_velocity=Vector3.ZERO
	robot.knockback_velocity = Vector3.ZERO
	robot.applied_knockback = Vector3.ZERO
	robot.movement_pose.reset()
	robot.local_motion=Vector2.ZERO
	robot.measured_speed=0
	robot.align_spawn_facing()
	robot.ah = 100
	robot.ep = ArenaTuning.MAX_EP
	robot.sh = 0
	robot.shield_time = 0
	robot.protection = 5
	robot.alive = true
	robot.crouched = false
	robot.wants_crouch = false
	robot.body_capsule.height = 1.72
	robot.body_shape.position.y = 0.86
	robot.animation_lock = 0.0
	robot.airborne_from_jump = false
	robot.airborne_time = 0.0
	robot.jump_charge = 0.0
	robot.jump_buffer = 0.0
	robot.coyote_time = 0.0
	robot.jump_release = false
	robot.jump_held = false
	robot.crouch_idle_time = 0.0
	robot.repair = null
	robot.reload_time = 0
	robot.reset_inventory()
	robot.carrying = -1
	robot.contributors.clear()
	robot.last_hit_robot_id=-1
	robot.last_hit_weapon=""
	if match_type=="GUNGAME":
		if robot.gun_game_weapon.is_empty(): advance_gun_game(robot)
		else: equip_gun_game(robot)
	else: robot.equip("pistol")
	robot.pose("idle_crouching")
	robot.hide()
	robot.body.show()
	robot.collision_layer = 2
	Assets.paint(robot.body,robot.tint,robot.armor_secondary,robot.head,false,robot.upper_body)
	if robot == local_robot: camera_snap = true

func spawn_geometry_safe(spawn: Dictionary) -> bool:
	if spawn.point.y < map.config.fall_boundary or not is_instance_valid(spawn.node) or not is_instance_valid(spawn.mount): return false
	var shape := CapsuleShape3D.new()
	shape.radius = 0.31
	shape.height = 1.72
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = shape
	query.transform = Transform3D(Basis.IDENTITY,spawn.point+Vector3.UP*0.9)
	query.collision_mask = 1
	# The authored hatch/lift is the intentional spawn envelope, while other
	# world geometry must leave standing clearance at the deck marker.
	var exclusions: Array[RID] = []
	for body in spawn.node.find_children("*","CollisionObject3D",true,false): exclusions.append(body.get_rid())
	query.exclude = exclusions
	return get_world_3d().direct_space_state.intersect_shape(query,1).is_empty()

func _physics_process(dt):
	if async_scene_loading and not initialization_complete: return
	if not authority: return
	if replicating and phase == "Countdown" and not roster_valid():
		finish(true,"The roster is no longer valid for this match type.")
		return
	if phase == "Countdown":
		if not loading_hold:
			countdown += dt
			if countdown >= OPENING_SECONDS:
				phase = "Active"
				for r in robots: r.protection = 0.0
	elif phase == "Active":
		elapsed += dt
		hit_marker = maxf(0,hit_marker-dt)
		map.tick(dt)
		if match_type == "CTF": tick_flags(dt)
		tick_drops(dt)
		if local_robot and not local_robot.alive:
			death_view_remaining = maxf(0.0, death_view_remaining - dt)
		var top := 0
		if MatchTypes.individual(match_type):
			for r in robots: top = maxi(top,r.kills)
		else: top = maxi(team_scores[0],team_scores[1])
		if match_type=="ELIMINATION":
			if top>=goal or robots.filter(func(robot): return not robot.eliminated()).size()<=1 or elapsed>=time_limit: finish()
		elif top >= goal or elapsed >= time_limit: finish()
	else: map.tick(dt)

func uses_first_person() -> bool:
	return phase == "Active" and local_robot != null and local_robot.alive and not third_person and local_robot.protection <= 0 and local_robot.spawn_remaining <= 0 and local_robot.repair == null

func update_view_models():
	if local_robot == null: return
	var fp := uses_first_person()
	local_robot.body.visible = not fp
	local_robot.gun.visible = local_robot.alive and local_robot.weapon_pose_visible and not fp
	if is_instance_valid(first_person): first_person.visible = fp

func _process(dt):
	if camera_rig!=null: camera_rig.shake_enabled=not reduced_motion and phase=="Active"
	if async_scene_loading and not initialization_complete: return
	if not authority and local_robot!=null and not local_robot.alive:
		death_view_remaining=maxf(0.0,death_view_remaining-dt)
	for team in flags.size():
		flags[team].base_effect.configure(team_colors[team], reduced_motion)
	update_view_models()
	if phase == "Countdown" or local_robot == null:
		if local_robot != null:
			var focus: Vector3 = local_robot.global_position + Vector3.UP * 0.9
			var point: Vector3 = focus
			# Narrow chamber doors need a shallower front-left angle. Prefer a
			# complete view over retracting a wide angle into the robot's chest.
			for lateral in [-2.5,-1.2,-0.5,-0.15]:
				var candidate: Vector3 = focus + Basis(Vector3.UP,local_robot.yaw) * Vector3(lateral,0.65,-3.0)
				var obstruction := combat.ray(focus,candidate,[],1)
				if not obstruction.is_empty(): candidate = obstruction.position + obstruction.normal * 0.15
				if candidate.distance_squared_to(focus)>point.distance_squared_to(focus): point=candidate
				if obstruction.is_empty(): break
			camera_rig.set_cinematic("opening",point,focus,fov)
		return
	var r = local_robot
	if r.eliminated() and phase=="Active" and death_view_remaining<=0:
		var survivors: Array=robots.filter(func(robot): return robot.alive and not robot.eliminated())
		if not survivors.is_empty():
			var focus: Vector3=survivors[0].eye()
			var desired: Vector3=focus+Basis(Vector3.UP,survivors[0].yaw)*Vector3(0.6,1.0,3.0)
			var obstruction:=combat.ray(focus,desired,[],1)
			camera_rig.set_cinematic("spectating",obstruction.position+obstruction.normal*0.18 if not obstruction.is_empty() else desired,focus,fov)
			return
	if not r.alive and death_view_remaining > 0 and is_instance_valid(local_death_corpse):
		var focus: Vector3 = local_death_corpse.global_position + Vector3.UP * 0.95
		var desired := focus + Basis(Vector3.UP, r.yaw) * Vector3(1.5, 1.0, -3.2)
		if local_fall_death:
			if fall_camera_stop == Vector3.INF and desired.y <= -25.0:
				fall_camera_stop = Vector3(desired.x, -25.0, desired.z)
			if fall_camera_stop != Vector3.INF: desired = fall_camera_stop
		else:
			var obstruction := combat.ray(focus, desired, [], 1)
			if not obstruction.is_empty(): desired = obstruction.position + obstruction.normal * 0.15
		camera_rig.set_cinematic("death",desired,focus,fov)
		return
	var third := not uses_first_person()
	var basis := Basis(Vector3.UP,r.yaw) * Basis(Vector3.RIGHT,r.pitch + deg_to_rad(r.recoil))
	var eye: Vector3 = r.eye()
	var target: Vector3 = eye
	if third:
		target = eye + basis * Vector3(0.48,0.25,2.0 if r.repair == null else 4.0)
		var hit := combat.ray(eye,target,[],1)
		if not hit.is_empty(): target = hit.position + hit.normal * 0.18
	var view := "tpv" if third else "fpv"
	var desired_fov := fov / 2.5 if r.equipped in ["rifle", "rocket_launcher"] and r.wants_secondary and r.can_act() else fov
	var smooth_fov := lerpf(camera.fov,desired_fov,minf(1,dt*12))
	camera_rig.set_gameplay(view,Transform3D(basis,target),smooth_fov,camera_snap)
	camera_snap = false

func fall_killer(victim: ArenaRobot) -> ArenaRobot:
	if victim.last_hit_weapon not in ["grenade_launcher","rocket_launcher","emp_gun"]: return null
	var attacker: ArenaRobot=robot_by_id(victim.last_hit_robot_id)
	return attacker if attacker!=null and attacker!=victim and attacker.enemy(victim) else null

func eliminate(victim,killer,cause: String):
	if not victim.alive or phase != "Active": return
	if cause=="Fall off map": killer=fall_killer(victim)
	var credited_weapon: String=victim.last_hit_weapon if cause=="Fall off map" and killer!=null else cause
	victim.alive = false
	kill_chains.erase(victim.robot_id)
	map.abort_repair_for_robot(victim,"death")
	victim.deaths += 1
	victim.collision_layer = 0
	victim.streaming = false
	combat.stop_contact(victim)
	victim.reload_time = 0
	var incoming := Vector3.ZERO
	if killer != null:
		incoming = Basis(Vector3.UP, victim.yaw).inverse() * (killer.global_position - victim.global_position).normalized()
	var fall_death := cause == "Fall off map"
	var lunar_impact := {}
	if fall_death:
		var hit := combat.ray(victim.global_position+Vector3.UP*0.5,victim.global_position-Vector3.UP*0.5,[],1)
		if not hit.is_empty() and hit.collider.get_meta("lethal_surface",false): lunar_impact=hit
	var death_clip := RobotClips.death(cause, incoming, victim.crouched)
	if not lunar_impact.is_empty(): death_clip="death_front"
	victim.pose(death_clip)
	var death_animation: Animation = victim.animator.get_animation_library("").get_animation("common_" + death_clip)
	var falling_out := fall_death and lunar_impact.is_empty()
	var death_duration := 3.0 if falling_out else death_animation.length if death_animation != null else 104.0 / 30.0
	Assets.paint(victim.body,victim.tint,victim.armor_secondary,victim.head,true,victim.upper_body)
	Assets.paint(victim.gun,victim.tint,victim.armor_secondary,victim.head,true,victim.upper_body)
	var corpse = victim.body.duplicate()
	for mesh in corpse.find_children("SK_TensorShield*","MeshInstance3D",true,false): mesh.hide()
	add_child(corpse)
	corpse.visible = true
	corpse.global_transform = victim.body.global_transform
	for collider in corpse.find_children("*", "CollisionObject3D", true, false): collider.collision_layer = 0
	var corpse_animator := corpse.find_child("RuntimeAnimator", true, false) as AnimationPlayer
	if corpse_animator:
		corpse_animator.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
		corpse_animator.play("common_" + death_clip, 0.0)
		corpse_animator.advance(0.0)
		if not lunar_impact.is_empty() and death_animation != null:
			# Falling is an airborne loop. Ground impact needs the settled corpse,
			# without replaying a standing collapse or changing respawn timing.
			corpse_animator.seek(death_animation.length, true, true)
			corpse_animator.pause()
	var landing_point: Vector3 = victim.global_position
	if not lunar_impact.is_empty():
		landing_point=lunar_impact.position
		corpse.global_position.y=landing_point.y
	if not fall_death:
		var landing := SurfacePlacement.below(get_world_3d(),victim.global_position,map.config.fall_boundary)
		if landing.is_empty(): landing = SurfacePlacement.below(get_world_3d(),victim.last_safe,map.config.fall_boundary)
		landing_point = landing.position if not landing.is_empty() else victim.last_safe
	corpses.append({"robot":victim.robot_id,"node":corpse,"time":death_duration + 1.0,"point":landing_point,"fall_velocity":victim.velocity.y if falling_out else 0.0,"falling_out":falling_out,"ep":0.0 if fall_death else victim.ep if victim.ah <= 0 else 0.0,"killer":killer.robot_id if killer else -1})
	victim.hide()
	victim.respawn_time = death_duration + 1.0
	if victim.carrying >= 0:
		var flag: Dictionary = flags[victim.carrying]
		drop_carried_flag(flag,victim.global_position,cause == "Fall off map")
		victim.carrying = -1
	if killer != null:
		killer.kills += 1
		killer.reached = elapsed
		if match_type == "TDM": team_scores[killer.team] += 1; team_reached[killer.team] = elapsed
		for id in victim.contributors:
			if id == killer.robot_id: continue
			var total := 0.0
			for contribution in victim.contributors[id]:
				if elapsed-contribution[0] <= 10: total += contribution[1]
			var helper = robot_by_id(id)
			if total >= 20 and helper: helper.assists += 1
		push_feed({"kind":"kill", "killer":killer.display_name, "killer_team":killer.team,
			"victim":victim.display_name, "victim_team":victim.team,
			"weapon":Arsenal.WEAPONS[credited_weapon].title if Arsenal.WEAPONS.has(credited_weapon) else credited_weapon.replace("_", " ").capitalize(),"cause":cause})
		if killer != victim and killer.enemy(victim):
			record_elimination(killer,victim.display_name)
			if callouts: callouts.kill_quip(killer,credited_weapon)
			if match_type=="GUNGAME": advance_gun_game(killer,true)
	else:
		push_feed({"kind":"death", "victim":victim.display_name, "victim_team":victim.team,
			"cause":cause})
	if victim == local_robot:
		local_death_corpse = corpse
		death_view_remaining = death_duration + 1.0
		local_fall_death = falling_out
		fall_camera_stop = Vector3.INF
	if victim.eliminated():
		if not online and victim==local_robot:
			finish(false,"You lost all five lives.",true)
		elif callouts:
			callouts.publish("Eliminated","Announcer",-1,true,Vector3.INF,victim.robot_id)

func spawn_energy_drops(point: Vector3, energy: float, killer_id: int) -> void:
	var scatter := EnergyCoreScatter.new()
	effects.add_child(scatter)
	var placements: Array[Vector3] = await scatter.positions(point+Vector3.UP*0.2,ceili(energy/ArenaTuning.DROPPED_CORE_EP),rng.randi())
	scatter.free()
	for position in placements:
		var amount := minf(ArenaTuning.DROPPED_CORE_EP,energy)
		var node := CoreOrb.new("energy",true)
		effects.add_child(node)
		node.global_position = position
		drops.append({"node":node,"time":ArenaTuning.DROPPED_CORE_LIFETIME,"ep":amount,"killer":killer_id,"claim":-1})
		energy -= amount

func tick_drops(dt: float):
	for corpse in corpses.duplicate():
		if corpse.falling_out or corpse.node.global_position.y > corpse.point.y + 0.01:
			corpse.fall_velocity -= gravity * dt
			var position: Vector3 = corpse.node.global_position
			position.y += corpse.fall_velocity * dt
			if not corpse.falling_out: position.y = maxf(corpse.point.y,position.y)
			corpse.node.global_position = position
		corpse.time -= dt
		if corpse.time <= 0:
			corpse.node.queue_free()
			corpses.erase(corpse)
			if corpse.ep > 0:
				spawn_energy_drops(corpse.point,corpse.ep,corpse.killer)
	for drop in drops.duplicate():
		drop.time -= dt
		var killer = robot_by_id(drop.killer)
		var collector = null
		if killer != null and killer.can_act() and killer.ep < ArenaTuning.MAX_EP and killer.global_position.distance_to(drop.node.global_position) <= 10:
			drop.claim = killer.robot_id
			var target: Vector3 = killer.body_shape.global_position
			drop.node.global_position = drop.node.global_position.move_toward(target,ArenaTuning.DROPPED_CORE_SPEED * dt)
			if drop.node.global_position.distance_to(target) < 0.5: collector = killer
		else:
			drop.claim = -1
			for robot in robots:
				if robot.can_act() and robot.ep < ArenaTuning.MAX_EP and robot.global_position.distance_to(drop.node.global_position) < 0.8: collector = robot; break
		if collector != null:
			collector.ep = minf(ArenaTuning.MAX_EP,collector.ep + drop.ep)
			audio.energy_core_pickup(collector.body_shape.global_position,collector == local_robot or online,collector)
		if collector != null or drop.time <= 0:
			drop.node.queue_free()
			drops.erase(drop)

func tick_flags(dt: float):
	for team in 2:
		var flag: Dictionary = flags[team]
		if flag.state == "carried":
			var carrier = robot_by_id(flag.carrier)
			if carrier == null or not carrier.alive:
				drop_carried_flag(flag,flag.node.global_position,false)
				continue
			if carrier != null:
				var mount := Assets.socket(carrier.body,"FlagMount")
				var back := Assets.socket(flag.node,"BackMount")
				if mount and back:
					var relative: Transform3D = flag.node.global_transform.affine_inverse() * back.global_transform
					flag.node.global_transform = mount.global_transform * relative.affine_inverse()
				if carrier.can_act() and flags[carrier.team].state == "home" and flags[carrier.team].capture_area.overlaps_body(carrier):
					team_scores[carrier.team] += 1
					team_reached[carrier.team] = elapsed
					carrier.captures += 1
					carrier.carrying = -1
					reset_flag_home(flag)
					push_feed({"kind":"flag", "actor":carrier.display_name, "team":carrier.team, "action":"captured the flag"})
					message.emit("FLAG CAPTURED")
		else:
			if flag.falling:
				flag.fall_velocity -= gravity * dt
				var next_position: Vector3 = flag.node.global_position
				next_position.y = maxf(flag.point.y,next_position.y + flag.fall_velocity * dt)
				flag.node.global_position = next_position
				if next_position.y <= flag.point.y + 0.01:
					flag.falling = false
					SurfacePlacement.ground_mount(flag.node,Assets.socket(flag.node,"GroundMount"),flag.point)
					Assets.play(flag.node,"deploy")
				else: continue
			for r in robots:
				if not r.can_act() or r.position.distance_to(flag.point) > 1.1: continue
				if r.team == team and flag.state == "dropped":
					reset_flag_home(flag)
					push_feed({"kind":"flag", "actor":r.display_name, "team":r.team, "action":"returned the flag"})
					break
				elif r.team != team and r.carrying < 0:
					r.carrying = team
					flag.state = "carried"
					flag.carrier = r.robot_id
					flag.falling = false
					Assets.play(flag.node,"stow")
					push_feed({"kind":"flag", "actor":r.display_name, "team":r.team, "action":"took the flag"})
					break

func finish(canceled := false, reason := "", local_eliminated := false):
	if phase == "Finished": return
	audio.cue("objective",Vector3.ZERO,true)
	phase = "Finished"
	map.abort_all_repairs("match_canceled" if canceled else "match_finished")
	var entries: Array = []
	for robot in robots: entries.append(robot.snapshot())
	var teams := [{"name":"Team A","score":team_scores[0],"time":team_reached[0]},{"name":"Team B","score":team_scores[1],"time":team_reached[1]}]
	var winners: Array
	if match_type=="ELIMINATION" and not entries.any(func(entry): return entry.kills>=goal): winners=MatchTypes.elimination_winners(entries)
	elif MatchTypes.individual(match_type): winners = Arsenal.winners(entries,"kills","reached")
	else:
		winners = Arsenal.winners(teams,"score","time")
	var mvps := Arsenal.winners(entries,"kills","reached")
	var mvp_names: Array[String] = []
	for mvp in mvps: mvp_names.append(mvp.name)
	result = {"match_type":match_type,"teams":teams,"title":"Canceled" if canceled else "Eliminated" if local_eliminated else "Draw" if winners.size() != 1 else winners[0].name + " wins", "mvp":"" if canceled else ", ".join(mvp_names),"entries":entries,"elapsed":elapsed,"canceled":canceled,"early_exit":local_eliminated,"winner_ids":[]}
	if not canceled and not local_eliminated and winners.size()==1:
		for robot in robots:
			if (MatchTypes.individual(match_type) and robot.robot_id==int(winners[0].id)) or (not MatchTypes.individual(match_type) and robot.team==(0 if winners[0].name=="Team A" else 1)): result.winner_ids.append(robot.robot_id)
	result["reason"] = reason if reason != "" else "Not enough players to continue." if canceled else ""
	result["goal"] = goal
	var winning_team := -1
	if not canceled and winners.size() == 1 and not MatchTypes.individual(match_type): winning_team = 0 if winners[0].name == "Team A" else 1
	for robot in robots:
		if not robot.alive: continue
		if canceled or local_eliminated or winners.size() != 1: robot.pose("common/idle")
		elif robot.display_name == winners[0].name or robot.team == winning_team and winning_team >= 0:
			robot.pose("common/"+robot.account_emote if online and robot.account_emote != "" else RobotClips.victory(robot.robot_id, int(elapsed)))
		else: robot.pose("defeated")
	for flag in flags:
		reset_flag_home(flag)
	for r in robots: r.carrying = -1
	notice(result.title)
	completed.emit()

func local_won() -> bool:
	return local_robot != null and local_robot.robot_id in result.get("winner_ids",[])

func advance_gun_game(robot: ArenaRobot, deferred := false) -> void:
	if robot.gun_game_cycle.is_empty():
		var cycle: Array=Arsenal.WEAPONS.keys()
		shuffle_roster(cycle,rng)
		if cycle.size()>1 and cycle[0]==robot.gun_game_weapon:
			var first=cycle[0];cycle[0]=cycle[1];cycle[1]=first
		robot.gun_game_cycle.assign(cycle)
	robot.gun_game_weapon=robot.gun_game_cycle.pop_front()
	if robot.alive:
		if deferred: equip_gun_game.call_deferred(robot)
		else: equip_gun_game(robot)

func equip_gun_game(robot: ArenaRobot) -> void:
	if phase=="Finished" or not is_instance_valid(robot) or not robot.alive or robot.gun_game_weapon.is_empty(): return
	var id: String=robot.gun_game_weapon
	robot.owned_weapons.assign([id])
	robot.pickup_weapon="" if id=="pistol" else id
	robot.queued_weapon=""
	robot.reload_time=0.0
	if id!="pistol":
		var ammo:=robot.ammo_entry(id)
		ammo.loaded=int(Arsenal.WEAPONS[id].capacity)
		ammo.packs=mini(int(ammo.packs),3)
	robot.equip(id)

func notice(text: String, robot = null):
	message.emit(text)
	if callouts:
		if robot != null and ArenaSpeech.follows_speaker(text):
			callouts.publish(text,robot.display_name,robot.team,false,robot.eye(),-1,robot.robot_id)
			return
		var critical := text.begins_with("ARENA /") or text.begins_with("POWER /") or phase == "Finished"
		var speaker = robot if robot != null else local_robot
		var robot_voice := speaker != null and (not critical or text.begins_with("POWER /"))
		callouts.publish(text,speaker.display_name if robot_voice else "Announcer",speaker.team if robot_voice else -1,critical,speaker.global_position if robot_voice else Vector3.INF,robot.robot_id if robot != null else -1,speaker.robot_id if robot_voice else -1)

func record_elimination(killer: ArenaRobot, victim_name: String) -> void:
	var chain: Dictionary = kill_chains.get(killer.robot_id,{"count":0,"time":-INF})
	var count: int = int(chain.count)+1 if elapsed-float(chain.time)<=KILL_CHAIN_WINDOW else 1
	if killer.alive: kill_chains[killer.robot_id]={"count":count,"time":elapsed}
	else: count=1
	var event := {"kind":"elimination","recipient":killer.robot_id,"victim":victim_name,"count":count,"accolade":KILL_ACCOLADES.get(count,"")}
	if replicating and authority: present(event)
	else: receive_elimination(event)

func receive_elimination(event: Dictionary) -> void:
	if local_robot == null or int(event.recipient) != local_robot.robot_id: return
	local_elimination.emit(event)
	if not String(event.accolade).is_empty() and callouts:
		callouts.play_recording(String(event.accolade),true,Vector3.INF)

func push_feed(event: Dictionary) -> void:
	event["time"] = elapsed
	feed_events.push_front(event)
	if feed_events.size() > 4: feed_events.pop_back()
	if callouts and event.kind == "flag":
		callouts.publish(event.actor + " " + event.action,"Announcer",int(event.team),true)

func robot_by_id(id: int):
	for robot in robots:
		if robot.robot_id == id: return robot
	return null

func remove_robot(id: int) -> void:
	var robot = robot_by_id(id)
	if robot == null: return
	if robot.carrying >= 0:
		drop_carried_flag(flags[robot.carrying], robot.global_position, false)
		robot.carrying = -1
	map.abort_repair_for_robot(robot, "disconnect")
	robot.streaming = false
	combat.stop_contact(robot)
	audio.set_loop("weapon_" + str(id), robot.equipped, robot.muzzle(), false)
	audio.set_loop("walk_" + str(id), "walk", robot.global_position, false)
	push_feed({"kind": "leave", "actor": robot.display_name, "team": robot.team})
	robots.erase(robot)
	if robot == local_robot: local_robot = null
	robot.queue_free()
	if online and phase == "Active":
		if match_type=="ELIMINATION" and not robots.is_empty():
			if robots.filter(func(r): return not r.eliminated()).size()<=1: finish()
			return
		goal = 2 * robots.size()
		var team_a := robots.any(func(r): return r.team == 0)
		var team_b := robots.any(func(r): return r.team == 1)
		if robots.size() < 2 or (not MatchTypes.individual(match_type) and (not team_a or not team_b)): finish(true,"A team is empty." if not MatchTypes.individual(match_type) and (not team_a or not team_b) else "Fewer than two players remain.")

func roster_valid() -> bool:
	return robots.size() >= 2 and (MatchTypes.individual(match_type) or (robots.any(func(r): return r.team == 0) and robots.any(func(r): return r.team == 1)))

func score_text() -> String:
	if match_type=="ELIMINATION": return "%d / %d lives" % [local_robot.lives_remaining() if local_robot else 0,MatchTypes.LIVES]
	if MatchTypes.individual(match_type): return "%d / %d" % [local_robot.kills if local_robot else 0,goal]
	return "A %d  :  %d B  /  %d" % [team_scores[0],team_scores[1],goal]

func clock_text() -> String:
	var remaining := maxi(0,int(time_limit-elapsed))
	return "%02d:%02d" % [remaining/60,remaining%60]


func _exit_tree():
	get_tree().node_added.disconnect(configure_emissive_only_light)
	# Remove per-instance materials while imported base resources are still alive.
	# RenderingServer can otherwise inspect freed override RIDs during teardown.
	for mesh in find_children("*","MeshInstance3D",true,false):
		mesh.material_overlay = null
		mesh.material_override = null
		if mesh.mesh:
			for surface in mesh.mesh.get_surface_count(): mesh.set_surface_override_material(surface,null)
