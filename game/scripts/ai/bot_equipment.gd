class_name BotEquipment
extends RefCounted
## Equipment policy requests ordinary pickups/reloads/equips; it grants no resources.
var owner_ref: WeakRef
var brain:
	get: return owner_ref.get_ref()
var switch_time := 0.0
var last_pickup := ""
var suspend_fire := false
var head_centers: Dictionary = {}
var head_shapes: Dictionary = {}

func exposed_head(victim) -> Vector3:
	var id: int = victim.get_instance_id()
	var cached: Array = head_shapes.get(id,[])
	if cached.is_empty() or cached[0].get_ref()==null:
		cached=[]
		for collider in victim.find_children("*","StaticBody3D",true,false):
			if collider.get_meta("hit_region","")!="head": continue
			for shape in collider.find_children("*","CollisionShape3D",true,false): cached.append(weakref(shape))
		head_shapes[id]=cached
	for ref in cached:
		var shape: CollisionShape3D = ref.get_ref()
		if shape==null: continue
		var center := head_center(shape)
		if brain.robot.arena_match.combat.clear(brain.robot.eye(),center): return center
	return Vector3.ZERO

func head_center(shape: CollisionShape3D) -> Vector3:
	var id := shape.get_instance_id()
	if not head_centers.has(id): head_centers[id]=shape.shape.get_debug_mesh().get_aabb().get_center()
	return shape.global_transform*head_centers[id]

func _init(owner): owner_ref = weakref(owner)

func reset() -> void:
	switch_time = 0
	last_pickup = ""
	suspend_fire = false

func tick(dt: float) -> void:
	switch_time = maxf(0,switch_time-dt)
	suspend_fire = false
	var robot = brain.robot
	if robot.pickup_weapon != last_pickup:
		last_pickup = robot.pickup_weapon
		switch_time = 0
	if not robot.can_act() or robot.reload_time>0: return
	# Shared combat finishes the funded shot/stream, then reloads the equipped gun.
	if robot.equipped!="pistol" and robot.loaded<=0 and robot.packs>0: return
	var distance := engagement_distance()
	var choice := "pistol"
	var pistol_score := utility("pistol",distance)
	var best_score := 0.0
	for id in robot.owned_weapons:
		if id=="pistol" or not robot.has_ammo(id): continue
		var score := utility(id,distance)
		var margin := 1.12 if robot.equipped=="pistol" else 0.88
		if score>0 and score>=pistol_score*margin and score>best_score:
			choice=id
			best_score=score
	if choice!=robot.equipped:
		var unusable: bool = robot.equipped!="pistol" and (robot.loaded<=0 or utility(robot.equipped,distance)<=0)
		if switch_time<=0 or unusable:
			suspend_fire = true
			if robot.animation_lock<=0 and (robot.weapon_vfx==null or robot.weapon_vfx.pending.is_empty()):
				robot.equip(choice)
				switch_time = 1.25
				BotDifficulty.trace("equip",{"robot":robot.robot_id,"weapon":choice,"distance":distance})
	# Safe manual reloads discard the remainder under the ordinary player rule.
	if robot.equipped!="pistol" and robot.packs>0 and robot.animation_lock<=0:
		var fraction: float = float(robot.loaded)/float(Arsenal.WEAPONS[robot.equipped].capacity)
		var quiet: bool = brain.target==null and brain.memory<=float(brain.tuning.reload_memory_remaining)
		if robot.loaded<=0 or (quiet and fraction<=float(brain.tuning.reload_fraction)):
			robot.start_reload()

func engagement_distance() -> float:
	if brain.target!=null: return brain.robot.eye().distance_to(brain.observed_aim if brain.observed_aim!=Vector3.ZERO else brain.target.eye())
	return 11.0

func scoped(weapon: String,distance: float) -> bool:
	return weapon=="rifle" and distance>22.0

func secondary(weapon: String,distance: float) -> bool:
	if weapon == "rocket_launcher": return distance > 15.0
	if scoped(weapon,distance): return true
	return Arsenal.orb_secondary(weapon) and (distance>float(Arsenal.WEAPONS[weapon].range) or (distance>=float(brain.tuning.orb_min_range) and ammo_seconds()<=float(brain.tuning.ammo_horizon)))

func reach(weapon: String,distance: float) -> float:
	if weapon=="grenade_launcher":
		var profile: Dictionary=Arsenal.WEAPONS[weapon]
		return minf(profile.range,profile.projectile_speed*profile.projectile_speed/(profile.projectile_gravity*brain.robot.arena_match.gravity/ArenaTuning.GRAVITY))
	if weapon == "rocket_launcher": return float(Arsenal.WEAPONS[weapon].range)
	if scoped(weapon,distance) or secondary(weapon,distance): return Arsenal.mode_value(weapon,"range",true)
	return float(Arsenal.WEAPONS[weapon].range)

func utility(weapon: String,distance: float) -> float:
	var profile: Dictionary = Arsenal.WEAPONS[weapon]
	if distance>reach(weapon,distance): return 0
	var rate: float = 1.0/float(profile.interval)
	var damage: float = profile.damage
	if weapon=="rifle":
		rate = 1.0/maxf(float(profile.interval),float(brain.tuning.precision_interval))
		if scoped(weapon,distance):
			damage=float(profile.scoped_damage)
			rate=1.0/maxf(float(profile.scoped_interval),float(brain.tuning.precision_interval))
			if brain.target!=null and brain.target.velocity.length()<=float(brain.tuning.headshot_max_speed) and exposed_head(brain.target)!=Vector3.ZERO:
				damage+=75.0*float(brain.tuning.headshot_chance)*0.5/(1.0+brain.target.velocity.length())
	elif Arsenal.orb_secondary(weapon):
		if secondary(weapon,distance): rate=1.0/float(profile.secondary_interval); damage=float(profile.secondary_damage)*1.8
		else: rate=1.0; damage*=1.5 if weapon=="lightning_gun" else 1.2
	elif weapon=="emp_gun": damage=Arsenal.emp_damage(distance)*1.25
	elif weapon=="rocket_launcher":
		if distance<5.0: return 0 # Do not deliberately blast our own feet.
		if brain.target!=null:
			var direction: Vector3 = (brain.target.eye()-brain.robot.eye()).normalized()
			if not brain.robot.arena_match.combat.ray(brain.robot.muzzle(),brain.robot.muzzle()+direction*5.0,[brain.robot.get_rid()]).is_empty(): return 0
		damage*=clampf(1.0-(distance-15.0)*0.025,0.35,1.0)
	if weapon in ["rocket_launcher","emp_gun"] or (Arsenal.orb_secondary(weapon) and secondary(weapon,distance)):
		var flight := distance/Arsenal.mode_value(weapon,"projectile_speed",secondary(weapon,distance))
		var uncertainty: float = brain.observed_velocity.length()*(flight*(1.0-float(brain.tuning.projectile_lead))+maxf(0,flight-1.0))*0.25
		damage/=1.0+uncertainty
	var duty: float = float(brain.tuning.fire_burst)/(float(brain.tuning.fire_burst)+float(brain.tuning.fire_pause))
	return damage*rate*duty

func ammo_seconds(id := "") -> float:
	var robot = brain.robot
	if id=="": id=robot.ammo_weapon()
	if id=="" or id=="pistol": return 0
	var ammo: Dictionary = robot.ammo_for(id)
	var profile: Dictionary = Arsenal.WEAPONS[id]
	var rate: float = 2.0 if profile.attack in ["beam","flame"] else 1.0/float(profile.interval)
	if id=="rifle": rate=1.0/maxf(float(profile.interval),float(brain.tuning.precision_interval))
	# Full-trigger time is conservative: a burst pause must not justify running dry.
	return float(int(ammo.loaded)+int(ammo.packs)*int(profile.capacity))/rate

func plan(urgent: bool) -> bool:
	var robot = brain.robot
	if not robot.can_act() or robot.reload_time>0 or brain.transition_index>=0: return false
	var critical: bool = robot.pickup_weapon=="" or ammo_seconds()<=float(brain.tuning.ammo_horizon)
	if urgent and not critical: return false
	# Flag emergencies are handled above this intent. Carriers/escorts otherwise
	# accept only a nearby, critical refill, never routine shopping detours.
	var committed: bool = robot.carrying>=0 or brain.goal_kind in ["extract","recover","intercept","escort"]
	if committed and not critical: return false
	if not urgent and brain.target!=null: return false
	var limit: float = float(brain.tuning.equipment_detour)
	if committed: limit=4.0
	elif brain.target!=null: limit=6.0
	var candidates := []
	var distance := engagement_distance()
	var current: float = utility("pistol",distance)
	for id in robot.owned_weapons:
		if id!="pistol" and ammo_seconds(id)>0: current=maxf(current,utility(id,distance))
	for fixture in robot.arena_match.map.fixtures:
		if fixture.kind not in ["ammo","weapon","shield"] or not robot.arena_match.map.can_collect(fixture,robot): continue
		var travel: float = brain.resource_cost(fixture.point)
		if travel>limit: continue
		var value := 0.0
		if fixture.kind=="ammo":
			if fixture.weapon not in robot.owned_weapons: continue
			var horizon: float = float(brain.tuning.ammo_horizon)+travel/6.0
			if ammo_seconds(fixture.weapon)>horizon: continue
			value=2.0+maxf(0,1.0-ammo_seconds(fixture.weapon)/maxf(1,horizon))
		elif fixture.kind=="shield":
			if not urgent and not committed and brain.target==null and robot.sh<=25: value=1.0
		elif not committed:
			var improvement: float = utility(fixture.weapon,distance)/maxf(1,current)
			var threshold: float = 1.05 if robot.pickup_weapon=="" else float(brain.tuning.weapon_upgrade_ratio)
			if improvement<threshold: continue
			value=improvement
		if value>0: candidates.append({"fixture":fixture,"score":value/(1.0+travel/8.0)})
	candidates.sort_custom(func(a,b): return a.score>b.score)
	for index in mini(int(BotDifficulty.data.tactics.resource_candidates),candidates.size()):
		var fixture: Dictionary = candidates[index].fixture
		if brain.equipment_travel(fixture.point)>limit: continue
		if brain.commit_goal(fixture.point,fixture.kind):
			BotDifficulty.trace("equipment_goal",{"robot":robot.robot_id,"kind":fixture.kind,"fixture":fixture.id,"ammo_seconds":ammo_seconds(),"urgent":urgent})
			return true
	return false
