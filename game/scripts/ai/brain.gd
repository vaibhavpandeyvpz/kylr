class_name ArenaBrain
extends RefCounted
var robot
var decision := 0.0
var target = null
var seen := Vector3.ZERO
var memory := 0.0
var visible_time := 0.0
var goal := Vector3.ZERO
var goal_kind := "patrol"
var path: Array=[]
var path_index := 0
var retarget := 0.0
var strafe := 1.0
var stuck := 0.0
var previous := Vector3.ZERO
var airborne_goal:=Vector3.INF
var lift_clearance_time := 0.0
var lift_clearance_origin := Vector3.INF
var transition_index := -1
var transition_launched := false
var transition_via_reached := false
var behavior: BTPlayer
var dodge_time := 0.0
var maneuver_cooldown := 0.0
var crouch_time := 0.0
var cover_time := 0.0
var cover_cooldown := 0.0
var combat_direction := Vector3.ZERO
var tactical_probe_time := 0.0
var blocked_attempts := 0
var blocked_destination := Vector3.INF
var blocked_destination_time := 0.0
var observations: Dictionary = {}
var tuning: Dictionary
var aim_sample_clock := 0.0
var observed_aim := Vector3.ZERO
var observed_velocity := Vector3.ZERO
var fire_time := 0.0
var combat_paused := false
var precision_cooldown := 0.0
var observed_shots := 0
var equipment: BotEquipment
var head_choice_shot := -1
var aiming_head := false
var projectile_dodge := ProjectileDodge.new()
var firing_blocked := false
var firing_position_cooldown := 0.0
var firing_point := Vector3.INF
# Keep respawns in the same four cohorts as initial construction, rather than
# resetting every tree onto one physics tick. Per-bot intervals stay unchanged.
static var decision_phases := 4
static var profile_decisions := false
static var decision_usec := 0

static func decision_phase_offset(id: int,interval: float) -> float:
	return float(posmod(id,decision_phases))*interval/float(decision_phases)

func _init(owner):
	robot = owner
	tuning = BotDifficulty.profile(robot.arena_match.difficulty)
	equipment = BotEquipment.new(self)
	decision = float(robot.robot_id % 4) * float(tuning.decision_interval)/4.0
	if decision_phases > 1: decision = decision_phase_offset(robot.robot_id,float(tuning.decision_interval))
	strafe = -1 if robot.robot_id % 2 else 1
	behavior=BTPlayer.new()
	behavior.name="TacticalBehavior"
	behavior.update_mode=BTPlayer.MANUAL
	behavior.behavior_tree=load("res://data/ai/trees/"+("dm" if MatchTypes.individual(robot.arena_match.match_type) else robot.arena_match.match_type.to_lower())+".tres")
	behavior.set_scene_root_hint(robot.arena_match)
	robot.add_child(behavior)

func reset():
	projectile_dodge.reset()
	target=null
	memory=0
	observations.clear()
	visible_time=0
	reset_aim()
	precision_cooldown=0
	observed_shots=robot.network_shots
	equipment.reset()
	path.clear()
	path_index=0
	airborne_goal=Vector3.INF
	transition_index=-1
	transition_launched=false
	robot.jump_held=false
	robot.wants_crouch=false
	dodge_time=0
	maneuver_cooldown=0
	crouch_time=0
	cover_time=0
	cover_cooldown=0
	combat_direction=Vector3.ZERO
	combat_paused=false
	tactical_probe_time=0
	blocked_attempts=0
	blocked_destination=Vector3.INF
	blocked_destination_time=0
	retarget=0
	decision=decision_phase_offset(robot.robot_id,float(tuning.decision_interval))
	stuck=0
	goal_kind="patrol"
	firing_blocked=false
	firing_position_cooldown=0.0
	behavior.restart()

func hear(point: Vector3):
	if target == null:
		seen = point + Vector3(robot.arena_match.rng.randf_range(-3,3),0,robot.arena_match.rng.randf_range(-3,3))
		memory = 2.0

func tick(dt: float):
	var game = robot.arena_match
	decision -= dt
	retarget -= dt
	memory = maxf(0, memory - dt)
	dodge_time -= dt
	maneuver_cooldown = maxf(0, maneuver_cooldown-dt)
	crouch_time = maxf(0, crouch_time-dt)
	cover_time = maxf(0, cover_time-dt)
	cover_cooldown = maxf(0, cover_cooldown-dt)
	tactical_probe_time -= dt
	aim_sample_clock -= dt
	if robot.network_shots != observed_shots:
		observed_shots = robot.network_shots
		if robot.equipped=="rifle": precision_cooldown = tuning.precision_interval
	precision_cooldown = maxf(0,precision_cooldown-dt)
	blocked_destination_time=maxf(0,blocked_destination_time-dt)
	firing_position_cooldown=maxf(0,firing_position_cooldown-dt)
	firing_blocked=false
	robot.wants_crouch = false
	robot.wants_fire = false
	robot.wants_secondary = false
	if decision <= 0:
		decision = tuning.decision_interval
		game.map.traversal.begin_planning_queries()
		var decision_started := Time.get_ticks_usec() if profile_decisions else 0
		behavior.update(tuning.decision_interval)
		if profile_decisions: decision_usec += Time.get_ticks_usec()-decision_started
		game.map.traversal.end_planning_queries()
	if robot.protection > 0:
		target=null
		steer(dt)
		return
	if target!=null and (not target.alive or target.protection>0 or visible_aim_point(target)==Vector3.INF):
		target=null
		visible_time=0
		reset_aim()
	equipment.tick(dt)
	if target != null:
		if not target.alive or target.protection > 0:
			target = null
			visible_time = 0
			reset_aim()
		else:
			seen = target.eye()
			memory = tuning.memory_seconds
			remember(target)
			visible_time += dt
			if aim_sample_clock<=0:
				# Observe the torso while visible, never continuously snap to the head.
				observed_aim = visible_aim_point(target)
				if equipment.scoped(robot.equipped,robot.eye().distance_to(observed_aim)):
					if head_choice_shot!=robot.network_shots:
						head_choice_shot=robot.network_shots
						aiming_head=target.velocity.length()<=float(tuning.headshot_max_speed) and game.rng.randf()<float(tuning.headshot_chance)
					if aiming_head:
						var center := equipment.exposed_head(target)
						if center!=Vector3.ZERO: observed_aim=center
				observed_velocity = target.velocity
				aim_sample_clock = tuning.aim_sample_interval
			var aim: Vector3 = observed_aim
			var distance: float = robot.eye().distance_to(aim)
			var secondary := equipment.secondary(robot.equipped,distance)
			if robot.equipped not in ["pistol","rifle","minigun"] and (not Arsenal.orb_secondary(robot.equipped) or secondary):
				var speed := Arsenal.mode_value(robot.equipped,"projectile_speed",secondary)
				aim += observed_velocity * minf(1.0, distance / speed) * float(tuning.projectile_lead)
			firing_point=aim
			var desired: Vector3 = (aim - robot.eye()).normalized()
			if robot.equipped=="grenade_launcher":
				var profile: Dictionary=Arsenal.WEAPONS.grenade_launcher
				var arc := BallisticProjectile.launch_direction(robot.muzzle(),aim,profile.projectile_speed,profile.projectile_gravity*game.gravity/ArenaTuning.GRAVITY)
				if arc!=Vector3.ZERO: desired=arc
			robot.bot_aim = robot.bot_aim.slerp(desired, minf(1, dt * float(tuning.aim_turn_rate))).normalized()
			robot.yaw = lerp_angle(robot.yaw, atan2(-desired.x,-desired.z), minf(1, dt * minf(float(tuning.aim_turn_rate),float(BotDifficulty.data.tactics.yaw_turn_rate))))
			if visible_time >= float(tuning.reaction_delay) and robot.bot_aim.dot(desired) > 0.995:
				var ready: bool=not equipment.suspend_fire and robot.reload_time<=0 and distance <= equipment.reach(robot.equipped,distance)
				var check_lane: bool=ready and (robot.cooldown<=0 or (Arsenal.orb_secondary(robot.equipped) and not secondary))
				firing_blocked=check_lane and not game.combat.firing_lane(robot,aim,secondary)
				if ready and not firing_blocked:
					robot.wants_secondary=secondary
					robot.wants_fire=fire_window(dt) and (robot.equipped!="rifle" or precision_cooldown<=0)
					if robot.equipped=="rocket_launcher" and secondary:
						robot.wants_fire=robot.wants_fire and robot.rocket_lock_target==target.robot_id and robot.rocket_lock_progress>=1.0
					if Arsenal.orb_secondary(robot.equipped): robot.wants_secondary=secondary and robot.wants_fire
				elif ready and firing_blocked and firing_position_cooldown<=0:
					seek_firing_position(aim,secondary)
	steer(dt)
	projectile_dodge.tick(self,dt)

func perceive():
	var game = robot.arena_match
	var candidates: Array = []
	for other in game.robots:
		if not robot.enemy(other) or not other.alive or other.protection > 0: continue
		var delta: Vector3 = other.eye() - robot.eye()
		if delta.length() > float(tuning.perception_radius): continue
		var facing: Vector3 = Basis(Vector3.UP, robot.yaw) * Vector3.FORWARD
		if delta.length() > 6 and facing.dot(delta.normalized()) < -0.3: continue
		candidates.append(other)
	candidates.sort_custom(func(a,b): return robot.position.distance_squared_to(a.position) < robot.position.distance_squared_to(b.position))
	var selected = null
	var selected_cost := INF
	for i in mini(int(BotDifficulty.data.tactics.perception_candidates), candidates.size()):
		if visible_aim_point(candidates[i])!=Vector3.INF:
			remember(candidates[i])
			var cost := target_cost(candidates[i])
			if cost < selected_cost:
				selected = candidates[i]
				selected_cost = cost
	if selected != target:
		visible_time = 0
		reset_aim()
	target = selected
	if target != null:
		seen = target.eye()
		memory = tuning.memory_seconds

func reset_aim() -> void:
	aim_sample_clock = 0
	fire_time = 0
	observed_aim = Vector3.ZERO
	observed_velocity = Vector3.ZERO
	head_choice_shot = -1
	aiming_head = false
	firing_point=Vector3.INF

func validate_fire() -> void:
	# Movement and pose attachment run after decisions. Recheck the real muzzle
	# immediately before the shared trigger, including recoil and current aim.
	if firing_point==Vector3.INF or (not robot.wants_fire and not (Arsenal.orb_secondary(robot.equipped) and robot.wants_secondary)): return
	if robot.cooldown>0 and (not Arsenal.orb_secondary(robot.equipped) or robot.wants_secondary): return
	var actual: Vector3=robot.eye()+robot.aim_direction()*robot.eye().distance_to(firing_point)
	firing_blocked=not robot.arena_match.combat.firing_lane(robot,firing_point if robot.equipped=="grenade_launcher" else actual,robot.wants_secondary,Vector3.INF,robot.aim_direction())
	if not firing_blocked: return
	robot.wants_fire=false
	if Arsenal.orb_secondary(robot.equipped): robot.wants_secondary=false
	if firing_position_cooldown<=0: seek_firing_position(firing_point,equipment.secondary(robot.equipped,robot.eye().distance_to(firing_point)))

func visible_aim_point(other) -> Vector3:
	var torso: Vector3=other.position+Vector3.UP*(1.08 if other.crouched else other.character.eye_height)*0.65
	for point in [torso,other.eye()]:
		if robot.arena_match.combat.clear(robot.eye(),point): return point
	return Vector3.INF

func seek_firing_position(aim: Vector3, secondary: bool) -> bool:
	firing_position_cooldown=0.5
	if transition_index>=0 or not robot.is_on_floor() or robot.carrying>=0 or goal_kind in ["repair","energy","cover","extract","recover","intercept","escort"]: return false
	var toward: Vector3=aim-robot.eye();toward.y=0
	if toward.length_squared()<0.01: return false
	toward=toward.normalized()
	var side := toward.cross(Vector3.UP)*strafe
	var map=robot.arena_match.map
	var muzzle_offset: Vector3=robot.muzzle()-robot.position
	for offset in [side*1.25,-side*1.25,side*2.5,-side*2.5,-toward*1.5,toward*1.5,side*2.5-toward*1.5,-side*2.5-toward*1.5]:
		var point: Vector3=robot.position+offset
		if not map.traversal.supported(point) or not map.traversal.standing_clear(point): continue
		if not map.traversal.movement_clear(robot.position,point): continue
		if not robot.arena_match.combat.firing_lane(robot,aim,secondary,point+muzzle_offset): continue
		if commit_goal(point,"firing_position"): return true
	return commit_goal(target.position,"reposition")

func fire_window(dt: float) -> bool:
	var firing := fmod(fire_time,float(tuning.fire_burst)+float(tuning.fire_pause)) < float(tuning.fire_burst)
	fire_time += dt
	return firing

func remember(other) -> void:
	observations[other.robot_id] = {"point":other.position,"time":robot.arena_match.elapsed}

func visible_enemy(other) -> bool:
	if other == null or not other.alive or other.protection > 0 or not robot.enemy(other): return false
	var delta: Vector3 = other.eye()-robot.eye()
	if delta.length() > float(tuning.perception_radius): return false
	var facing: Vector3 = Basis(Vector3.UP,robot.yaw)*Vector3.FORWARD
	if delta.length() > 6.0 and facing.dot(delta.normalized()) < -0.3: return false
	return visible_aim_point(other)!=Vector3.INF

func interception_point(carrier_id: int) -> Vector3:
	var game = robot.arena_match
	var thief = game.robot_by_id(carrier_id)
	if visible_enemy(thief):
		remember(thief)
		return thief.position
	var last: Dictionary = observations.get(carrier_id,{})
	if not last.is_empty() and game.elapsed-float(last.time) <= float(tuning.memory_seconds): return last.point
	# Search the public extraction route, never the carried flag's live point.
	var search: Vector3 = game.flags[1-robot.team].home.lerp(game.flags[robot.team].home,0.35)
	if game.map.traversal != null:
		# The interpolation can lie over the void or above a lower bridge.
		# Route to its supported endpoint before commit_goal checks reachability.
		var route: Array = game.map.traversal.route(robot.position,search,robot.ep>ArenaTuning.HALF_EP,robot.is_on_floor())
		if not route.is_empty(): return route.back().point
	return search

func team_role() -> String:
	var game = robot.arena_match
	if game.bot_roles == null: game.bot_roles = BotTeamRoles.new(game)
	return game.bot_roles.role(robot)

func dm_leader():
	var leading = null
	for other in robot.arena_match.robots:
		if leading == null or other.kills > leading.kills or (other.kills == leading.kills and other.reached < leading.reached): leading = other
	return leading if leading != null and leading.kills > 0 else null

func unfavorable_duel(other) -> bool:
	return robot.ah < float(BotDifficulty.data.tactics.unfavorable_ah) or robot.reload_time > 0 or (robot.equipped == "pistol" and other.equipped != "pistol")

func protecting_lead() -> bool:
	var game = robot.arena_match
	if game.match_type != "DM" or dm_leader() != robot: return false
	var runner_up := 0
	for other in game.robots:
		if other != robot: runner_up = maxi(runner_up,other.kills)
	var tactics: Dictionary = BotDifficulty.data.tactics
	return robot.kills-runner_up >= int(tactics.dm_lead_margin) and (game.goal-robot.kills <= int(tactics.dm_remaining_kills) or game.time_limit-game.elapsed <= float(tactics.dm_remaining_seconds))

func target_cost(other) -> float:
	var cost: float = robot.position.distance_to(other.position)
	if robot.arena_match.match_type == "DM" and other == dm_leader() and unfavorable_duel(other): cost += BotDifficulty.data.tactics.leader_target_penalty
	return cost

func dm_survival() -> bool:
	var avoid: bool = target != null and unfavorable_duel(target) and (protecting_lead() or target == dm_leader())
	if not protecting_lead() and not avoid: return false
	if robot.ah <= 50 and seek_fixture("repair_station"): return true
	if avoid and seek_cover(): return true
	var resources := ["shield","energy"]
	for kind in resources:
		if seek_fixture(kind):
			goal_kind = "protect_lead" if protecting_lead() else "avoid_leader"
			return true
	if equipment.plan(true) or (target==null and equipment.plan(false)): return true
	if avoid:
		var away: Vector3 = (robot.position-target.position).normalized()
		for angle in [0.0,0.8,-0.8]:
			if commit_goal(robot.position+away.rotated(Vector3.UP,angle)*8.0,"avoid_leader"): return true
	return false

func plan_intent(intent: String) -> bool:
	var game = robot.arena_match
	# Finish a brief break in sight before exposing ourselves again. Survival still wins.
	if goal_kind == "cover" and cover_time > 0 and intent in ["combat", "objective", "search", "patrol"]: return true
	match intent:
		"egress":
			if robot.protection<=0: return false
			return commit_goal(game.map.zone_exit(robot.team,robot.position),"egress")
		"emergency":
			if MatchTypes.individual(game.match_type): return dm_survival()
			if game.match_type!="CTF": return false
			var own: Dictionary=game.flags[robot.team]
			if robot.carrying>=0:
				if own.state=="home": return commit_goal(own.home,"extract")
				if own.state=="dropped": return commit_goal(own.point,"recover")
				return commit_goal(interception_point(own.carrier),"intercept")
			if team_role() == "recover":
				if own.state=="dropped": return commit_goal(own.point,"recover")
				if own.state=="carried": return commit_goal(interception_point(own.carrier),"intercept")
			return false
		"repair":
			return seek_fixture("repair_station") if robot.ah<=50 else false
		"energy":
			return seek_fixture("energy") if robot.ep<ArenaTuning.HALF_EP else false
		"fortify":
			if target==null: return false
			for plate in game.map.fixtures:
				if plate.kind!="pressure_plate" or robot.position.distance_to(plate.point)>7.0 or robot.position.distance_to(plate.point)<1.1 or target.position.distance_to(plate.point)>11.0: continue
				var barricade=game.map.fixture_by_id(plate.id.replace("plate","barricade"))
				if barricade==null or not barricade.open: continue
				var toward_cover: Vector3 = barricade.point - plate.point
				var toward_enemy: Vector3 = target.position - barricade.point
				toward_cover.y = 0
				toward_enemy.y = 0
				if toward_cover.dot(toward_enemy) <= 0: continue
				var lateral: Vector3 = toward_enemy - toward_cover.normalized() * toward_enemy.dot(toward_cover.normalized())
				if lateral.length() > 3.0: continue
				if commit_goal(plate.point,"fortify"): return true
			return false
		"combat":
			if target==null: return false
			if goal_kind=="firing_position" and robot.position.distance_to(goal)>.4: return true
			if cover_cooldown <= 0 and (robot.reload_time > 0 or (robot.ah < 70 and target.wants_fire)) and seek_cover(): return true
			if game.match_type == "TDM":
				var enemy_home: Vector3=game.flags[1-robot.team].home
				if signf(robot.position.z)!=signf(enemy_home.z) or absf(robot.position.z)<12:
					var advance := enemy_home+Vector3(strafe*4.0,0,-signf(enemy_home.z)*7.0)
					if commit_goal(advance,"advance_fire"): return true
			var distance: float=robot.position.distance_to(seen)
			var toward: Vector3=(target.position-robot.position).normalized()
			var preferred := engagement_range()
			var destination: Vector3=target.position-toward*preferred+toward.cross(Vector3.UP)*strafe*1.5
			destination.y=target.position.y
			if commit_goal(destination,"engage"): return true
			if commit_goal(target.position,"engage"): return true
			return commit_goal(robot.position,"hold_cover") if distance<6 else false
		"objective":
			if target != null and robot.carrying < 0 and cover_cooldown <= 0 and (robot.reload_time > 0 or (robot.ah < 70 and target.wants_fire)) and seek_cover(): return true
			if game.match_type=="CTF":
				var flag: Dictionary=game.flags[1-robot.team]
				var role := team_role()
				if role == "escort" and flag.state=="carried":
					var carrier=game.robot_by_id(flag.carrier)
					if carrier!=null: return commit_goal(carrier.position+Vector3(strafe*2,0,0),"escort")
				if role == "defend" and game.flags[robot.team].state=="home":
					return commit_goal(game.flags[robot.team].home+Vector3(strafe*4,0,-signf(game.flags[robot.team].home.z)*6),"defend")
				return commit_goal(flag.point if flag.state=="dropped" else flag.home,"attack")
			if game.match_type=="TDM":
				var enemy_home: Vector3=game.flags[1-robot.team].home
				var attack_point:=enemy_home+Vector3(strafe*4.0,0,-signf(enemy_home.z)*7.0)
				for ally in game.robots:
					if ally==robot or ally.team!=robot.team or not ally.alive or ally.brain==null: continue
					if ally.brain.target!=null and robot.position.distance_to(ally.position)<18 and signf(ally.position.z)==signf(enemy_home.z) and absf(ally.position.z)>10 and ally.position.distance_to(enemy_home)<robot.position.distance_to(enemy_home):
						return commit_goal(ally.position+Vector3(strafe*3,0,0),"support")
				return commit_goal(attack_point,"assault")
			if MatchTypes.individual(game.match_type):
				var opposite := -signf(robot.spawn_fixture.point.z) if not robot.spawn_fixture.is_empty() else -signf(robot.position.z)
				return commit_goal(Vector3(strafe*6.0,0,opposite*22.0),"hunt")
			return false
		"equipment":
			return equipment.plan(false)
		"equipment_urgent":
			return equipment.plan(true)
		"search":
			# Sight can flicker at a corner. Keep the last known movement route for
			# two decision intervals; aiming/firing still lose the target immediately.
			if target==null and memory>0 and float(tuning.memory_seconds)-memory<float(tuning.decision_interval)*2.0 and robot.hit_flash<=0 and goal_kind in ["engage","hold_cover","advance_fire","firing_position"] and not path.is_empty() and robot.position.distance_to(goal)>0.65:
				return true
			return commit_goal(seen,"search") if memory>0 else false
		"patrol":
			if goal_kind=="patrol" and robot.position.distance_to(goal)>2 and not path.is_empty(): return true
			for attempt in 4:
				if commit_goal(game.map.patrol_point(robot.robot_id),"patrol"): return true
			robot.move_input=Vector2.ZERO
			return true
	return false

func engagement_range() -> float:
	return BotDifficulty.data.tactics.engagement_ranges.get(robot.equipped,11.0)

func seek_cover() -> bool:
	var game = robot.arena_match
	var away: Vector3 = robot.position-target.position
	away.y=0
	away=away.normalized()
	# Local candidates only: no scanning the full graph on every combat decision.
	for angle in [0.0, 0.7*strafe, -0.7*strafe, 1.4*strafe, -1.4*strafe]:
		var candidate: Vector3 = robot.position + away.rotated(Vector3.UP,angle)*float(BotDifficulty.data.tactics.cover_distance)
		if not game.map.traversal.supported(candidate): continue
		if game.combat.clear(candidate+Vector3.UP*1.08, target.eye()): continue
		if commit_goal(candidate,"cover"):
			cover_time=BotDifficulty.data.tactics.cover_hold
			cover_cooldown=BotDifficulty.data.tactics.cover_cooldown
			return true
	cover_cooldown=1.0
	return false

func combat_motion(route_direction: Vector3) -> Vector3:
	combat_paused = false
	if target == null or not robot.can_act() or transition_index >= 0 or airborne_goal != Vector3.INF: return route_direction
	if firing_blocked or goal_kind in ["firing_position","reposition"]: return route_direction
	if goal_kind in ["repair", "energy", "fortify", "cover", "protect_lead", "avoid_leader"]: return route_direction
	var toward: Vector3 = target.position-robot.position
	toward.y=0
	var distance := toward.length()
	if distance < 0.01 or absf(target.position.y-robot.position.y)>1.5: return route_direction
	if distance > engagement_range()*1.6: return route_direction
	toward/=distance
	if dodge_time <= 0:
		strafe *= -1
		dodge_time=robot.arena_match.rng.randf_range(0.7,1.5)+float(tuning.strafe_pause)
	var crossing: bool=robot.arena_match.map.carriers!=null and robot.arena_match.map.carriers.traffic.committed(robot)
	if robot.is_on_floor() and goal_kind in ["engage","hold_cover"] and not crossing and dodge_time<float(tuning.strafe_pause):
		combat_paused = true
		return Vector3.ZERO
	var lateral := toward.cross(Vector3.UP)*strafe
	var desired := route_direction
	if goal_kind in ["engage", "hold_cover"] and not crossing:
		var closing := clampf((distance-engagement_range())/4.0,-0.8,0.8)
		desired=(lateral*0.9+toward*closing).normalized()
	else:
		# Advance along objective routes while weaving, never orbit a flag target.
		desired=(route_direction+lateral*0.4).normalized()
	if not robot.is_on_floor(): return combat_direction if combat_direction != Vector3.ZERO else route_direction
	var stopping := Vector2(robot.velocity.x,robot.velocity.z).length_squared()/(2.0*ArenaTuning.GROUND_BRAKING)
	if tactical_probe_time <= 0:
		tactical_probe_time=0.12
		combat_direction=desired if desired != Vector3.ZERO and robot.arena_match.map.traversal.supported(robot.position+desired*maxf(1.2,stopping+0.4)) else route_direction
	desired=combat_direction
	var incoming: bool = target.wants_fire and target.aim_direction().dot((robot.eye()-target.eye()).normalized())>0.9
	if incoming and visible_time >= float(tuning.reaction_delay) and maneuver_cooldown <= 0 and desired != Vector3.ZERO:
		maneuver_cooldown=float(tuning.dodge_cooldown)*robot.arena_match.rng.randf_range(0.85,1.15)
		if robot.arena_match.rng.randf()>float(tuning.dodge_chance): return desired
		var projectile_threat: bool = target.equipped in ["rocket_launcher", "emp_gun"]
		if projectile_threat or robot.arena_match.rng.randf()<0.5:
			# Validate the whole normal-jump runway and headroom before requesting player jump.
			var height: float = robot.arena_match.jump_release_height(ArenaTuning.NORMAL_JUMP_HEIGHT)
			var speed: float = sqrt(2.0*robot.arena_match.gravity*height)
			var flight: float = height/speed+(speed+sqrt(speed*speed+2.0*robot.arena_match.gravity*height))/robot.arena_match.gravity
			var landing: Vector3 = robot.position+desired*ArenaTuning.RUN_SPEED*flight
			if safe_dodge_jump(landing): robot.jump_buffer=ArenaTuning.JUMP_BUFFER
		else:
			crouch_time=0.45
	robot.wants_crouch=crouch_time>0
	return desired

func safe_dodge_jump(landing: Vector3) -> bool:
	var game = robot.arena_match
	if game.map.traversal.crosses_portal(robot.position,landing): return false
	for fraction in [0.25,0.5,0.75,1.0]:
		var point: Vector3 = robot.position.lerp(landing,fraction)
		if not game.map.traversal.supported(point): return false
		if not game.combat.clear(point+Vector3.UP*0.8,point+Vector3.UP*(1.8+2.0*game.jump_release_height(ArenaTuning.NORMAL_JUMP_HEIGHT))): return false
		if not game.combat.clear(robot.eye(),point+Vector3.UP*1.55): return false
	return true

func seek_fixture(kind: String) -> bool:
	var candidates: Array=[]
	for fixture in robot.arena_match.map.fixtures:
		if fixture.kind!=kind: continue
		if kind == "repair_station":
			if not robot.can_act() or robot.ah > 50 or fixture.cooldown > 0 or fixture.occupant != null: continue
		elif not robot.arena_match.map.can_collect(fixture,robot): continue
		candidates.append(fixture)
	candidates.sort_custom(func(a,b): return resource_cost(a.point)<resource_cost(b.point))
	for index in mini(int(BotDifficulty.data.tactics.resource_candidates),candidates.size()):
		if commit_goal(candidates[index].point,"repair" if kind=="repair_station" else kind):
			BotDifficulty.trace("pickup",{"robot":robot.robot_id,"fixture":candidates[index].id,"eligible":true})
			return true
	return false

func resource_cost(point: Vector3) -> float:
	var cost: float = robot.position.distance_to(point)
	if target != null:
		var threat := maxf(0.0,1.0-point.distance_to(target.position)/float(BotDifficulty.data.tactics.threat_radius))
		cost += threat*float(tuning.route_risk)*float(BotDifficulty.data.tactics.threat_route_penalty)
	return cost

func equipment_travel(point: Vector3) -> float:
	var route: Array = robot.arena_match.map.traversal.route(robot.position,point,robot.ep>ArenaTuning.HALF_EP,robot.is_on_floor())
	if route.is_empty() or route[-1].point.distance_to(point)>2.0: return INF
	var cost := 0.0
	var previous_point: Vector3 = robot.position
	for step in route:
		if step.action=="portal": cost+=previous_point.distance_to(step.from)+3.0
		else:
			cost+=previous_point.distance_to(step.point)
			if step.action=="charged_jump": cost+=12.0
		previous_point=step.point
	return cost+resource_cost(point)-robot.position.distance_to(point)

func commit_goal(destination: Vector3,kind: String) -> bool:
	if blocked_destination_time > 0 and destination.distance_to(blocked_destination)<2.0: return false
	if transition_index >= 0 and transition_index < path.size(): return true
	if kind==goal_kind and kind not in ["firing_position","reposition"] and destination.distance_to(goal)<8.0 and retarget>0 and not path.is_empty(): return true
	var route: Array=navigation_route(destination,kind)
	if route.is_empty() or (not route[-1].get("staging",false) and route[-1].point.distance_to(destination)>2.0): return false
	if destination.distance_to(goal) > 1.5 or kind != goal_kind:
		if BotDifficulty.trace_enabled:
			BotDifficulty.trace("goal_commit", {"robot":robot.robot_id,"time":robot.arena_match.elapsed,"position":robot.position,"previous_kind":goal_kind,"kind":kind,"previous_destination":goal,"destination":destination,"ah":robot.ah,"ep":robot.ep,"sh":robot.sh,"weapon":robot.equipped,"loaded":robot.loaded,"packs":robot.packs,"carrying":robot.carrying,"target":target.robot_id if target!=null else -1})
		goal = destination
		goal_kind = kind
		path=route
		path_index=0
		transition_index=-1
		transition_launched=false
		retarget=1.0
	return true

func navigation_route(destination: Vector3,kind: String) -> Array:
	var map=robot.arena_match.map
	if map.carriers:return map.carriers.traffic.route(robot,destination,kind)
	return map.traversal.route(robot.position,destination,robot.ep>ArenaTuning.HALF_EP,robot.is_on_floor())

func steer(dt):
	combat_paused = false
	var map = robot.arena_match.map
	if map.carriers:
		map.carriers.traffic.observe(robot)
		map.carriers.advance_route(path)
		if transition_launched and transition_index>=0 and transition_index<path.size() and path[transition_index].has("point_carrier"):
			airborne_goal=path[transition_index].point
	if clear_empty_lift(dt): return
	# An entry trigger may fire before the approach waypoint is consumed.
	# Recognise that transfer once and replan from the real exit position.
	if robot.portal_lock>0:
		for index in range(path_index,path.size()):
			if path[index].action=="portal" and robot.position.distance_to(path[index].point)<4:
				finish_transition();break
	if robot.lift_from_pad and robot.lift_target>robot.position.y+0.5 and transition_index<0:
		for index in range(path_index,path.size()):
			if path[index].action!="launch": continue
			var entry: Vector3 = path[index].from
			if Vector2(entry.x-robot.position.x,entry.z-robot.position.z).length()<1.6:
				path_index=index
				break
	if goal_kind == "repair" and robot.position.distance_to(goal) < 0.35:
		robot.move_input = Vector2.ZERO
		return
	if goal_kind == "cover" and robot.position.distance_to(goal) < 0.6 and cover_time > 0:
		robot.move_input=Vector2.ZERO
		robot.wants_crouch=true
		return
	if retarget <= 0 and transition_index < 0 and robot.is_on_floor():
		path = navigation_route(goal,goal_kind)
		path_index = 0
		retarget = 1.0
	var destination: Vector3 = goal
	var action: String="walk"
	if not path.is_empty():
		while path_index < path.size() - 1 and path[path_index].action == "walk" and robot.position.distance_to(path[path_index].point) < 0.65: path_index += 1
		# The last walk sample can be inside the shaft. Start the lift approach
		# from outside so waiting does not require occupying that sample first.
		if path_index<path.size()-1 and path[path_index].action=="walk" and path[path_index+1].action=="lift" and robot.position.distance_to(path[path_index+1].from)<5.0:
			path_index+=1
		destination = path[path_index].point
		action=path[path_index].action
		if action=="walk" and map.carriers and robot.position.distance_to(path[path_index].from)<.9:
			var step: Dictionary=path[path_index]
			var source_deck: String=step.get("from_carrier",{}).get("deck","")
			var destination_deck: String=step.get("point_carrier",{}).get("deck","")
			if source_deck!=destination_deck and not map.carriers.walk_reachable(step):
				robot.move_input=Vector2.ZERO;path.clear();retarget=.5
				return
	else:
		robot.move_input=Vector2.ZERO
		stuck+=dt
		if stuck>1.5: recover_stuck("walk")
		return
	if action=="wait_carrier":
		transition_index=-1
		robot.move_input=Vector2.ZERO
		stuck=0.0
		return
	if action != "walk":
		if transition_index != path_index:
			transition_index = path_index
			transition_launched = false
			transition_via_reached = false
			robot.jump_held = false
		var source: Vector3 = path[path_index].from
		match action:
			"portal":
				if robot.portal_lock > 0 and robot.position.distance_to(destination) < 4.0:
					finish_transition()
					if path_index >= path.size(): robot.move_input=Vector2.ZERO; return
					destination=path[path_index].point
					action=path[path_index].action
				else:
					var entry: Vector3 = path[path_index].entry
					if entry == Vector3.INF: entry = source
					var through: Vector3 = entry-source
					through.y=0
					destination=entry+through.normalized()*0.45 if through.length()>0.01 else entry
			"jump", "charged_jump":
				if path[path_index].get("crouch",false) and transition_launched and not robot.is_on_floor():robot.wants_crouch=true
				if action == "charged_jump" and not transition_launched and robot.ep <= ArenaTuning.HALF_EP:
					robot.jump_held=false
					transition_index=-1
					path.clear()
					retarget=0
					return
				if robot.lift_from_pad and robot.lift_target > robot.position.y + 0.5 and robot.position.distance_to(destination) < 1.35:
					finish_transition()
					robot.move_input = Vector2.ZERO
					return
				if not transition_launched:
					if map.carriers and robot.position.distance_to(source)<=.55 and (action=="jump" or robot.jump_charge>=ArenaTuning.CHARGE_SECONDS) and (path[path_index].has("point_carrier") or path[path_index].has("from_carrier")):
						var height: float=ArenaTuning.CHARGED_JUMP_HEIGHT if action=="charged_jump" else ArenaTuning.NORMAL_JUMP_HEIGHT
						if not map.carriers.jump_reachable(path[path_index],height):
							transition_index=-1;robot.jump_held=false;robot.move_input=Vector2.ZERO
							path.clear();retarget=0.5
							return
					if robot.position.distance_to(source) > 0.55:
						destination=source
					else:
						robot.move_input=Vector2.ZERO
						if not robot.is_on_floor() or not robot.can_act(): return
						if action == "charged_jump" and robot.jump_charge < ArenaTuning.CHARGE_SECONDS:
							robot.jump_held=true
							return
						robot.jump_held=false
						if action == "charged_jump": robot.jump_release=true
						else: robot.jump_buffer=ArenaTuning.JUMP_BUFFER
						transition_launched=true
						airborne_goal=destination
				if transition_launched:
					var via: Vector3=path[path_index].get("via",Vector3.INF)
					if via!=Vector3.INF and robot.is_on_floor() and robot.can_act() and (not transition_via_reached or robot.position.distance_to(destination)>.6 or absf(robot.position.y-destination.y)>.15):
						robot.wants_crouch=false
						robot.jump_buffer=ArenaTuning.JUMP_BUFFER
					if via!=Vector3.INF and not transition_via_reached:
						if Vector2(robot.position.x-via.x,robot.position.z-via.z).length()<.2:transition_via_reached=true
						else:airborne_goal=via
					if transition_via_reached:airborne_goal=destination
				var scripted: bool=path[path_index].get("via",Vector3.INF)!=Vector3.INF
				var landed: bool=robot.position.distance_to(destination)<(.6 if scripted else 1.35)
				if scripted:landed=landed and transition_via_reached and absf(robot.position.y-destination.y)<.15
				if transition_launched and robot.is_on_floor() and landed:
					finish_transition()
			"drop":
				if not transition_launched and robot.position.distance_to(source)>0.75: destination=source
				else:
					transition_launched=true
					airborne_goal=destination
					if robot.is_on_floor() and absf(robot.position.y-destination.y)<0.2 and robot.position.distance_to(destination)<2.0: finish_transition()
			"lift":
				var fixture=map.lift_near(source)
				if fixture==null:finish_transition();return
				var controller=fixture.lift_controller
				if not transition_launched:
					controller.request_floor(source.y)
					if absf(controller.surface.global_position.y-source.y)<.15 and not controller.traveling:
						destination=controller.surface.global_position
						if controller.trigger.overlaps_body(robot):transition_launched=true
					else:destination=controller.waiting_point(robot,source.y)
				if transition_launched:
					controller.request_floor(path[path_index].point.y)
					if absf(controller.surface.global_position.y-path[path_index].point.y)>.15:airborne_goal=controller.surface.global_position
					else:airborne_goal=path[path_index].point
					if not controller.traveling and robot.is_on_floor() and absf(robot.position.y-path[path_index].point.y)<.1 and robot.position.distance_to(path[path_index].point)<.75:finish_transition()
			"speed_ramp":
				if robot.ramp_stage != 0:
					transition_launched=true;airborne_goal=destination
				elif not transition_launched:
					destination=path[path_index].entry if path[path_index].entry!=Vector3.INF else source
				elif robot.is_on_floor() and robot.position.distance_to(destination)<2.0:finish_transition()
			"launch":
				# The closest grid sample may sit outside the pad's trigger.
				# Approach and rise from its authored centre, not that sample.
				if path[path_index].entry != Vector3.INF: source=path[path_index].entry
				if robot.lift_target>robot.position.y+0.5 or not robot.is_on_floor():
					transition_launched=true
					airborne_goal=destination
					# A lower pad may be beside, rather than under, its landing.
					# Rise clear of the landing's underside before steering over it.
					if map.config.get("vertical_pad_departure",false) and robot.position.y < destination.y+0.2:
						airborne_goal=Vector3(source.x,destination.y,source.z)
				elif not transition_launched: destination=source
				if transition_launched and robot.is_on_floor() and absf(robot.position.y-path[path_index].point.y)<0.8 and robot.position.distance_to(path[path_index].point)<2.0: finish_transition()
	if transition_index >= 0 and transition_launched and airborne_goal!=Vector3.INF: destination=airborne_goal
	var delta: Vector3 = destination - robot.position
	delta.y = 0
	var weaving := target != null and goal_kind in ["engage", "hold_cover"] and transition_index < 0
	if delta.length() < 0.35 and absf(destination.y-robot.position.y)<0.8 and not weaving:
		robot.move_input = Vector2.ZERO
		return
	var requested_direction := delta.normalized()
	if action == "walk": requested_direction = combat_motion(requested_direction)
	if combat_paused:
		robot.move_input = Vector2.ZERO
		stuck = 0
		previous = robot.position
		return
	var direction: Vector3 = avoid_obstacles(requested_direction,action)
	if direction == Vector3.ZERO:
		robot.move_input=Vector2.ZERO
		stuck += dt
		if stuck>1.5: recover_stuck(action)
		return
	if target == null:
		robot.yaw = lerp_angle(robot.yaw, atan2(-direction.x,-direction.z), minf(1, dt * 4))
		robot.bot_aim = Basis(Vector3.UP,robot.yaw) * Vector3.FORWARD
	var local: Vector3 = Basis(Vector3.UP,robot.yaw).inverse() * direction
	robot.move_input = Vector2(local.x,local.z)
	robot.wants_walk = goal_kind == "repair" and delta.length() < 2.0
	robot.wants_sprint = robot.protection <= 0 and (target == null or goal_kind in ["cover", "extract", "recover"] or (robot.ah<40 and goal_kind=="repair")) and not robot.wants_walk and action == "walk" and airborne_goal == Vector3.INF
	var horizontal_speed := Vector2(robot.velocity.x, robot.velocity.z).length()
	var stopping_distance := horizontal_speed * horizontal_speed / (2.0 * ArenaTuning.GROUND_BRAKING)
	if airborne_goal == Vector3.INF and robot.is_on_floor() and not map.traversal.supported(robot.position + direction * maxf(0.65, stopping_distance + 0.32)):
		robot.wants_walk = true
		robot.wants_sprint = false
	var speed := Locomotion.speed(robot.wants_walk, robot.wants_sprint, robot.ep, robot.protection > 0)
	# Brake into nearby waypoints instead of overshooting them at sprint speed.
	if not weaving: robot.move_input *= minf(1.0, sqrt(2.0 * ArenaTuning.GROUND_BRAKING * maxf(0, delta.length() - 0.1)) / speed)
	if robot.position.distance_to(previous) < dt * 0.2: stuck += dt
	else:
		stuck = 0
		blocked_attempts=0
	previous = robot.position
	if stuck > 1.5 and not robot.jump_held:
		recover_stuck(action)

func recover_stuck(action: String) -> void:
	strafe *= -1
	retarget=0
	stuck=0
	blocked_attempts+=1
	if transition_index >= 0 and action != "portal":
		transition_index=-1
		transition_launched=false
		airborne_goal=Vector3.INF
	if blocked_attempts >= 3:
		# A graph route can exist while a pickup approach is physically obstructed.
		# Stop retrying that same destination and let the tree choose a useful alternative.
		blocked_destination=goal
		blocked_destination_time=6.0
		blocked_attempts=0
		path.clear()
		path_index=0
		transition_index=-1
		transition_launched=false
		airborne_goal=Vector3.INF
		robot.jump_held=false
		goal_kind="reposition"
		decision=0

func clear_empty_lift(dt: float) -> bool:
	var lifts = robot.arena_match.map.get("cargo_lifts")
	if lifts == null: return false
	for controller: ArchitectureLift in lifts:
		if not controller.needs_clearance(robot,robot.global_position): continue
		var floor_y := controller.lower if absf(robot.position.y-controller.lower)<absf(robot.position.y-controller.upper) else controller.upper
		var delta: Vector3=controller.waiting_point(robot,floor_y)-robot.global_position
		delta.y=0
		var direction := avoid_obstacles(delta.normalized(),"lift")
		var local: Vector3=Basis(Vector3.UP,robot.yaw).inverse()*direction
		robot.move_input=Vector2(local.x,local.z)
		robot.wants_walk=true
		robot.wants_sprint=false
		robot.jump_held=false
		# A robot already beneath the absent deck may be below the room's lip.
		# Escape with an ordinary jump if walking/stepping makes no progress.
		lift_clearance_time-=dt
		if lift_clearance_time<=0:
			var moved := Vector2(robot.position.x-lift_clearance_origin.x,robot.position.z-lift_clearance_origin.z).length()
			if moved<0.15 and robot.is_on_floor() and robot.can_act() and robot.protection<=0:
				robot.jump_buffer=ArenaTuning.JUMP_BUFFER
			lift_clearance_origin=robot.position
			lift_clearance_time=0.4
		stuck=0
		previous=robot.position
		return true
	lift_clearance_origin=Vector3.INF
	lift_clearance_time=0
	return false

func finish_transition() -> void:
	path=robot.arena_match.map.traversal.route(robot.position,goal,robot.ep>ArenaTuning.HALF_EP,robot.is_on_floor())
	if path.is_empty(): path=[{"point":goal,"action":"walk","from":robot.position,"entry":Vector3.INF}]
	path_index=0
	transition_index=-1
	transition_launched=false
	airborne_goal=Vector3.INF
	robot.jump_held=false
	retarget=1.0

func avoid_obstacles(desired: Vector3,action: String) -> Vector3:
	if not robot.is_on_floor(): return desired
	var bypass_edge := transition_index>=0 and transition_launched and action in ["drop","jump","charged_jump","launch","speed_ramp"]
	var nearby: Array=[]
	for other in robot.arena_match.robots:
		if other!=robot and other.alive and absf(other.position.y-robot.position.y)<1.4 and other.position.distance_to(robot.position)<2.2: nearby.append(other)
	var portal_risk := false
	if action!="portal":
		for portal in robot.arena_match.map.traversal.portal_points:
			if absf(portal.y-robot.position.y)>1.0: continue
			if robot.position.distance_to(portal)>1.2 and (robot.position+desired*0.95).distance_to(portal)<1.25: portal_risk=true; break
	var probe: Vector3=robot.position+Vector3.UP*0.9
	var clear_ahead: bool=robot.arena_match.combat.clear(probe,probe+desired*1.05) and robot.walk_or_step_motion_clear(desired*0.6)
	var safe_ahead: bool=bypass_edge or robot.arena_match.map.traversal.supported(robot.position+desired*0.6)
	if nearby.is_empty() and not portal_risk and clear_ahead and safe_ahead: return desired
	var side := strafe
	var best := Vector3.ZERO
	var best_score := -INF
	for angle in [0.0, 0.42*side, -0.42*side, 0.84*side, -0.84*side, 1.3*side, -1.3*side, 1.57*side, -1.57*side]:
		var candidate: Vector3=desired.rotated(Vector3.UP,angle)
		# Portal and separation adjustments only subtract from this bound. A
		# direction that cannot win needs no floor, movement or visibility probes.
		var score := candidate.dot(desired)*2.0-absf(angle)*0.12
		if score <= best_score: continue
		if angle == 0.0:
			# The forward direction was tested above against this same scene.
			if not safe_ahead or not clear_ahead: continue
		else:
			if not bypass_edge and not robot.arena_match.map.traversal.supported(robot.position+candidate*0.6): continue
			if not robot.walk_or_step_motion_clear(candidate*0.6): continue
			if not robot.arena_match.combat.clear(probe,probe+candidate*1.05): continue
		if action!="portal":
			for portal in robot.arena_match.map.traversal.portal_points:
				if absf(portal.y-robot.position.y)>1.0: continue
				if robot.position.distance_to(portal)>1.2 and (robot.position+candidate*0.95).distance_to(portal)<1.25: score-=5.0
		for other in nearby:
			var separation: Vector3=other.position-(robot.position+candidate*0.9)
			separation.y=0
			if separation.length()<0.75: score-=4.0
			elif separation.length()<1.4: score-=0.9
		if score>best_score: best_score=score; best=candidate
	return best if best_score>-1.5 else Vector3.ZERO
