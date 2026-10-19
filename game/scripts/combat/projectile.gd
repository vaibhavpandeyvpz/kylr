class_name ArenaProjectile
extends Node3D
var game
var shooter
var weapon := "rocket_launcher"
var direction := Vector3.FORWARD
const DEFAULT_SPEED := 15.0
var speed := DEFAULT_SPEED
var distance := 0.0
var age := 0.0
var fall := 0.0
var visual: Node3D
var energy_material: ShaderMaterial
var launch_voice: WeakRef
var launch_voice_serial := 0
var view_launch_offset := Vector3.ZERO
var view_convergence_distance := 1.0
var view_start_distance := 0.0
var presentation_configured := false
var homing_target: WeakRef
var warhead: Node3D

static func steer_direction(current: Vector3, desired: Vector3, travel: float, radius: float) -> Vector3:
	if desired.length_squared() < 0.000001: return current
	var goal := desired.normalized()
	var angle := current.angle_to(goal)
	if angle < 0.000001: return goal
	var axis := current.cross(goal).normalized()
	if axis.length_squared() < 0.001:
		axis = current.cross(Vector3.UP if absf(current.y) < 0.99 else Vector3.RIGHT).normalized()
	return current.rotated(axis, minf(angle, travel / maxf(radius, 0.001))).normalized()

func steer_homing(dt: float) -> bool:
	if homing_target == null: return false
	var target = homing_target.get_ref()
	if not is_instance_valid(target) or not target.alive or target.spawn_remaining > 0:
		homing_target = null
		return false
	direction = steer_direction(direction, target.global_position + Vector3.UP - global_position, speed * dt, float(Arsenal.WEAPONS.rocket_launcher.turn_radius))
	return true

func stop_launch_report() -> void:
	if launch_voice == null: return
	var voice: ArenaVoice = launch_voice.get_ref()
	if voice != null and voice.active and voice.serial == launch_voice_serial:
		voice.stop()

func _ready():
	add_to_group("dodge_projectiles")
	if weapon == "rocket_launcher":
		visual = Assets.model("weapons", weapon, "_rocket")
		add_child(visual)
		warhead = Assets.socket(visual, "Warhead")
		# Imported rocket geometry points +Z; the flight node points -Z.
		visual.rotation.y = PI
		Assets.play(visual, "deploy")
		var exhaust := Assets.socket(visual, "Exhaust")
		if exhaust:
			var tail := NozzleExhaust.new()
			tail.radius_m = 0.025
			tail.flame_diameter_m = 0.05
			tail.length_m = 0.15
			exhaust.add_child(tail)
	elif weapon == "lightning_gun":
		visual = LightningOrb.new()
		add_child(visual)
	elif weapon == "flamethrower":
		visual = FireOrb.new()
		add_child(visual)
	elif weapon == "emp_gun":
		if game is ArenaMatch:
			visual = game.effects.acquire_emp_charge(self)
		else:
			visual = EmpCharge.new()
			add_child(visual)
	else:
		var mesh := MeshInstance3D.new()
		var sphere := ProjectileResources.primitive(&"SphereMesh", {"radius":0.18,"height":0.36})
		mesh.mesh = sphere
		energy_material = ProjectileResources.shader(preload("res://shaders/combat/energy_projectile.gdshader"))
		mesh.material_override = energy_material
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mesh)
		visual = mesh
	orient_to_flight(direction)

func configure_presentation() -> void:
	presentation_configured = true
	if not game is ArenaMatch or not is_instance_valid(shooter): return
	if shooter != game.local_robot or not game.uses_first_person(): return
	var origin: Vector3 = shooter.weapon_vfx.origin()
	var target: Vector3 = game.combat.aim_target(shooter, Arsenal.ORB_GRAVITY_RANGE if Arsenal.orb_secondary(weapon) else Arsenal.WEAPONS[weapon].range)
	set_presentation_launch(origin, target)

func set_presentation_launch(origin: Vector3, target: Vector3) -> void:
	view_launch_offset = origin - global_position
	view_start_distance = distance
	view_convergence_distance = maxf(global_position.distance_to(target), 0.01)
	update_presentation()

func update_presentation() -> void:
	if not is_instance_valid(visual): return
	var offset := Vector3.ZERO
	if game is ArenaMatch and shooter == game.local_robot and game.uses_first_person():
		offset = view_launch_offset * maxf(0.0, 1.0 - (distance - view_start_distance) / view_convergence_distance)
	visual.global_position = global_position + offset

func _process(_dt: float) -> void:
	update_presentation()

func orient_to_flight(travel: Vector3):
	if travel.length_squared() < 0.0001: return
	var forward := travel.normalized()
	global_basis = Basis.looking_at(forward, Vector3.RIGHT if absf(forward.y) > 0.99 else Vector3.UP)

func update_emp_visual():
	(visual as EmpCharge).update_travel(distance)

func retire() -> void:
	if is_queued_for_deletion(): return
	if visual is EmpCharge and game is ArenaMatch and is_instance_valid(game.effects):
		game.effects.recycle_emp_charge(visual)
		visual = null
	queue_free()

func _physics_process(dt):
	if game.phase != "Active": retire(); return
	age += dt
	if age > Arsenal.PROJECTILE_LIFETIME: retire(); return
	var gravity_range := Arsenal.ORB_GRAVITY_RANGE if Arsenal.orb_secondary(weapon) else 100.0
	var guided := weapon == "rocket_launcher" and steer_homing(dt)
	if distance > gravity_range and not guided: fall += game.gravity * dt
	var next: Vector3 = global_position + direction * speed * dt - Vector3.UP * fall * dt
	if weapon == "emp_gun":
		next = global_position + direction * minf(speed * dt, maxf(0.0, Arsenal.EMP_MAX_RANGE - distance))
	# The cosmetic FPV launch offset must never move the world collision sweep.
	orient_to_flight(next-global_position)
	var hit: Dictionary = game.combat.projectile_hit(self, next-global_position, [shooter.get_rid()])
	distance += global_position.distance_to(hit.position if weapon == "emp_gun" and not hit.is_empty() else hit.get("center",hit.position) if not hit.is_empty() else next)
	if weapon == "emp_gun":
		update_emp_visual()
	if not hit.is_empty():
		var shielded: bool = hit.collider is ArenaRobot and (hit.collider.sh > 0 or hit.collider.protection > 0)
		if hit.collider is ArenaRobot:
			var damage := 50.0 if weapon == "rocket_launcher" else Arsenal.emp_damage(distance) if weapon == "emp_gun" else Arsenal.ORB_DAMAGE
			var impulse := Knockback.rocket(direction) if weapon == "rocket_launcher" else Knockback.emp(direction) if weapon == "emp_gun" else Vector3.ZERO
			hit.collider.hit(damage, shooter, weapon, impulse)
		if weapon == "rocket_launcher":
			stop_launch_report()
			for robot in game.robots:
				if robot == hit.collider or not robot.alive: continue
				var d: float = robot.eye().distance_to(hit.position)
				if d <= ArenaTuning.ROCKET_SPLASH_RADIUS and game.combat.clear(hit.position + hit.normal * 0.05, robot.eye()):
					var outward: Vector3 = robot.eye() - hit.position
					if Vector2(outward.x, outward.z).length_squared() < 0.001: outward = direction
					if not robot.hit(Arsenal.splash_damage(d), shooter, weapon, Knockback.rocket(outward, d)) and game.combat.invulnerable(robot):
						game.combat.play_impact(weapon, robot.eye(), robot, true, shooter)
			game.effects.explosion(hit.position, hit.normal, 1.3, (next - global_position).normalized())
			game.combat.play_impact(weapon, hit.position, hit.collider, shielded, shooter)
		elif weapon == "emp_gun":
			game.effects.emp_contact(hit.position, hit.normal)
			game.combat.play_impact(weapon, hit.position, hit.collider, shielded, shooter)
		elif weapon == "flamethrower":
			game.effects.fire_contact(hit.position, hit.normal)
			game.combat.play_impact(weapon, hit.position, hit.collider, shielded, shooter, true)
		else:
			game.effects.electric_contact(hit.position, hit.normal, true)
			game.combat.play_impact(weapon, hit.position, hit.collider, shielded, shooter, true)
		retire()
		return
	if weapon == "emp_gun" and distance >= Arsenal.EMP_MAX_RANGE:
		retire()
		return
	global_position = next
	orient_to_flight(direction * speed - Vector3.UP * fall)
	update_presentation()
