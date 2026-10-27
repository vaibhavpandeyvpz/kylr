class_name CrossingTraffic
extends RefCounted
## Balance actual corridor entries and commitments, using only live safe links.
var carrier_ref: WeakRef
var carriers: MapCarriers:
	get: return carrier_ref.get_ref() as MapCarriers
var arena
var actors: Dictionary={}
var usage := {"junction":0,"floaters":0}

func _init(controller: MapCarriers,map):
	carrier_ref=weakref(controller);arena=map

func base_at(point: Vector3) -> int:
	for index in arena.config.zone_bounds.size():
		var bounds: Dictionary=arena.config.zone_bounds[index]
		if point.x>=float(bounds.min[0]) and point.x<=float(bounds.max[0]) and point.z>=float(bounds.min[2]) and point.z<=float(bounds.max[2]):return index
	return -1

func state_for(robot) -> Dictionary:
	if not actors.has(robot.robot_id):actors[robot.robot_id]={"base":base_at(robot.position),"touches":{},"assignment":{},"deck":""}
	return actors[robot.robot_id]

func observe(robot) -> void:
	var state:=state_for(robot)
	var base:=base_at(robot.position)
	if not robot.alive or robot.protection>0:
		state.assignment.clear();state.touches.clear()
		if base>=0:state.base=base
		return
	if base>=0:
		state.deck=""
		if state.base>=0 and base!=state.base:
			state.assignment.clear();state.touches.clear()
		elif base==state.base and not state.touches.is_empty():
			state.assignment.clear();state.touches.clear()
		state.base=base
		return
	if not robot.is_on_floor():
		state.deck="";return
	for section in carriers.sections:
		var local: Vector3=MapCarriers.transform_at(arena.game.elapsed,section).affine_inverse()*robot.position
		local-=Vector3(float(section.position[0]),float(section.position[2]),-float(section.position[1]))
		for rect in section.rects:
			if local.x<float(rect[0]) or local.x>float(rect[2]) or -local.z<float(rect[1]) or -local.z>float(rect[3]):continue
			var kind:="junction" if section.name=="Junction" else "floaters"
			if not state.touches.has(kind):usage[kind]+=1
			if state.deck!=section.name and not state.assignment.is_empty():state.assignment.waiting_since=-1.0
			state.deck=section.name
			state.touches[kind]=true
			if not state.assignment.is_empty():
				if state.assignment.kind!=kind:
					state.assignment.via=String(section.name);state.assignment.passed=true
				state.assignment.kind=kind
				if section.name==state.assignment.via:state.assignment.passed=true
			return

func choose_kind() -> String:
	var scores: Dictionary={"junction":float(usage.junction),"floaters":float(usage.floaters)}
	for state in actors.values():
		if not state.assignment.is_empty() and not state.touches.has(state.assignment.kind):scores[state.assignment.kind]+=1.0
	var weights: Dictionary=arena.config.get("crossing_balance",{"junction":1.0,"floaters":1.0})
	return "junction" if scores.junction/float(weights.junction)<=scores.floaters/float(weights.floaters) else "floaters"

func waypoint(deck: String) -> Vector3:
	# Rigid motion preserves distance to the deck centre. Rank IDs once, then
	# read the first enabled point's live coordinates instead of rescanning it.
	if not carriers.waypoint_order.has(deck):
		var specs: Array=carriers.deck_sections if not carriers.deck_sections.is_empty() else carriers.sections
		var section: Dictionary=specs.filter(func(item):return item.name==deck)[0]
		var center:=Vector3(float(section.position[0]),float(section.position[2]),-float(section.position[1]))
		var ranked: Array=carriers.deck_navigation.get(deck,[]).filter(func(id):return absf(carriers.navigation_points[id].rest.y-center.y)<=1.0)
		ranked.sort_custom(func(a,b):return carriers.navigation_points[a].rest.distance_squared_to(center)<carriers.navigation_points[b].rest.distance_squared_to(center))
		carriers.waypoint_order[deck]=ranked
	for id in carriers.waypoint_order[deck]:
		if arena.nav.is_point_disabled(id):continue
		return arena.nav.get_point_position(id)
	return Vector3.INF

func has_other_corridor(path: Array,kind: String) -> bool:
	for step in path:
		for field in ["point_carrier","from_carrier"]:
			if not step.has(field):continue
			var deck: String=step[field].deck
			if kind=="floaters" and deck=="Junction":return true
			if kind=="junction" and "Floater" in deck:return true
	return false

func route(robot,destination: Vector3,goal_kind: String) -> Array:
	var allow: bool=robot.ep>ArenaTuning.HALF_EP
	var grounded: bool=robot.is_on_floor()
	var graph: TraversalGraph=arena.traversal
	var state:=state_for(robot)
	var requested_destination:=destination
	var target_base:=base_at(destination)
	var strategic: bool=robot.carrying<0 and goal_kind in ["patrol","attack","advance","engage","search"]
	if not strategic:
		state.assignment.clear()
		return graph.route(robot.position,destination,allow,grounded)
	if strategic and not state.assignment.is_empty() and target_base<0 and robot.position.distance_to(destination)>8.0:
		destination=state.assignment.goal
		target_base=state.assignment.destination
	if not strategic or target_base<0 or state.base<0 or target_base==state.base:
		return graph.route(robot.position,destination,allow,grounded)
	if state.assignment.is_empty() or state.assignment.destination!=target_base:
		var kind:=choose_kind()
		state.assignment={"kind":kind,"destination":target_base,"goal":destination,"via":"","passed":false,"waiting_since":-1.0}
	var assignment: Dictionary=state.assignment
	if assignment.kind=="floaters":
		var staged:=floater_route(robot,destination,assignment,allow,grounded)
		if not staged.is_empty():return staged
		return graph.route(robot.position,destination,allow,grounded)
	var bias:=1 if assignment.kind=="junction" else 2
	var candidates: Array=["Junction"] if bias==1 else ["A_Floater_2","B_Floater_2"]
	if assignment.passed:
		var direct:=graph.route(robot.position,destination,allow,grounded,bias)
		if not direct.is_empty() and not has_other_corridor(direct,assignment.kind):
			if destination.distance_to(requested_destination)>2.0:direct.back()["staging"]=true
			return direct
		var wait:=waiting_route(robot,assignment,allow,grounded)
		if not wait.is_empty():return wait
	else:
		if not String(assignment.via).is_empty():candidates=[String(assignment.via)]
		for deck in candidates:
			var via:=waypoint(deck)
			if via==Vector3.INF:continue
			var first:=graph.route(robot.position,via,allow,grounded,bias)
			if first.is_empty() or first.back().point.distance_to(via)>2.0 or has_other_corridor(first,assignment.kind):continue
			var second:=graph.route(via,destination,allow,false,bias)
			assignment.via=deck
			if second.is_empty() or second.back().point.distance_to(destination)>2.0 or has_other_corridor(second,assignment.kind):
				if assignment.kind!="floaters":continue
				append_wait(first,via)
				return first
			first.append_array(second.slice(1))
			if destination.distance_to(requested_destination)>2.0:first.back()["staging"]=true
			return first
	var wait:=waiting_route(robot,assignment,allow,grounded)
	if not wait.is_empty():return wait
	return graph.route(robot.position,destination,allow,grounded)

func floater_route(robot,destination: Vector3,assignment: Dictionary,allow: bool,grounded: bool) -> Array:
	var state:=state_for(robot)
	var current_id: int=arena.nav.get_closest_point(robot.position)
	var current_deck: String=carriers.navigation_points.get(current_id,{}).get("deck","")
	var lanes: Array=[]
	if assignment.has("lane"):lanes=[assignment.lane]
	else:
		for recipe in arena.config.get("floater_paths",[]):
			var lane: Array=recipe.duplicate()
			if state.base==1:lane.reverse()
			lanes.append(lane)
	for lane: Array in lanes:
		var index:=lane.find(current_deck)
		if index<0 or index>=lane.size()-1:continue
		var next_deck: String=lane[index+1]
		var target:=destination if index+1==lane.size()-1 else waypoint(next_deck)
		if target==Vector3.INF:continue
		var path: Array=arena.traversal.route(robot.position,target,allow,grounded,2)
		if path.is_empty() or path.back().point.distance_to(target)>2.0 or has_other_corridor(path,"floaters"):continue
		var leaves_lane:=false
		for step in path:
			for field in ["point_carrier","from_carrier"]:
				if step.has(field) and step[field].deck not in lane:leaves_lane=true
		if leaves_lane:continue
		assignment.lane=lane;assignment.via=next_deck
		if index+1<lane.size()-1:append_wait(path,target)
		return path
	return waiting_route(robot,assignment,allow,grounded)

func append_wait(path: Array,point: Vector3) -> void:
	path.append({"point":point,"from":point,"entry":Vector3.INF,"action":"wait_carrier","staging":true})
	carriers.bind_route(path)

func waiting_route(robot,assignment: Dictionary,allow: bool,grounded: bool) -> Array:
	if assignment.kind!="floaters" or String(assignment.via).is_empty():return []
	if assignment.waiting_since<0:assignment.waiting_since=arena.game.elapsed
	if arena.game.elapsed-float(assignment.waiting_since)>20.0:return []
	var state:=state_for(robot)
	var holding: String=state.deck
	if holding.is_empty():
		var id: int=arena.nav.get_closest_point(robot.position)
		holding=carriers.navigation_points.get(id,{}).get("deck","")
	if "Floater" not in holding and not holding.ends_with("_Island"):return []
	var center:=waypoint(holding)
	if center==Vector3.INF:return []
	var path: Array=arena.traversal.route(robot.position,center,allow,grounded,2)
	if path.is_empty() or has_other_corridor(path,"floaters"):return []
	append_wait(path,center)
	return path

func committed(robot) -> bool:
	return actors.has(robot.robot_id) and not actors[robot.robot_id].assignment.is_empty()
