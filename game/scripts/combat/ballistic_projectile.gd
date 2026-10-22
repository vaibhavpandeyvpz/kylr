class_name BallisticProjectile
extends Node3D

## Shared flight, collision and bounce behavior for physical weapon projectiles.
var game
var shooter
var weapon := ""
var profile: Dictionary
var velocity := Vector3.ZERO
var age := 0.0
var travelled := 0.0
var bounces := 0
var bounce_distance := 0.0
var has_bounced := false
var bounce_falloff := INF
var cosmetic_only := false
var visual: Node3D
var spin := 0.0
var extra_exclusions: Array[RID] = []

static func launch_direction(origin: Vector3, target: Vector3, speed: float, gravity: float) -> Vector3:
	var delta := target-origin
	var horizontal := Vector2(delta.x,delta.z).length()
	if gravity<=0: return delta.normalized()
	if horizontal<.01: return Vector3.ZERO
	var v2 := speed*speed
	var discriminant := v2*v2-gravity*(gravity*horizontal*horizontal+2.0*delta.y*v2)
	if discriminant<0: return Vector3.ZERO
	var angle := atan((v2-sqrt(discriminant))/(gravity*horizontal))
	return Vector3(delta.x/horizontal*cos(angle),sin(angle),delta.z/horizontal*cos(angle))

static func launch(world, owner_robot, id: String, origin: Vector3, direction: Vector3, settings: Dictionary, cosmetic := false) -> BallisticProjectile:
	var projectile := BallisticProjectile.new()
	projectile.game = world
	projectile.shooter = owner_robot
	projectile.weapon = id
	projectile.profile = settings.duplicate(true)
	projectile.velocity = direction.normalized() * float(settings.get("projectile_speed", settings.get("speed",45)))
	projectile.bounces = int(settings.get("bounces",0))
	projectile.cosmetic_only = cosmetic
	world.add_child(projectile)
	projectile.global_position = origin
	projectile.orient()
	return projectile

func _ready() -> void:
	add_to_group("dodge_projectiles")
	if DisplayServer.get_name() == "headless": return
	if weapon == "bio_rifle":
		visual = BioProjectileVisual.new()
		add_child(visual)
	elif weapon == "pulse_gun":
		visual = PulseProjectileVisual.new()
		add_child(visual)
	elif weapon == "flak_cannon":
		visual = FlakRoundVisual.new()
		visual.fragmented = true
		add_child(visual)
	else:
		visual = Assets.model("weapons","grenade_launcher","_grenade")
		add_child(visual)

func orient() -> void:
	if velocity.length_squared() < 0.0001: return
	global_basis = Basis.looking_at(velocity.normalized(),Vector3.RIGHT if absf(velocity.normalized().y)>.99 else Vector3.UP)
	if weapon == "grenade_launcher" and visual: visual.rotation = Vector3(spin,spin*.6,0)

func _physics_process(dt: float) -> void:
	if game.phase != "Active": queue_free(); return
	age += dt
	if age > float(profile.get("projectile_lifetime",8.0)) or travelled > float(profile.get("range",100)): queue_free(); return
	velocity.y -= float(profile.get("projectile_gravity",0)) * game.gravity / ArenaTuning.GRAVITY * dt
	if has_bounced and bounce_distance >= bounce_falloff:
		velocity.y -= float(profile.get("bounce_gravity",0)) * game.gravity / ArenaTuning.GRAVITY * dt
	var motion := velocity*dt
	var excluded: Array = [shooter.get_rid()] if is_instance_valid(shooter) else []
	excluded.append_array(extra_exclusions)
	orient()
	var hit: Dictionary = game.combat.projectile_hit(self,motion,excluded)
	if not hit.is_empty():
		travelled += global_position.distance_to(hit.get("center",hit.position))
		if weapon == "pulse_gun" and is_instance_valid(visual):
			visual.update_length(travelled)
			visual.absorb(hit.position,velocity.length())
		if not (hit.collider is ArenaRobot) and bounces>0:
			bounces -= 1
			bounce_falloff = (bounce_falloff if has_bounced else travelled) * float(profile.get("bounce_falloff_ratio",1.0))
			has_bounced = true
			bounce_distance = 0.0
			velocity = velocity.bounce(hit.normal) * float(profile.get("bounce_restitution",.5))
			global_position = hit.get("center",hit.position) + hit.normal*.015
			game.audio.cue(weapon+"_bounce",hit.position)
			orient()
			return
		impact(hit)
		queue_free()
		return
	travelled += motion.length()
	if weapon == "pulse_gun" and is_instance_valid(visual): visual.update_length(travelled)
	if has_bounced: bounce_distance += motion.length()
	global_position += motion
	spin += deg_to_rad(480)*dt
	orient()

func impact(hit: Dictionary) -> void:
	if not cosmetic_only and game.authority:
		if hit.collider is ArenaRobot:
			var allied_pulse: bool=weapon=="pulse_gun" and hit.collider.team==int(profile.get("owner_team",-1))
			var impulse := Knockback.grenade(velocity) if weapon=="grenade_launcher" else Vector3.ZERO
			if not allied_pulse and hit.collider.hit(float(profile.damage),shooter,weapon,impulse,{"point":hit.position,"direction":velocity.normalized(),"radial":false}):
				apply_status(hit.collider)
				if game is ArenaMatch: game.impact_at(hit.collider,weapon,hit.position,float(profile.get("splash_radius",0)))
		var radius := float(profile.get("splash_radius",0))
		if radius>0:
			for robot in game.robots:
				if robot == hit.collider or not robot.alive: continue
				var distance: float = robot.eye().distance_to(hit.position)
				if distance<=radius and game.combat.clear(hit.position+hit.normal*.03,robot.eye()):
					var outward: Vector3=robot.eye()-hit.position
					if Vector2(outward.x,outward.z).length_squared()<.001: outward=velocity
					var impulse := Knockback.grenade(outward,distance,radius) if weapon=="grenade_launcher" else Vector3.ZERO
					if robot.hit(float(profile.get("splash_damage",0))*(1-distance/radius),shooter,weapon,impulse,{"point":hit.position,"direction":velocity.normalized(),"radial":true}):
						apply_status(robot)
						if game is ArenaMatch: game.impact_at(robot,weapon,hit.position,radius)
	game.audio.cue("hit_"+weapon,hit.position)
	if weapon == "grenade_launcher":
		game.effects.grenade_explosion(hit.position,hit.normal)
	elif weapon == "pulse_gun":
		game.effects.pulse_contact(hit.position,hit.normal)
	elif weapon == "bio_rifle":
		game.effects.bio_contact(hit.position,hit.normal)
	elif weapon == "flak_cannon":
		game.effects.flak_contact(hit.position,hit.normal)

func apply_status(robot) -> void:
	robot.slow_remaining = maxf(robot.slow_remaining,float(profile.get("slow_duration",0)))
	robot.slow_multiplier = minf(robot.slow_multiplier,float(profile.get("slow_multiplier",1)))
	if float(profile.get("dot_damage",0))>0:
		var key := "Poison_"+weapon
		var dot := robot.get_node_or_null(key) as ProjectileStatus
		if dot == null:
			dot = ProjectileStatus.new()
			dot.name = key
			robot.add_child(dot)
		dot.configure(robot,shooter,weapon,profile)
