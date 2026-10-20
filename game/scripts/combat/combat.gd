class_name ArenaCombat
extends RefCounted
var game
var shape_cast: ShapeCast3D
var shape_exclusions: Array = []
var beam_shapes: Dictionary = {}
var projectile_bounds := BoxShape3D.new()
var native_clear_rays := false
static var profile_queries := false
static var query_stats: Dictionary = {}

static func record_query(kind: String, started: int) -> void:
	var elapsed := Time.get_ticks_usec()-started
	query_stats[kind+"_calls"] = int(query_stats.get(kind+"_calls",0))+1
	query_stats[kind+"_us"] = int(query_stats.get(kind+"_us",0))+elapsed
	query_stats[kind+"_max_us"] = maxi(int(query_stats.get(kind+"_max_us",0)),elapsed)
func _init(owner): game = owner

func sweep(shape: Shape3D, from: Transform3D, motion: Vector3, exclude: Array = [], mask := 5) -> Dictionary:
	var started := Time.get_ticks_usec() if profile_queries else 0
	if not is_instance_valid(shape_cast):
		shape_cast = ShapeCast3D.new()
		shape_cast.enabled = false
		shape_cast.collision_mask = 5
		shape_cast.margin = 0.001
		shape_cast.max_results = 1
		game.add_child(shape_cast)
		shape_exclusions.clear()
	var expanded := exclude.duplicate()
	for robot in game.robots:
		if robot.get_rid() in exclude or not robot.alive:
			expanded.append_array(robot.hit_rids)
	# Compound projectile hulls and repeated beam queries commonly reuse the
	# same shooter. Recheck live RIDs each call, but only rebuild engine exceptions
	# when they change (including death, respawn and equipped collider changes).
	if expanded != shape_exclusions:
		shape_cast.clear_exceptions()
		for rid in expanded: shape_cast.add_exception_rid(rid)
		shape_exclusions = expanded
	shape_cast.shape = shape
	shape_cast.collision_mask = mask
	shape_cast.global_transform = from
	shape_cast.target_position = from.basis.inverse()*motion
	var cast_started := Time.get_ticks_usec() if profile_queries else 0
	shape_cast.force_shapecast_update()
	if profile_queries: record_query("shape_cast",cast_started)
	if profile_queries: record_query("shape",started)
	if not shape_cast.is_colliding(): return {}
	var collider = shape_cast.get_collider(0)
	if not is_instance_valid(collider): return {}
	var result := {"collider":collider, "position":shape_cast.get_collision_point(0), "normal":shape_cast.get_collision_normal(0), "fraction":shape_cast.get_closest_collision_safe_fraction()}
	if collider.has_meta("robot"):
		result.hit_object = collider
		result.hit_region = collider.get_meta("hit_region", "body")
		result.collider = collider.get_meta("robot")
	return result

func projectile_hit(projectile: Node3D, motion: Vector3, exclude: Array = []) -> Dictionary:
	var components := ProjectileCollision.shapes(projectile.weapon)
	var poses: Array[Transform3D] = []
	var bounds := AABB()
	for component in components:
		var pose: Transform3D = projectile.global_transform*ProjectileCollision.local_pose(projectile,component)
		poses.append(pose)
		if components.size() > 1:
			var center: Vector3 = pose*component.bounds_center
			var scale := pose.basis.get_scale().abs()
			var radius: float = component.bounds_radius*maxf(scale.x,maxf(scale.y,scale.z))
			var part := AABB(center-Vector3.ONE*radius,Vector3.ONE*radius*2.0)
			bounds = part if poses.size() == 1 else bounds.merge(part)
	# Empty space needs one conservative sweep instead of every authored hull.
	# Contact still resolves against the exact components, including animated poses.
	if components.size() > 1:
		projectile_bounds.size = bounds.size
		if sweep(projectile_bounds,Transform3D(Basis.IDENTITY,bounds.get_center()),motion,exclude).is_empty(): return {}
	var closest := {}
	for index in components.size():
		var hit := sweep(components[index].shape, poses[index], motion, exclude)
		if not hit.is_empty() and (closest.is_empty() or hit.fraction < closest.fraction): closest = hit
	if not closest.is_empty(): closest.center = projectile.global_position + motion*closest.fraction
	return closest

func beam_hit(origin: Vector3, target: Vector3, radius: float, exclude: Array = []) -> Dictionary:
	if not beam_shapes.has(radius):
		var sphere := SphereShape3D.new()
		sphere.radius = radius
		beam_shapes[radius] = sphere
	return sweep(beam_shapes[radius],Transform3D(Basis.IDENTITY,origin),target-origin,exclude)

func attack_hit(robot, origin: Vector3, direction: Vector3, reach: float) -> Dictionary:
	var weapon: String = robot.equipped
	var excluded := [robot.get_rid()]
	if Arsenal.orb_secondary(weapon) and not robot.wants_secondary:
		return beam_hit(origin,origin+direction*reach,CombatStream.FLAME_OUTER_END_RADIUS if weapon == "flamethrower" else 0.02,excluded)
	if weapon in ["pistol","rifle","minigun"]: return ray(origin,origin+direction*reach,excluded)
	var basis := Basis.looking_at(direction,Vector3.RIGHT if absf(direction.y)>.99 else Vector3.UP)
	var model_basis := Basis(Vector3.UP,PI) if weapon == "rocket_launcher" else Basis.IDENTITY
	var closest := {}
	for component in ProjectileCollision.shapes(weapon):
		var hit := sweep(component.shape,Transform3D(basis,origin)*Transform3D(model_basis,Vector3.ZERO)*component.pose,direction*reach,excluded)
		if not hit.is_empty() and (closest.is_empty() or hit.fraction < closest.fraction): closest=hit
	return closest

func ray(from: Vector3, to: Vector3, exclude: Array = [], mask := 5) -> Dictionary:
	var started := Time.get_ticks_usec() if profile_queries else 0
	var excluded: Array[RID] = []
	excluded.assign(exclude)
	if mask != 1:
		for r in game.robots:
			if r.get_rid() in excluded or not r.alive:
				excluded.append_array(r.hit_rids)
	var query := PhysicsRayQueryParameters3D.create(from, to, mask, excluded)
	query.hit_from_inside = true
	var result: Dictionary = game.get_world_3d().direct_space_state.intersect_ray(query)
	if profile_queries: record_query("ray",started)
	if not result.is_empty() and result.collider.has_meta("robot"):
		result.hit_object = result.collider
		result.hit_region = result.collider.get_meta("hit_region", "body")
		result.collider = result.collider.get_meta("robot")
	return result

func clear(from: Vector3, to: Vector3) -> bool:
	if native_clear_rays:
		var started := Time.get_ticks_usec() if profile_queries else 0
		var space = game.get_world_3d().direct_space_state
		var hit: bool = space.ray_intersects(from,to,1,true,true)
		if profile_queries: record_query("ray",started)
		return not hit
	return ray(from, to, [], 1).is_empty()

func firing_lane(robot, point: Vector3, secondary: bool, origin := Vector3.INF, flight_direction := Vector3.INF) -> bool:
	if origin==Vector3.INF: origin=robot.muzzle()
	var weapon: String=robot.equipped
	if weapon=="grenade_launcher": return grenade_lane(origin,point,flight_direction)
	if not clear(origin,point): return false
	if weapon in ["pistol","rifle","minigun"]: return true
	var direction := (point-origin).normalized()
	var basis := Basis.looking_at(direction,Vector3.RIGHT if absf(direction.y)>.99 else Vector3.UP)
	if Arsenal.orb_secondary(weapon) and not secondary:
		var radius := 0.02 if weapon=="lightning_gun" else 0.12
		if not beam_shapes.has(radius):
			var sphere := SphereShape3D.new();sphere.radius=radius;beam_shapes[radius]=sphere
		return sweep(beam_shapes[radius],Transform3D(Basis.IDENTITY,origin),point-origin,[],1).is_empty()
	var model_basis := Basis(Vector3.UP,PI) if weapon=="rocket_launcher" else Basis.IDENTITY
	for component in ProjectileCollision.shapes(weapon):
		if not sweep(component.shape,Transform3D(basis,origin)*Transform3D(model_basis,Vector3.ZERO)*component.pose,point-origin,[],1).is_empty(): return false
	return true

func grenade_lane(origin: Vector3, point: Vector3, direction := Vector3.INF) -> bool:
	var profile: Dictionary=Arsenal.WEAPONS.grenade_launcher
	var speed: float=profile.projectile_speed
	var gravity: float=profile.projectile_gravity*game.gravity/ArenaTuning.GRAVITY
	if direction==Vector3.INF: direction=BallisticProjectile.launch_direction(origin,point,speed,gravity)
	if direction==Vector3.ZERO: return false
	var horizontal := Vector2(direction.x,direction.z).length()*speed
	if horizontal<.01: return false
	var duration := Vector2(point.x-origin.x,point.z-origin.z).length()/horizontal
	# A conservative native bounding sphere includes the tumbling grenade.
	var radius := 0.0
	for component in ProjectileCollision.shapes("grenade_launcher"):
		radius=maxf(radius,(component.pose*component.bounds_center).length()+component.bounds_radius)
	if not beam_shapes.has(radius):
		var sphere := SphereShape3D.new();sphere.radius=radius;beam_shapes[radius]=sphere
	var previous := origin
	var steps := clampi(ceili(duration/.18),1,24)
	for step in range(1,steps+1):
		var time := duration*step/steps
		var next := origin+direction*speed*time-Vector3.UP*gravity*time*time*.5
		if not clear(previous,next) or not sweep(beam_shapes[radius],Transform3D(Basis.IDENTITY,previous),next-previous,[],1).is_empty(): return false
		previous=next
	return true

func update_rocket_lock(robot, dt: float) -> void:
	var target: ArenaRobot
	if robot.equipped == "rocket_launcher" and robot.wants_secondary:
		target = damageable_target(robot)
	if target == null:
		robot.rocket_lock_target = -1
		robot.rocket_lock_progress = 0.0
		return
	if robot.rocket_lock_target != target.robot_id:
		robot.rocket_lock_target = target.robot_id
		robot.rocket_lock_progress = 0.0
	robot.rocket_lock_progress = minf(1.0, robot.rocket_lock_progress + dt / float(Arsenal.WEAPONS.rocket_launcher.lock_seconds))

func trigger(robot, dt: float) -> void:
	if robot.reload_time > 0: return
	var weapon: String = robot.equipped
	var profile: Dictionary = Arsenal.WEAPONS[weapon]
	var orb: bool = Arsenal.orb_secondary(weapon) and robot.wants_secondary
	var continuous: bool = Arsenal.orb_secondary(weapon) and not orb
	# An exhausted gun falls back even if the trigger was released after its last shot.
	# Keep a funded stream or scheduled shot alive until its final event/interval.
	if weapon != "pistol" and robot.loaded<=0 and robot.weapon_vfx.pending.is_empty() and (not robot.streaming or (not robot.wants_fire and not orb)):
		robot.handle_empty_weapon()
		return
	if not robot.wants_fire and not orb:
		robot.streaming = false
		robot.stream_time = 0
		robot.stream_accuracy_valid = false
		stop_contact(robot)
		return
	if not continuous and robot.streaming:
		robot.streaming = false
		robot.stream_time = 0
		robot.stream_accuracy_valid = false
		stop_contact(robot)
	if continuous:
		if not robot.streaming:
			if robot.loaded <= 0:
				stop_contact(robot)
				robot.handle_empty_weapon()
				return
			robot.loaded -= 1
			robot.stream_time = profile.interval
			robot.streaming = true
			roll_stream_accuracy(robot)
			robot.stream_accuracy_time = 1.0
			robot.play_event("fire", 0.18)
			robot.apply_recoil(profile.recoil)
		robot.stream_time -= dt
		if robot.stream_time <= 0:
			if robot.loaded <= 0:
				robot.streaming = false
				stop_contact(robot)
				robot.handle_empty_weapon()
				return
			robot.loaded -= 1
			robot.stream_time += profile.interval
		robot.stream_accuracy_time -= dt
		if robot.stream_accuracy_time <= 0:
			robot.stream_accuracy_time += 1.0
			roll_stream_accuracy(robot)
		var damage_ticked := false
		while robot.stream_damage_time <= 0:
			damage_ticked = true
			robot.stream_damage_time += profile.damage_tick
			if weapon == "lightning_gun":
				trace(robot, profile.range, profile.damage * profile.damage_tick, Color("82baff"), false)
			else:
				flame(robot)
		if weapon == "lightning_gun":
			if not damage_ticked: trace(robot, profile.range, 0.0, Color("82baff"), false)
		else:
			update_flame_contact(robot)
		return
	# Complete the last shot's scheduled launch/casing before changing its rig.
	if weapon != "pistol" and robot.loaded <= 0 and robot.weapon_vfx.pending.is_empty():
		robot.handle_empty_weapon()
		return
	if robot.cooldown > 0: return
	if weapon != "pistol" and robot.loaded <= 0:
		robot.handle_empty_weapon()
		return
	robot.cooldown += Arsenal.mode_value(weapon,"interval",robot.wants_secondary)
	if weapon != "pistol": robot.loaded -= 1
	var scoped: bool = weapon == "rifle" and robot.wants_secondary
	robot.weapon_vfx.begin_shot()
	var report_voice: ArenaVoice
	if game.audio.cue(Arsenal.shot_cue(weapon, orb), robot.muzzle(), robot == game.local_robot, robot):
		report_voice = game.audio.last_started_voice
	if weapon in ["pistol", "rifle", "minigun"]:
		trace(robot, Arsenal.mode_value(weapon,"range",scoped), Arsenal.mode_value(weapon,"damage",scoped), Color("ffd295"), scoped)
	else:
		if weapon == "rocket_launcher":
			# Capture the authoritative lock at trigger time, not at the delayed muzzle event.
			var locked_id: int = robot.rocket_lock_target if robot.wants_secondary and robot.rocket_lock_progress >= 1.0 else -1
			var scoped_shot: bool = robot.wants_secondary
			robot.weapon_vfx.schedule(1.0 / 30.0, func(): launch(robot, weapon, report_voice, locked_id, scoped_shot))
		else: launch(robot, weapon)
	robot.apply_recoil(1.0 if scoped else profile.recoil)
	robot.weapon_vfx.shot()
	robot.barrel += 1
	robot.network_shots += 1
	if game is ArenaMatch: game.present({"kind":"shot","robot":robot.robot_id,"number":robot.network_shots,"weapon":weapon,"secondary":robot.wants_secondary,"barrel":robot.barrel-1,"trace":robot.network_trace_end})
	for other in game.robots:
		if other.brain and other != robot and other.position.distance_to(robot.position) < 28:
			other.brain.hear(robot.position)

func launch(robot, weapon: String, report_voice: ArenaVoice = null, locked_id := -1, scoped_shot := false):
	if weapon in ["flak_cannon","bio_rifle","grenade_launcher"]:
		var profile: Dictionary = Arsenal.WEAPONS[weapon]
		var direction := shot_direction(robot)
		for pellet in int(profile.get("pellets",1)):
			var shot := direction
			if int(profile.get("pellets",1))>1:
				var basis := Basis.looking_at(direction,Vector3.UP)
				var spread := tan(deg_to_rad(float(profile.get("spread_degrees",0))))
				var angle: float = game.rng.randf()*TAU
				var radial: float = sqrt(game.rng.randf())*spread
				shot=(direction+basis.x*cos(angle)*radial+basis.y*sin(angle)*radial).normalized()
			BallisticProjectile.launch(game,robot,weapon,robot.muzzle(),shot,profile)
		return
	var projectile := ArenaProjectile.new()
	projectile.game = game
	projectile.shooter = robot
	projectile.weapon = weapon
	if weapon == "rocket_launcher" and locked_id >= 0:
		for target in game.robots:
			if target.robot_id == locked_id and target.can_take_damage(robot):
				projectile.homing_target = weakref(target)
				break
	if weapon == "rocket_launcher" and report_voice != null:
		projectile.launch_voice = weakref(report_voice)
		projectile.launch_voice_serial = report_voice.serial
	projectile.direction = shot_direction(robot, Arsenal.projectile_range(weapon))
	projectile.speed = Arsenal.mode_value(weapon,"projectile_speed",Arsenal.orb_secondary(weapon) or scoped_shot)
	game.add_child(projectile)
	projectile.global_position = robot.muzzle()
	projectile.orient_to_flight(projectile.direction)
	projectile.configure_presentation()
	if weapon in ["emp_gun", "rocket_launcher"]:
		robot.apply_knockback(Knockback.impulse(-projectile.direction, ArenaTuning.WEAPON_RECOIL_SPEED, 0))

func accuracy_error(robot) -> Vector2:
	if robot.human: return Vector2.ZERO
	var hit: bool = game.rng.randf() <= BotDifficulty.profile(game.difficulty).accuracy
	var error := Vector2.ZERO if hit else Vector2(deg_to_rad(5),game.rng.randf()*TAU)
	BotDifficulty.trace("shot_roll",{"robot":robot.robot_id,"weapon":robot.equipped,"hit":hit,"azimuth":error.y})
	return error

func roll_stream_accuracy(robot) -> void:
	robot.stream_accuracy_error = accuracy_error(robot)
	robot.stream_accuracy_valid = true

func shot_direction(robot, reach := -1.0, continuous := false) -> Vector3:
	if reach < 0: reach = Arsenal.WEAPONS[robot.equipped].range
	var direction: Vector3 = (aim_target(robot, reach) - robot.muzzle()).normalized()
	if not robot.human and robot.equipped=="grenade_launcher": direction=robot.aim_direction()
	var error: Vector2
	if continuous and robot.get("streaming") == true:
		if not robot.stream_accuracy_valid: roll_stream_accuracy(robot)
		error = robot.stream_accuracy_error
	else: error = accuracy_error(robot)
	if error.x > 0:
		var tangent := direction.cross(Vector3.UP).normalized()
		if tangent.length() < 0.1: tangent = Vector3.RIGHT
		var axis := tangent.rotated(direction,error.y)
		direction = direction.rotated(axis,error.x)
	return direction.normalized()

func aim_target(robot, reach: float) -> Vector3:
	var origin: Vector3 = robot.eye()
	var direction: Vector3 = robot.aim_direction()
	# The local crosshair is the camera's center ray, including the shoulder offset.
	if robot.human and robot == game.local_robot and is_instance_valid(game.camera):
		origin = game.camera.global_position
		direction = -game.camera.global_basis.z.normalized()
	var target := origin + direction * (reach + origin.distance_to(robot.eye()))
	var sight := ray(origin, target, [robot.get_rid()])
	return sight.position if not sight.is_empty() else target

func has_damageable_target(robot) -> bool:
	return damageable_target(robot) != null

func damageable_target(robot) -> ArenaRobot:
	if not robot.can_act() or robot.reload_time > 0: return null
	if robot.equipped != "pistol" and robot.loaded <= 0: return null
	var reach: float = Arsenal.WEAPONS[robot.equipped].range
	if robot.wants_secondary: reach = Arsenal.mode_value(robot.equipped,"range",true)
	var origin: Vector3 = robot.muzzle()
	var direction: Vector3 = (aim_target(robot, reach) - origin).normalized()
	var hit := attack_hit(robot,origin,direction,reach)
	return hit.collider if not hit.is_empty() and hit.collider is ArenaRobot and hit.collider.can_take_damage(robot) else null

func flame_endpoint(robot, origin: Vector3) -> Vector3:
	var muzzle: Vector3 = robot.muzzle()
	var direction := shot_direction(robot,15.0,true) if robot.get("streaming") == true else (aim_target(robot,15.0)-muzzle).normalized()
	var target := muzzle + direction * 15.0
	var hit := beam_hit(muzzle,target,CombatStream.FLAME_OUTER_END_RADIUS,[robot.get_rid()])
	if not hit.is_empty(): target = hit.position
	return target


func trace(robot, reach: float, damage: float, color: Color, scoped: bool) -> void:
	var direction := shot_direction(robot, reach, robot.streaming and robot.equipped == "lightning_gun")
	var origin: Vector3 = robot.muzzle()
	var target := origin + direction * reach
	var hit := beam_hit(origin,target,0.02,[robot.get_rid()]) if robot.equipped == "lightning_gun" else ray(origin, target, [robot.get_rid()])
	if not hit.is_empty():
		target = hit.position
		var shielded: bool = hit.collider is ArenaRobot and (hit.collider.sh > 0 or hit.collider.protection > 0)
		if hit.collider is ArenaRobot and damage > 0:
			var victim = hit.collider
			var headshot: bool = scoped and hit.get("hit_region", "body") == "head"
			if headshot: damage = float(Arsenal.WEAPONS.rifle.headshot_damage)
			victim.hit(damage, robot, "rifle_headshot" if headshot else robot.equipped)
		if robot.equipped != "lightning_gun":
			game.effects.impact(target, hit.normal, shielded, null if hit.collider is ArenaRobot else hit.collider, hit.collider is ArenaRobot)
		if robot.equipped != "lightning_gun": play_impact(robot.equipped, target, hit.collider, shielded, robot)
	if robot.equipped == "lightning_gun":
		update_contact(robot, hit)
		robot.weapon_vfx.beam_target = target
		robot.weapon_vfx.beam_hit = hit
	else:
		robot.network_trace_end = target
		game.effects.beam(robot.weapon_vfx.origin(), target, color, 0.009)

func invulnerable(collider) -> bool:
	return collider is ArenaRobot and (collider.protection > 0 or (collider.repair != null and collider.repair.elapsed >= 1))

func stop_contact(robot) -> void:
	robot.network_contact = Vector3.INF
	game.audio.set_loop("contact_" + str(robot.robot_id), "hit_" + robot.equipped, Vector3.ZERO, false)

func update_contact(robot, hit: Dictionary) -> void:
	robot.network_contact = hit.position if not hit.is_empty() and not invulnerable(hit.collider) else Vector3.INF
	var key := "contact_" + str(robot.robot_id)
	if hit.is_empty() or invulnerable(hit.collider):
		game.audio.set_loop(key, "hit_" + robot.equipped, Vector3.ZERO, false)
	else:
		game.audio.set_loop(key, "hit_" + robot.equipped, hit.position, true)

func update_flame_contact(robot) -> void:
	var origin: Vector3 = robot.muzzle()
	var direction := shot_direction(robot,15.0,true)
	update_contact(robot,beam_hit(origin,origin+direction*15.0,CombatStream.FLAME_OUTER_END_RADIUS,[robot.get_rid()]))

func play_impact(weapon: String, point: Vector3, collider, _shielded: bool, shooter, secondary := false) -> void:
	var id := ""
	if weapon in ["lightning_gun", "flamethrower"] and invulnerable(collider): return
	if invulnerable(collider): id = "hit_shield"
	elif secondary and Arsenal.orb_secondary(weapon): id = "hit_" + weapon + "_secondary"
	elif weapon in ["pistol", "rifle", "minigun", "rocket_launcher", "emp_gun", "lightning_gun"]: id = "hit_" + weapon
	if id.is_empty(): return
	var emitter: Node3D = collider if collider is ArenaRobot else shooter
	game.audio.cue(id, point, false, emitter)

func flame(robot) -> void:
	var origin: Vector3 = robot.muzzle()
	var direction := shot_direction(robot,15.0,true)
	var direct: Array = []
	var amounts: Dictionary = {}
	var hit := beam_hit(origin,origin+direction*15.0,CombatStream.FLAME_OUTER_END_RADIUS,[robot.get_rid()])
	if not hit.is_empty() and hit.collider is ArenaRobot:
		var victim: ArenaRobot = hit.collider
		direct.append(victim)
		var distance := origin.distance_to(hit.position)
		var tick_damage: float = Arsenal.WEAPONS.flamethrower.damage * Arsenal.WEAPONS.flamethrower.get("damage_tick", 0.1)
		var falloff_width: float = Arsenal.WEAPONS.flamethrower.range-Arsenal.WEAPONS.flamethrower.full_damage_range
		amounts[victim] = tick_damage * clampf((Arsenal.WEAPONS.flamethrower.range-distance)/falloff_width,0.0,1.0)
	for victim in direct:
		for other in game.robots:
			if other in direct or other == robot or origin.distance_to(other.eye()) > 15: continue
			var distance: float = victim.position.distance_to(other.position)
			if distance <= 5 and clear(victim.eye(), other.eye()):
				var splash_tick: float = Arsenal.WEAPONS.flamethrower.splash_damage
				amounts[other] = maxf(amounts.get(other, 0), splash_tick * clampf((6.0 - distance) / 5.0, 0.0, 1.0))
	for victim in amounts:
		victim.hit(amounts[victim], robot, "flamethrower")
