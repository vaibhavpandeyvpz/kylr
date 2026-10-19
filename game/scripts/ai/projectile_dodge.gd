class_name ProjectileDodge
extends RefCounted

var scan_time := 0.0
var remaining := 0.0
var direction := Vector3.ZERO
var seen := {}

func reset() -> void:
	seen.clear()
	remaining=0.0
	direction=Vector3.ZERO
	scan_time=0.0

static func closest_time(offset: Vector3, relative_velocity: Vector3) -> float:
	if relative_velocity.length_squared()<0.001: return -1.0
	return -offset.dot(relative_velocity)/relative_velocity.length_squared()

func tick(brain, dt: float) -> void:
	var robot=brain.robot
	var game=robot.arena_match
	remaining=maxf(0,remaining-dt)
	scan_time-=dt
	if not robot.can_act() or not robot.is_on_floor() or brain.transition_index>=0 or brain.airborne_goal!=Vector3.INF:
		remaining=0
		return
	if scan_time<=0:
		scan_time=0.12
		var threats: Array=[]
		for projectile in game.get_tree().get_nodes_in_group("dodge_projectiles"):
			if projectile.game!=game or projectile.is_queued_for_deletion() or projectile.shooter==robot: continue
			if projectile is BallisticProjectile and projectile.cosmetic_only: continue
			if projectile.weapon=="pulse_gun" and int(projectile.profile.get("owner_team",-1))==robot.team: continue
			var offset: Vector3=projectile.global_position-(robot.position+Vector3.UP*0.9)
			if offset.length_squared()>900: continue
			var velocity: Vector3=projectile.velocity if projectile is BallisticProjectile else projectile.direction*projectile.speed-Vector3.UP*projectile.fall
			var time:=closest_time(offset,velocity-robot.velocity)
			if time<0 or time>1.5: continue
			var predicted: Vector3=offset+(velocity-robot.velocity)*time
			if projectile is BallisticProjectile:
				predicted.y-=float(projectile.profile.get("projectile_gravity",0))*game.gravity/ArenaTuning.GRAVITY*time*time*0.5
			var radius:=2.5 if projectile.weapon in ["rocket_launcher","grenade_launcher"] else 0.85
			if predicted.length()>radius: continue
			# Perceive visible projectiles in the forward hemisphere, never through cover.
			if robot.aim_direction().dot(offset.normalized())<0.0: continue
			threats.append({"node":projectile,"time":time,"velocity":velocity,"point":projectile.global_position+velocity*time})
		threats.sort_custom(func(a,b):return a.time<b.time)
		var observed: Dictionary={}
		for index in mini(3,threats.size()):
			var threat: Dictionary=threats[index]
			if not game.combat.clear(robot.eye(),threat.node.global_position): continue
			var id: int=threat.node.get_instance_id()
			observed[id]=seen.get(id,game.elapsed)
			if game.elapsed-float(observed[id])<float(brain.tuning.reaction_delay) or brain.maneuver_cooldown>0: continue
			brain.maneuver_cooldown=float(brain.tuning.dodge_cooldown)
			if game.rng.randf()>float(brain.tuning.dodge_chance): continue
			var lateral: Vector3=threat.velocity.cross(Vector3.UP).normalized()
			if lateral.length_squared()<0.1: lateral=Basis(Vector3.UP,robot.yaw)*Vector3.RIGHT
			var candidates: Array[Vector3]=[lateral,-lateral]
			candidates.sort_custom(func(a,b):return (robot.position+a*2.0).distance_squared_to(threat.point)>(robot.position+b*2.0).distance_squared_to(threat.point))
			for candidate in candidates:
				if safe_runway(brain,candidate):
					direction=candidate
					remaining=0.4
					BotDifficulty.trace("projectile_dodge",{"robot":robot.robot_id,"weapon":threat.node.weapon})
					break
			if remaining>0: break
		seen=observed
	if remaining>0:
		var local: Vector3=Basis(Vector3.UP,robot.yaw).inverse()*direction
		robot.move_input=Vector2(local.x,local.z)
		robot.wants_walk=false
		robot.wants_sprint=false
		robot.wants_crouch=false
		brain.combat_paused=false

func safe_runway(brain, heading: Vector3) -> bool:
	var robot=brain.robot
	var game=robot.arena_match
	var distance:=ArenaTuning.RUN_SPEED*0.4+ArenaTuning.RUN_SPEED*ArenaTuning.RUN_SPEED/(2*ArenaTuning.GROUND_BRAKING)
	var destination: Vector3=robot.position+heading*distance
	if game.map.traversal.crosses_portal(robot.position,destination): return false
	for fraction in [0.25,0.5,0.75,1.0]:
		var point: Vector3=robot.position.lerp(destination,fraction)
		if not game.map.traversal.supported(point) or not game.map.traversal.standing_clear(point): return false
	return game.combat.clear(robot.eye(),destination+Vector3.UP*1.55)
