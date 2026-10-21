class_name ArenaRobot
extends CharacterBody3D

var arena_match
var robot_id := 0
var voice_variant := -1
var display_name := "Tensor"
var team := 0
var head := "projector"
var upper_body := "default"
var tint := Color("6fe5ea")
var armor_secondary := Color("6fe5ea")
var account_emote := ""
var human := false
var ah := 100.0
var ep := ArenaTuning.MAX_EP
var sh := 0.0
var shield_time := 0.0
var protection := 5.0
var alive := true
var respawn_time := 0.0
var ramp_stage := 0 # 1: magnetic traction to native lip, 2: ballistic flight
var ramp_target := Vector3.ZERO
var ramp_velocity := Vector3.ZERO
var ramp_time := 0.0

func begin_speed_ramp(lip: Vector3,impulse: Vector3) -> void:
	ramp_stage=1;ramp_target=lip;ramp_velocity=impulse;ramp_time=0
	lift_target=-INF

var kills := 0
var deaths := 0
var captures := 0
var assists := 0
var reached := 0.0
const MAX_WEAPON_SLOTS := 10
var owned_weapons: Array[String] = ["pistol"]
var gun_game_cycle: Array[String] = []
var gun_game_weapon := ""
var ammo_inventory: Dictionary = {}
var previous_weapon := "pistol"
var queued_weapon := ""
var pickup_weapon := "":
	set(value):
		if value != "" and value not in owned_weapons:
			if owned_weapons.size() >= MAX_WEAPON_SLOTS: return
			owned_weapons.append(value)
		pickup_weapon = value
var equipped := "pistol"
var loaded: int:
	get: return int(ammo_for(ammo_weapon()).loaded)
	set(value): ammo_entry(ammo_weapon()).loaded = value
var packs: int:
	get: return int(ammo_for(ammo_weapon()).packs)
	set(value): ammo_entry(ammo_weapon()).packs = value
var reload_time := 0.0
var cooldown := 0.0
var stream_time := 0.0
var stream_damage_time := 0.0
var streaming := false
var stream_accuracy_error := Vector2.ZERO
var stream_accuracy_valid := false
var stream_accuracy_time := 0.0
var barrel := 0
var yaw := 0.0
var pitch := 0.0
var recoil := 0.0
var recoil_recovery_remaining := 0.0
var recoil_recovery_start := 0.0
var move_input := Vector2.ZERO
var wants_fire := false
var wants_secondary := false
var rocket_lock_target := -1
var rocket_lock_progress := 0.0
var wants_sprint := false
var wants_walk := false
var wants_crouch := false
var crouched := false
var jump_charge := 0.0
var jump_held := false
var jump_release := false
var jump_buffer := 0.0
var coyote_time := 0.0
var repair = null
var portal_lock := 0.0
var lift_target := -INF
var lift_speed := ArenaTuning.JUMP_PAD_SPEED
var lift_from_pad := false

var last_safe := Vector3.ZERO
var carrying := -1
var contributors: Dictionary = {}
var last_hit_robot_id := -1
var last_hit_weapon := ""
var body: Node3D
var skeleton: Skeleton3D
var animator: AnimationPlayer
var gun: Node3D
var weapon_pose_visible := true
var gun_socket: Transform3D
var brain
var listener: AudioListener3D
var opponent_marker: OpponentMarker
var target_nameplate: Label3D
var anim_state := ""
var animation_lock := 0.0
var previous_yaw := 0.0
var airborne_from_jump := false
var airborne_time := 0.0
var knockback_velocity := Vector3.ZERO
var applied_knockback := Vector3.ZERO
var crouch_idle_time := 0.0
var body_capsule: CapsuleShape3D
var body_shape: CollisionShape3D
var hit_flash := 0.0
var surface_material: ShaderMaterial
var surface_meshes: Array[MeshInstance3D] = []
var surface_active := false
var bot_aim := Vector3.FORWARD
var hit_rids: Array[RID] = []
var character_id := "tensor"
var character: Dictionary
var spawn_fixture: Dictionary = {}
var spawn_remaining := 0.0
var spawn_reload_remaining := 0.0
var spawn_reload_duration := 2.0
var slow_remaining := 0.0
var slow_multiplier := 1.0
var spawn_started := false
var weapon_vfx: WeaponVfx
var aim_pose := AimPose.new()
var movement_pose := MovementPose.new()
var hit_pose := HitPose.new()
var local_motion := Vector2.ZERO
var measured_speed := 0.0
var network_shots := 0
var network_trace_end := Vector3.ZERO
var network_initialized := false
var predicted_shot_time := -10000
var network_contact := Vector3.INF
var network_grounded := false
var network_presented_shot := 0

func _ready() -> void:
	character = ContentRegistry.character(character_id)
	collision_layer = 2
	collision_mask = 3
	floor_snap_length = ArenaTuning.STEP_HEIGHT
	body_shape = CollisionShape3D.new()
	body_capsule = CapsuleShape3D.new()
	body_capsule.radius = 0.32
	body_capsule.height = 1.72
	body_shape.shape = body_capsule
	body_shape.position.y = 0.86
	add_child(body_shape)
	body = Assets.model("characters", character.model)
	add_child(body)
	surface_material = EnergySurface.material(tint)
	for mesh in body.find_children("*", "MeshInstance3D", true, false):
		surface_meshes.append(mesh)
		mesh.extra_cull_margin=maxf(mesh.extra_cull_margin,0.06)
	body.rotation.y = character.forward_yaw
	skeleton = Assets.find(body, "Skeleton3D")
	movement_pose.configure(skeleton,character.animation_family)
	animator = AnimationPlayer.new()
	animator.name = "RuntimeAnimator"
	animator.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	skeleton.get_parent().add_child(animator)
	animator.root_node = NodePath("..")
	animator.add_animation_library("", AnimationLibrary.new())
	armor_secondary = Assets.robot_accent(body, tint, character.model)
	Assets.paint(body, tint, armor_secondary, head, false, upper_body)
	CollisionRig.install(body,"characters",character.model,self)
	if not (arena_match.replicating and DisplayServer.get_name() == "headless"):
		RobotDebrisMesh.prepare(body)
	opponent_marker = OpponentMarker.new()
	opponent_marker.robot = self
	opponent_marker.arena_match = arena_match
	opponent_marker.modulate = arena_match.team_colors[team]
	add_child(opponent_marker)
	target_nameplate = Label3D.new()
	target_nameplate.text = display_name
	target_nameplate.position.y = 2.46
	target_nameplate.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	target_nameplate.fixed_size = true
	target_nameplate.pixel_size = 0.0027
	target_nameplate.font_size = 22
	target_nameplate.outline_size = 5
	target_nameplate.outline_modulate = Color(0, 0, 0, 0.9)
	target_nameplate.modulate = Color("f4fbff")
	target_nameplate.no_depth_test = false
	target_nameplate.visibility_range_end = OpponentMarker.MAX_CAMERA_DISTANCE
	target_nameplate.visible = false
	add_child(target_nameplate)
	listener = AudioListener3D.new()
	listener.position.y = 1.55
	add_child(listener)
	equip("pistol")
	weapon_vfx = WeaponVfx.new()
	weapon_vfx.robot = self
	add_child(weapon_vfx)
	if not human and not arena_match.online:
		brain = ArenaBrain.new(self)


func begin_powered_jump(height: float, speed: float, from_pad := false) -> void:
	lift_target = global_position.y + height
	lift_speed = speed
	lift_from_pad = from_pad
	velocity.y = speed

func can_act() -> bool:
	return alive and protection <= 0 and spawn_remaining <= 0 and repair == null and arena_match.phase == "Active"

func spawn_look_locked() -> bool:
	return alive and spawn_fixture.get("stasis",false) and (spawn_remaining>0.0 or arena_match.phase=="Countdown")

func align_spawn_facing() -> void:
	var forward: Vector3=spawn_fixture.mount.global_basis.z
	forward.y=0.0
	forward=forward.normalized()
	yaw=atan2(-forward.x,-forward.z)
	previous_yaw=yaw
	pitch=0.0
	bot_aim=forward
	body.rotation.y=yaw+character.forward_yaw
	if human: listener.basis=Basis(Vector3.UP,yaw)

func enemy(other) -> bool:
	return other != self and (MatchTypes.individual(arena_match.match_type) or other.team != team)

func lives_remaining() -> int:
	return maxi(0,MatchTypes.LIVES-deaths)

func eliminated() -> bool:
	return arena_match != null and arena_match.match_type=="ELIMINATION" and lives_remaining()==0

func aim_direction() -> Vector3:
	if human: return Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch) * Vector3.FORWARD
	var right := bot_aim.cross(Vector3.UP).normalized()
	if right.length_squared()<0.01: right = Vector3.RIGHT
	return bot_aim.rotated(right,deg_to_rad(recoil)).normalized()

func eye() -> Vector3:
	return global_position + Vector3.UP * (1.08 if crouched else character.eye_height)

func update_crouch() -> void:
	var requested := wants_crouch and alive and protection <= 0 and repair == null and is_on_floor()
	if crouched and not requested:
		var query := PhysicsShapeQueryParameters3D.new()
		var headroom := BoxShape3D.new()
		headroom.size = Vector3(0.62, 0.54, 0.62)
		query.shape = headroom
		query.transform = global_transform * Transform3D(Basis.IDENTITY, Vector3.UP * 1.45)
		query.collision_mask = 1
		query.exclude = [get_rid()]
		if not get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty(): requested = true
	if requested == crouched: return
	crouched = requested
	body_capsule.height = 1.18 if crouched else 1.72
	body_shape.position.y = 0.59 if crouched else 0.86

func play_event(clip: String, duration: float) -> void:
	if clip == "fire" and anim_state.ends_with("/fire"):
		animator.play(anim_state.replace("/", "_"), 0.0)
		animator.seek(0.0, true)
	else: pose(clip)
	animation_lock = duration
	if skeleton != null and alive and spawn_remaining<=0 and repair==null and arena_match.phase=="Active": movement_pose.apply(0)

func muzzle() -> Vector3:
	if gun:
		var muzzles: Array = Arsenal.WEAPONS[equipped].muzzles
		var id: String = "Muzzle1" if equipped == "rocket_launcher" else muzzles[barrel % muzzles.size()]
		var point := Assets.socket(gun, id)
		if point: return point.global_position
	return eye() + aim_direction() * 0.4

func ammo_weapon() -> String:
	return equipped if equipped != "pistol" else pickup_weapon

func ammo_for(id: String) -> Dictionary:
	return ammo_inventory.get(id, {"loaded":0,"packs":0})

func ammo_entry(id: String) -> Dictionary:
	if not ammo_inventory.has(id): ammo_inventory[id] = {"loaded":0,"packs":0}
	return ammo_inventory[id]

func has_ammo(id: String) -> bool:
	return id == "pistol" or (id in owned_weapons and int(ammo_for(id).loaded)+int(ammo_for(id).packs)>0)

func can_pickup_weapon(id: String) -> bool:
	if arena_match != null and arena_match.match_type=="GUNGAME": return false
	if id == "pistol" or not Arsenal.WEAPONS.has(id): return false
	return owned_weapons.size()<MAX_WEAPON_SLOTS if id not in owned_weapons else int(ammo_for(id).loaded)<int(Arsenal.WEAPONS[id].capacity)

func can_pickup_ammo(id: String) -> bool:
	if id == "pistol" or not Arsenal.WEAPONS.has(id): return false
	var capacity: int = Arsenal.WEAPONS[id].capacity
	var ammo := ammo_for(id)
	return int(ammo.loaded)+(int(ammo.packs)+1)*capacity <= capacity*4

func pickup_ammo(id: String) -> bool:
	if not can_pickup_ammo(id): return false
	ammo_entry(id).packs += 1
	return true

func take_weapon(id: String) -> bool:
	if not can_pickup_weapon(id): return false
	var fresh := id not in owned_weapons
	if fresh: pickup_weapon=id
	var ammo := ammo_entry(id)
	ammo.loaded = int(Arsenal.WEAPONS[id].capacity)
	# A full precollected bank funds the loaded pack instead of exceeding the cap.
	ammo.packs = mini(int(ammo.packs),3)
	if id == equipped: reload_time = 0.0
	if fresh:
		reload_time = 0.0
		request_equip(id)
	return true

func request_equip(id: String) -> void:
	if id==equipped:
		queued_weapon=""
		return
	if weapon_vfx != null and not weapon_vfx.pending.is_empty(): queued_weapon=id
	else: equip(id)

func select_weapon(id: String) -> void:
	if id not in owned_weapons or not can_act() or reload_time>0: return
	request_equip(id)

func cycle_weapon(direction: int) -> String:
	var index := owned_weapons.find(equipped)
	return owned_weapons[posmod(index+direction,owned_weapons.size())]

func reset_inventory() -> void:
	owned_weapons.assign(["pistol"])
	ammo_inventory.clear()
	pickup_weapon=""
	previous_weapon="pistol"
	queued_weapon=""
	reload_time=0.0

func equip(id: String) -> void:
	if not Arsenal.WEAPONS.has(id): return
	if id not in owned_weapons and owned_weapons.size()>=MAX_WEAPON_SLOTS: return
	if id != equipped:
		previous_weapon=equipped if equipped in owned_weapons else "pistol"
		reload_time=0.0
	if id != "pistol" and id not in owned_weapons: pickup_weapon=id
	if skeleton: aim_pose.restore(skeleton)
	if gun:
		for node in gun.find_children("*","StaticBody3D",true,false): hit_rids.erase(node.get_rid())
		gun.free()
	equipped = id
	streaming = false
	if arena_match != null and arena_match.combat != null: arena_match.combat.stop_contact(self)
	stream_time = 0
	gun = Assets.model("weapons", Arsenal.WEAPONS[id].model)
	add_child(gun)
	CollisionRig.install(gun,"weapons",Arsenal.WEAPONS[id].model,self)
	var grip := Assets.socket(gun, "RightHandSocket")
	gun_socket = gun.global_transform.affine_inverse() * grip.global_transform if grip else Transform3D.IDENTITY
	var ammo_mount := Assets.socket(gun, "AmmoMount")
	if ammo_mount:
		ammo_mount.add_child(Assets.model("weapons", id, "_ammo"))
	Assets.play(gun, "idle", true)
	anim_state = ""
	pose("idle")
	animator.advance(0)
	attach_gun()

func pose(clip: String) -> void:
	var key: String = clip if "/" in clip else "common/" + clip if clip.begins_with("death") or clip.begins_with("victory") or clip in ["defeated", "falling"] else Arsenal.WEAPONS[equipped].animation_family + "/" + clip
	if key == anim_state: return
	var library := animator.get_animation_library("")
	if not library.has_animation(key.replace("/", "_")):
		var one_shot := clip.begins_with("death") or clip.begins_with("victory") or clip.begins_with("turn_90") or clip.begins_with("crouch_turn_90") or clip in ["reload", "fire", "hit_reaction", "jump", "jump_running", "jump_up", "jump_down", "stand_to_kneel", "kneel_to_stand", "common/falling_to_landing", "defeated"]
		var animation := Assets.playback_animation(key,character.animation_family,one_shot,"_arc_" in clip or "turn_90" in clip)
		if animation == null: return
		library.add_animation(key.replace("/", "_"), animation)
	set_weapon_pose_visible(RobotClips.uses_weapon(key))
	anim_state = key
	animator.play(key.replace("/", "_"), 0.16)
	if clip == "reload": animator.speed_scale = animator.current_animation_length / 2.0
	else: animator.speed_scale = 1.0

func set_weapon_pose_visible(visible: bool) -> void:
	if weapon_pose_visible == visible: return
	weapon_pose_visible = visible
	if gun == null: return
	gun.visible = visible and (arena_match == null or arena_match.local_robot != self or not arena_match.uses_first_person())
	for collider in gun.find_children("*", "CollisionObject3D", true, false):
		if not collider.has_meta("equipped_collision_layer"):
			collider.set_meta("equipped_collision_layer", collider.collision_layer)
		collider.collision_layer = int(collider.get_meta("equipped_collision_layer")) if visible else 0

func attach_gun() -> void:
	if gun and skeleton:
		var bone := skeleton.find_bone(character.skeleton.weapon_hand)
		if bone >= 0:
			gun.global_transform = skeleton.global_transform * skeleton.get_bone_global_pose(bone) * gun_socket.affine_inverse()

func pose_aim_direction() -> Vector3:
	# Only the local camera is offset from the eye ray. A bot's sight hit lies
	# on its existing eye direction, so tracing it again cannot change pose pitch.
	if human and arena_match and arena_match.combat and self == arena_match.local_robot:
		return (arena_match.combat.aim_target(self,Arsenal.WEAPONS[equipped].range)-eye()).normalized()
	return aim_direction()

func update_aim_pose(dt: float, record_costs := false) -> void:
	var stage_started := Time.get_ticks_usec() if record_costs else 0
	aim_pose.restore(skeleton)
	hit_pose.restore(skeleton)
	if record_costs: stage_started=profile_stage("pose_restore",stage_started)
	if spawn_reload_remaining > 0 and anim_state == "pistol/reload":
		animator.speed_scale = animator.current_animation_length / spawn_reload_duration
	animator.advance(dt)
	if record_costs: stage_started=profile_stage("pose_animation",stage_started)
	if alive and spawn_remaining<=0 and repair==null and arena_match.phase=="Active": movement_pose.apply(dt)
	if record_costs: stage_started=profile_stage("pose_locomotion",stage_started)
	if alive and spawn_remaining<=0 and repair==null and arena_match.phase=="Active": hit_pose.apply(self)
	if record_costs: stage_started=profile_stage("pose_hit",stage_started)
	if alive and arena_match.phase == "Active" and reload_time <= 0 and spawn_reload_remaining <= 0 and repair == null:
		var direction := pose_aim_direction()
		aim_pose.apply(self, asin(clampf(direction.y, -1, 1)))
	if record_costs: stage_started=profile_stage("pose_aim",stage_started)
	attach_gun()
	if record_costs: profile_stage("pose_attachment",stage_started)

func _process(dt: float) -> void:
	# Authority already samples the active body for collision/aim each physics
	# tick. Avoid a second full skeleton pass solely for the rendered frame.
	if not arena_match.authority or not can_act(): update_aim_pose(dt)
	EnergySurface.update(self)
	if arena_match!=null:
		var weapon_loop_active: bool = alive and streaming and reload_time<=0 and arena_match.phase=="Active"
		arena_match.audio.set_loop("weapon_"+str(robot_id),equipped,muzzle() if weapon_loop_active else Vector3.ZERO,weapon_loop_active,self == arena_match.local_robot)
		if not arena_match.authority:
			hit_flash = maxf(0,hit_flash-dt)
			var speed := Vector2(velocity.x,velocity.z).length()
			arena_match.audio.set_loop("walk_"+str(robot_id),"walk",global_position,alive and network_grounded and speed > 0.25 and repair == null and spawn_remaining <= 0 and arena_match.phase == "Active",self == arena_match.local_robot,Locomotion.footstep_rate(speed))
			arena_match.audio.set_loop("contact_"+str(robot_id),"hit_"+equipped,network_contact if network_contact != Vector3.INF else Vector3.ZERO,alive and streaming and reload_time <= 0 and network_contact != Vector3.INF and arena_match.phase == "Active")
		if not alive or not streaming or reload_time>0 or arena_match.phase!="Active" or equipped not in ["lightning_gun", "flamethrower"]:
			arena_match.audio.set_loop("contact_"+str(robot_id),"hit_"+equipped,Vector3.ZERO,false)

static var profile_stages := false
static var stage_usec: Dictionary = {}

static func profile_stage(stage: String, started: int) -> int:
	var now := Time.get_ticks_usec()
	stage_usec[stage] = int(stage_usec.get(stage,0)) + now-started
	return now

func begin_spawn_reload() -> void:
	if equipped != "pistol": return
	spawn_reload_duration = 2.0
	if arena_match.phase == "Countdown":
		spawn_reload_duration = minf(2.0,maxf(0.001,ArenaMatch.OPENING_SECONDS-arena_match.countdown))
	spawn_reload_remaining = spawn_reload_duration
	pose("reload")
	animator.speed_scale = animator.current_animation_length / spawn_reload_duration

func tick_spawn_reload(dt: float) -> void:
	if spawn_reload_remaining <= 0: return
	spawn_reload_remaining = maxf(0,spawn_reload_remaining-dt)
	if not alive or equipped != "pistol" or protection <= 0: spawn_reload_remaining = 0
	if spawn_reload_remaining == 0 and anim_state == "pistol/reload": pose("idle")

func _physics_process(dt: float) -> void:
	if arena_match == null or not arena_match.authority: return
	if spawn_look_locked(): align_spawn_facing()
	if not can_act() or equipped != "rocket_launcher" or not wants_secondary or reload_time > 0:
		rocket_lock_target = -1
		rocket_lock_progress = 0.0
	slow_remaining = maxf(0,slow_remaining-dt)
	if slow_remaining == 0:slow_multiplier=1.0
	if spawn_remaining > 0:
		# Scene preparation renders the world before the opening is revealed.
		# Keep spawn motion and its fixture cues tied to the visible countdown.
		if arena_match.get("loading_hold")==true: return
		arena_match.audio.set_loop("walk_" + str(robot_id), "walk", global_position, false)
		if arena_match.phase=="Countdown" and arena_match.countdown < arena_match.zone_spawn_time(spawn_fixture.team): return
		if arena_match.phase not in ["Countdown","Active"]: return
		if not spawn_started:
			spawn_started=true
			arena_match.map.begin_spawn(spawn_fixture,self)
		spawn_remaining=maxf(0,spawn_remaining-dt)
		if spawn_remaining <= spawn_fixture.get("duration", 104.0 / 30.0) - spawn_fixture.get("reveal_after", 42.0 / 30.0): show()
		if spawn_remaining==0:
			var lift_player := Assets.find(spawn_fixture.node,"AnimationPlayer") as AnimationPlayer
			lift_player.seek(spawn_fixture.get("duration", 104.0/30.0),true)
			lift_player.pause()
			var lift_skeleton := Assets.find(spawn_fixture.node,"Skeleton3D") as Skeleton3D
			lift_skeleton.force_update_all_bone_transforms()
			pose("idle")
		var mount: Node3D=spawn_fixture.mount
		if mount: global_position=mount.global_position+Vector3.UP*safe_margin
		velocity=Vector3.ZERO
		protection=5.0
		if spawn_remaining==0:
			last_safe=global_position
			begin_spawn_reload()
		return
	tick_spawn_reload(dt)
	if arena_match.phase != "Active":
		arena_match.audio.set_loop("walk_" + str(robot_id), "walk", global_position, false)
		return
	if alive and repair==null and reload_time<=0 and queued_weapon != "" and weapon_vfx.pending.is_empty():
		var next_weapon := queued_weapon
		queued_weapon=""
		equip(next_weapon)
	var held_discrete_fire := (wants_fire and equipped not in ["lightning_gun", "flamethrower"]) or (Arsenal.orb_secondary(equipped) and wants_secondary)
	cooldown = cooldown - dt if held_discrete_fire and cooldown > 0 else maxf(0, cooldown - dt)
	if stream_damage_time > 0: stream_damage_time -= dt
	portal_lock = maxf(0, portal_lock - dt)
	hit_flash = maxf(0, hit_flash - dt)
	if not alive:
		arena_match.audio.set_loop("walk_" + str(robot_id), "walk", global_position, false)
		if eliminated(): return
		respawn_time -= dt
		if respawn_time <= 0: arena_match.spawn_robot(self)
		return
	animation_lock = maxf(0.0, animation_lock - dt)
	protection = maxf(0, protection - dt)
	shield_time = maxf(0, shield_time - dt)
	if shield_time <= 0: sh = 0
	if repair != null:
		arena_match.audio.set_loop("walk_" + str(robot_id), "walk", global_position, false)
		tick_repair_motion(dt)
		return
	var previous_ep := ep
	ep = maxf(0, ep - ArenaTuning.EP_DRAIN_PER_SECOND * dt)
	if (previous_ep>ArenaTuning.HALF_EP and ep<=ArenaTuning.HALF_EP) or (previous_ep>=ArenaTuning.CRITICAL_EP and ep<ArenaTuning.CRITICAL_EP):
		if self==arena_match.local_robot or (arena_match.replicating and human): arena_match.audio.cue("low_energy",eye(),true,self)
		if previous_ep>ArenaTuning.HALF_EP: arena_match.notice("Finding energy core.",self)
		else: arena_match.notice("Emergency!",self)
	if ep <= 0:
		arena_match.eliminate(self, null, "Power depleted")
		return
	var stage_started := Time.get_ticks_usec() if profile_stages else 0
	if brain: brain.tick(dt)
	if profile_stages: stage_started=profile_stage("brain",stage_started)
	if reload_time > 0:
		reload_time = maxf(0, reload_time - dt)
		if reload_time == 0 and packs > 0:
			packs -= 1
			loaded = Arsenal.WEAPONS[equipped].capacity
	simulate_movement(dt)
	if profile_stages: stage_started=profile_stage("movement",stage_started)
	if can_act():
		update_aim_pose(dt,profile_stages)
		if profile_stages: stage_started=profile_stage("pose",stage_started)
		arena_match.combat.update_rocket_lock(self, dt)
		if brain: brain.validate_fire()
		arena_match.combat.trigger(self, dt)
		if profile_stages: profile_stage("combat",stage_started)
	else:
		streaming = false
		arena_match.combat.stop_contact(self)

func simulate_movement(dt: float, predicted := false, replaying := false) -> void:
	var was_crouched := crouched
	update_crouch()
	if ep <= ArenaTuning.HALF_EP or (not jump_held and not jump_release) or (jump_held and not is_on_floor()): jump_charge = 0.0
	if jump_held and can_act() and ep > ArenaTuning.HALF_EP and not crouched and is_on_floor(): jump_charge += dt
	jump_buffer = maxf(0.0, jump_buffer - dt)
	coyote_time = ArenaTuning.COYOTE_TIME if is_on_floor() else maxf(0.0, coyote_time - dt)
	var charged := jump_release and jump_charge >= ArenaTuning.CHARGE_SECONDS and ep > ArenaTuning.HALF_EP and is_on_floor()
	var jumped := can_act() and not crouched and (charged or (jump_buffer > 0.0 and coyote_time > 0.0))
	if jumped:
		var height: float = arena_match.jump_release_height(ArenaTuning.CHARGED_JUMP_HEIGHT if charged else ArenaTuning.NORMAL_JUMP_HEIGHT)
		begin_powered_jump(height, sqrt(2.0 * arena_match.gravity * height))
		airborne_from_jump = true
		jump_charge = 0.0
		jump_buffer = 0.0
		coyote_time = 0.0
	jump_release = false
	var speed := Locomotion.speed(wants_walk, wants_sprint, ep, protection > 0, crouched)
	var direction := Basis(Vector3.UP, yaw) * Vector3(move_input.x, 0, move_input.y)
	# Remove last frame's external motion before accelerating the movement motor.
	velocity -= applied_knockback
	velocity = Locomotion.horizontal_velocity(velocity, direction, speed*slow_multiplier, is_on_floor(), dt)
	if ramp_stage != 0:
		ramp_time += dt
		if ramp_stage == 1:
			var to_lip := ramp_target-global_position
			if to_lip.length() <= ramp_velocity.length()*dt+0.06:
				velocity=ramp_velocity;ramp_stage=2;ramp_time=0;airborne_from_jump=true
			else:velocity=to_lip.normalized()*ramp_velocity.length()
		else:
			velocity.x=ramp_velocity.x;velocity.z=ramp_velocity.z
			if (is_on_floor() and ramp_time>0.12) or ramp_time>3:ramp_stage=0
	knockback_velocity = knockback_velocity.move_toward(Vector3.ZERO, ArenaTuning.KNOCKBACK_DRAG * dt)
	applied_knockback = knockback_velocity
	velocity += applied_knockback
	if ramp_stage == 1:
		pass # Magnetic traction follows the incline until the native release lip.
	elif lift_target > global_position.y:
		velocity.y = lift_speed
		if is_on_ceiling(): lift_target = -INF
	else:
		lift_target = -INF
		if not is_on_floor(): velocity.y -= arena_match.gravity * dt
	var previous_position := global_position
	var grounded := is_on_floor()
	var falling_speed := velocity.y
	var stepped := grounded and not jumped and direction.length_squared() > 0.01 and try_step_up(dt)
	move_and_slide()
	if lift_target != -INF and (global_position.y >= lift_target or is_on_ceiling()):
		# Release thrust without erasing momentum. Ceiling response belongs to move_and_slide.
		lift_target = -INF
	# Slide the impulse along walls too, so it cannot accumulate against a collider.
	for index in get_slide_collision_count():
		var normal := get_slide_collision(index).get_normal()
		if absf(normal.y) < 0.7 and knockback_velocity.dot(normal) < 0:
			knockback_velocity = knockback_velocity.slide(normal)
	applied_knockback = knockback_velocity
	if stepped and not is_on_floor(): apply_floor_snap()
	var time_airborne := airborne_time
	if is_on_floor(): airborne_time = 0.0
	else: airborne_time += dt
	# Reconciliation replays the motor, without retriggering audiovisual events.
	if replaying:
		if is_on_floor(): last_safe = global_position; airborne_from_jump = false
		return
	if is_on_floor():
		if not grounded and falling_speed < -2:
			arena_match.audio.cue("land",global_position,human,self)
	var ground_speed := Vector2(global_position.x-previous_position.x,global_position.z-previous_position.z).length() / maxf(dt, 0.0001)
	var yaw_change := wrapf(yaw - previous_yaw, -PI, PI)
	var actual_motion := Basis(Vector3.UP,yaw).inverse()*(global_position-previous_position)
	local_motion=Vector2(actual_motion.x,actual_motion.z)
	measured_speed=ground_speed
	movement_pose.advance(local_motion,dt,is_on_floor(),jumped,charged,crouched,Arsenal.WEAPONS[equipped].animation_family,yaw_change,velocity.y)
	arena_match.audio.set_loop("walk_" + str(robot_id), "walk", global_position, is_on_floor() and ground_speed > 0.25, self == arena_match.local_robot, Locomotion.footstep_rate(ground_speed))
	if is_on_floor(): last_safe = global_position
	var lunar_contact := false
	if arena_match.map.config.get("lunar_surface_lethal",false):
		for index in get_slide_collision_count():
			var collider := get_slide_collision(index).get_collider()
			if collider != null and collider.get_meta("lethal_surface",false): lunar_contact = true
	if not predicted and (lunar_contact or global_position.y < arena_match.map.config.fall_boundary):
		if protection > 0: arena_match.spawn_robot(self)
		else:
			ah = 0
			arena_match.eliminate(self, null, "Fall off map")
		return
	body.rotation.y = yaw + character.forward_yaw
	if human:
		listener.position.y = 1.08 if crouched else character.eye_height
		listener.basis = Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch)
	previous_yaw = yaw
	var family: String = Arsenal.WEAPONS[equipped].animation_family
	crouch_idle_time = crouch_idle_time + dt if crouched and move_input.length() <= 0.1 else 0.0
	var upper_busy := reload_time>0 or spawn_reload_remaining>0 or (animation_lock>0 and anim_state.ends_with("/fire"))
	if spawn_reload_remaining > 0: pose("reload")
	elif jumped and not upper_busy: play_event(RobotClips.takeoff(family, measured_speed > 0.1, charged), 0.22)
	elif not grounded and is_on_floor():
		if not upper_busy: play_event(RobotClips.landing(falling_speed < -6.0 or time_airborne > 0.5), 0.28)
		airborne_from_jump = false
	elif was_crouched != crouched and family == "pistol" and not upper_busy:
		play_event("stand_to_kneel" if crouched else "kneel_to_stand", 0.3)
	elif animation_lock <= 0.0:
		if reload_time > 0: pose("reload")
		elif not is_on_floor(): pose("jump_loop" if airborne_from_jump or velocity.y >= -4.0 else "common/falling")
		elif measured_speed > 0.15: pose(RobotClips.travel(local_motion, measured_speed, crouched, family, yaw_change))
		elif absf(yaw_change) >= 0.10: play_event(RobotClips.turn(crouched, yaw_change), 0.3)
		else: pose(RobotClips.idle(crouched, wants_fire or wants_secondary or (brain != null and brain.target != null), family, crouch_idle_time > 0.9))
	update_recoil(dt)

func apply_recoil(degrees: float) -> void:
	recoil = minf(ArenaTuning.RECOIL_MAX_DEGREES, recoil + degrees)
	recoil_recovery_start = recoil
	recoil_recovery_remaining = ArenaTuning.RECOIL_RECOVERY_SECONDS

func update_recoil(dt: float) -> void:
	recoil_recovery_remaining = maxf(0.0, recoil_recovery_remaining - dt)
	recoil = recoil_recovery_start * recoil_recovery_remaining / ArenaTuning.RECOIL_RECOVERY_SECONDS

func try_step_up(dt: float) -> bool:
	var travel := Vector3(velocity.x, 0.0, velocity.z) * dt
	var height:=step_height_for(travel)
	if height<=0:return false
	move_and_collide(Vector3.UP * height)
	return true

func walk_motion_clear(travel: Vector3) -> bool:
	var contact:=KinematicCollision3D.new()
	if not test_move(global_transform,travel,contact):return true
	# Sliding up a walkable apron is ordinary grounded movement.
	return contact.get_normal().y>=cos(floor_max_angle)

func can_step_up(travel: Vector3) -> bool:
	return step_height_for(travel)>0

func walk_or_step_motion_clear(travel: Vector3) -> bool:
	var contact := KinematicCollision3D.new()
	if not test_move(global_transform, travel, contact): return true
	if contact.get_normal().y >= cos(floor_max_angle): return true
	# The failed walking sweep already identified this obstruction. Reuse it
	# instead of querying the identical capsule motion again for the step test.
	return step_height_for(travel, contact) > 0.0

func step_height_for(travel: Vector3, contact: KinematicCollision3D = null) -> float:
	if travel.length_squared() < 0.0001: return 0.0
	var obstacle := contact
	if obstacle == null:
		obstacle = KinematicCollision3D.new()
		if not test_move(global_transform, travel, obstacle): return 0.0
	var collider := obstacle.get_collider()
	if not (collider is CollisionObject3D) or not (collider.collision_layer & 1): return 0.0
	# A shallow architectural threshold needs less lift than the maximum step.
	# Use the lowest clear lift so the robot also clears a low doorway lintel.
	for height in [0.1,0.15,0.2,0.25,ArenaTuning.STEP_HEIGHT]:
		if height>ArenaTuning.STEP_HEIGHT:continue
		var lift: Vector3=Vector3.UP*height
		if test_move(global_transform,lift):continue
		var raised:=global_transform.translated(lift)
		if test_move(raised,travel):continue
		if not test_move(raised.translated(travel),-lift):continue
		return height
	return 0.0

func start_reload() -> void:
	if not can_act() or reload_time > 0 or equipped == "pistol" or packs == 0: return
	if loaded >= Arsenal.WEAPONS[equipped].capacity: return
	reload_time = 2.0
	streaming = false
	arena_match.combat.stop_contact(self)
	arena_match.audio.cue("reload", global_position,human,self)

func handle_empty_weapon() -> void:
	if equipped == "pistol" or loaded > 0: return
	start_reload()
	if arena_match.match_type=="GUNGAME": return
	if reload_time <= 0.0:
		var fallback := previous_weapon if previous_weapon != equipped and has_ammo(previous_weapon) else "pistol"
		equip(fallback)
		if equipped != "pistol" and loaded <= 0: start_reload()

func can_take_damage(attacker) -> bool:
	if not alive or protection > 0 or arena_match.phase != "Active": return false
	if repair != null and repair.elapsed >= 1: return false
	if attacker != null and attacker != self and not enemy(attacker): return false
	if attacker != null and (not attacker.alive or attacker.protection > 0): return false
	return true

func apply_knockback(impulse: Vector3) -> void:
	if repair != null and repair.elapsed >= 1.0: return
	knockback_velocity = (knockback_velocity + Vector3(impulse.x, 0, impulse.z)).limit_length(ArenaTuning.KNOCKBACK_MAX_SPEED)
	if impulse.y > 0:
		velocity.y = minf(ArenaTuning.KNOCKBACK_MAX_SPEED, maxf(velocity.y, impulse.y))
		jump_charge = 0.0
		jump_held = false

func tick_repair_motion(dt: float) -> void:
	update_recoil(dt)
	if repair.elapsed >= 1.0:
		velocity = Vector3.ZERO
		knockback_velocity = Vector3.ZERO
		applied_knockback = Vector3.ZERO
		return
	# Ignore voluntary movement, but retain impact push during shield activation.
	knockback_velocity = knockback_velocity.move_toward(Vector3.ZERO, ArenaTuning.KNOCKBACK_DRAG * dt)
	velocity.x = knockback_velocity.x
	velocity.z = knockback_velocity.z
	if not is_on_floor(): velocity.y -= arena_match.gravity * dt
	applied_knockback = knockback_velocity
	move_and_slide()

func hit(amount: float, attacker, cause: String, impulse := Vector3.ZERO, contact: Dictionary = {}) -> bool:
	if amount <= 0 or not can_take_damage(attacker): return false
	last_hit_robot_id=attacker.robot_id if attacker!=null else -1
	last_hit_weapon=cause
	if attacker != null and not attacker.human: amount *= BotDifficulty.profile(arena_match.difficulty).damage
	if attacker != null and attacker != self:
		if not contributors.has(attacker.robot_id): contributors[attacker.robot_id] = []
		contributors[attacker.robot_id].append([arena_match.elapsed, amount])
	var split := Arsenal.shield_split(amount, sh)
	ah = maxf(0, ah - split.x)
	sh = maxf(0, sh - split.y)
	if arena_match.callouts and split.x >= 20.0 and ah > 0:
		arena_match.callouts.publish("Armor hit.",display_name,team,false,global_position,-1,robot_id)
	hit_flash = 0.2
	if attacker != null and attacker != self and arena_match.online:
		arena_match.present({"kind":"damage","victim":robot_id,"attacker":attacker.robot_id,"source":attacker.eye(),"amount":amount,"weapon":cause})
	EnergySurface.update(self)
	if attacker != null and attacker != self and attacker == arena_match.local_robot:
		arena_match.hit_marker = 0.24
	if self == arena_match.local_robot and attacker != null and attacker != self:
		arena_match.damage_taken.emit(attacker.eye(), amount)
	if ah <= 0:
		arena_match.eliminate(self, attacker if attacker != self else null, cause, contact)
	elif impulse.length_squared() > 0:
		apply_knockback(impulse)
	# The next physics pose sample applies the reaction. Its initial weight is
	# zero; resampling here repeats animation and collider updates for every hit.
	return true

func snapshot() -> Dictionary:
	return {"id":robot_id,"name":display_name,"team":team,"head":head,"upper_body":upper_body,"tint":tint.to_html(),"human":human,
		"p":[position.x,position.y,position.z],"yaw":yaw,"pitch":pitch,"ah":ah,"ep":ep,"sh":sh,
		"protection":protection,"alive":alive,"kills":kills,"assists":assists,"deaths":deaths,"captures":captures,
		"reached":reached,"weapon":equipped,"pickup":pickup_weapon,"loaded":loaded,"packs":packs,"reload":reload_time,"owned_weapons":owned_weapons.duplicate(),
		"ammo_inventory":ammo_inventory.duplicate(true),"previous_weapon":previous_weapon}


func network_state() -> Dictionary:
	var state := snapshot()
	state["voice_variant"] = voice_variant
	state["secondary"] = armor_secondary.to_html()
	state["emote"] = account_emote
	state["v"] = velocity
	state["shots"] = network_shots
	state["trace"] = network_trace_end
	state["barrel"] = barrel
	state["secondary_fire"] = wants_secondary
	state["rocket_lock_target"] = rocket_lock_target
	state["rocket_lock_progress"] = rocket_lock_progress
	state["beam"] = weapon_vfx.beam_target
	state["hit_weapon"] = last_hit_weapon
	state["contact"] = network_contact
	state["grounded"] = is_on_floor()
	state["knockback"] = knockback_velocity
	state["applied"] = applied_knockback
	state["spawn"] = spawn_remaining
	state["spawn_reload"] = spawn_reload_remaining
	state["spawn_reload_duration"] = spawn_reload_duration
	state["slow_remaining"] = slow_remaining
	state["slow_multiplier"] = slow_multiplier
	state["spawn_id"] = spawn_fixture.get("id", "")
	state["repair_id"] = repair.id if repair != null else ""
	state["repair_elapsed"] = repair.elapsed if repair != null else 0.0
	state["carry"] = carrying
	state["pose"] = anim_state
	state["visible"] = visible
	state["motor"] = {}
	state["stride"] = {}
	for key in ["phase","turn_phase","key","state_time","airborne","airborne_from_jump","landed","air_time","takeoff","landing_clip"]:
		state.stride[key] = movement_pose.get(key)
	for key in ["ramp_stage","ramp_target","ramp_velocity","ramp_time","coyote_time","jump_buffer","jump_charge","jump_release","jump_held","crouched","lift_target","lift_speed","lift_from_pad","shield_time","portal_lock","animation_lock","airborne_time","airborne_from_jump","streaming","recoil","recoil_recovery_remaining","recoil_recovery_start","cooldown","hit_flash"]:
		state.motor[key] = get(key)
	return state

func restore_network(state: Dictionary, local := false) -> void:
	voice_variant=int(state.get("voice_variant",voice_variant))
	var life_changed: bool = alive != state.alive
	var shot_changed: bool = network_shots != state.shots
	position = Vector3(state.p[0],state.p[1],state.p[2])
	velocity = state.v
	knockback_velocity = state.knockback
	applied_knockback = state.applied
	for key in ["yaw","pitch","ah","ep","sh","protection","alive","kills","assists","deaths","captures","reached"]: set(key,state[key])
	spawn_remaining = state.spawn
	spawn_reload_remaining = float(state.get("spawn_reload",0))
	spawn_reload_duration = float(state.get("spawn_reload_duration",2.0))
	slow_remaining = float(state.get("slow_remaining",0))
	slow_multiplier = float(state.get("slow_multiplier",1))
	spawn_fixture = {}
	for fixture in arena_match.map.spawns:
		if fixture.id == state.spawn_id: spawn_fixture = fixture; break
	repair = arena_match.map.fixture_by_id(state.repair_id) if state.repair_id != "" else null
	if repair != null: repair.elapsed = state.repair_elapsed
	carrying = state.carry
	owned_weapons.assign(state.get("owned_weapons",["pistol"]))
	ammo_inventory=state.get("ammo_inventory",{}).duplicate(true)
	pickup_weapon = state.pickup
	if equipped != state.weapon: equip(state.weapon)
	if not state.has("ammo_inventory"):
		loaded=state.loaded
		packs=state.packs
	previous_weapon=state.get("previous_weapon","pistol")
	reload_time = state.reload
	for key in state.motor: set(key,state.motor[key])
	for key in state.get("stride",{}): movement_pose.set(key,state.stride[key])
	wants_secondary = state.secondary_fire
	rocket_lock_target = int(state.get("rocket_lock_target", -1))
	rocket_lock_progress = float(state.get("rocket_lock_progress", 0.0))
	barrel = state.barrel
	weapon_vfx.beam_target = state.beam
	network_contact = state.get("contact",Vector3.INF)
	network_grounded = state.get("grounded",false)
	if shot_changed and network_initialized and not arena_match.replicating and state.shots > network_shots and alive and (not local or Time.get_ticks_msec()-predicted_shot_time > 200):
		barrel = maxi(0,state.barrel-1)
		weapon_vfx.begin_shot()
		weapon_vfx.shot()
		arena_match.audio.cue(equipped,muzzle(),self == arena_match.local_robot,self)
		if equipped in ["pistol","rifle","minigun"]: arena_match.effects.beam(weapon_vfx.origin(),state.trace,Color("ffd295"),0.009)
		barrel = state.barrel
	network_shots = state.shots
	if not network_initialized: network_presented_shot = state.shots
	network_initialized = true
	last_hit_weapon=str(state.get("hit_weapon",last_hit_weapon))
	EnergySurface.update(self)
	if life_changed:
		Assets.paint(body,tint,armor_secondary,head,not alive,upper_body)
		Assets.paint(gun,tint,armor_secondary,head,not alive,upper_body)
	body_capsule.height = 1.18 if crouched else 1.72
	body_shape.position.y = body_capsule.height * 0.5
	body.rotation.y = yaw + character.forward_yaw
	visible = state.visible
	collision_layer = 2 if alive else 0
	if not local or not can_act(): pose(state.pose)
	if spawn_reload_remaining > 0 and anim_state == "pistol/reload":
		animator.speed_scale = animator.current_animation_length / spawn_reload_duration
		animator.seek((spawn_reload_duration-spawn_reload_remaining)*animator.speed_scale,true)
