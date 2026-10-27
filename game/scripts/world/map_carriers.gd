class_name MapCarriers
extends RefCounted
## Gameplay motion samples the replicated match clock, independently of
## decorative animation budgets and Reduced Motion.
var arena
var skeleton: Skeleton3D
var sections: Array = []
var deck_sections: Array=[]
var contacts: Array = []
var last_remote_clock := -1.0
var remote_ahead := 0.0
var navigation_points: Dictionary = {}
var boundary_points: Array[int] = []
var dynamic_edges: Array[Vector2i] = []
var next_links := 0.0
var local_routes: Array = []
var traffic: CrossingTraffic
var deck_navigation: Dictionary={}
var waypoint_order: Dictionary={}
var moving_navigation: Array[int]=[]
var connection_queue: Array[Vector2i]=[]
var connection_cursor := 0
var connection_results: Dictionary={}
var connection_pending := false

static func shuttle_offset(time: float, spec: Dictionary) -> float:
	var distance := float(spec.distance)
	var phase := fposmod(float(spec.start)+time*float(spec.speed),2.0*distance)
	return (phase if phase<=distance else 2.0*distance-phase)-float(spec.start)

static func transform_at(time: float, section: Dictionary) -> Transform3D:
	var spec: Dictionary = section.motion
	var origin := Vector3(float(section.position[0]),float(section.position[2]),-float(section.position[1]))
	if spec.kind=="rotation":
		# Godot's negative Y rotation is clockwise from overhead.
		var basis := Basis(Vector3.UP,-time*float(spec.rim_speed)/float(spec.radius))
		return Transform3D(basis,origin-basis*origin)
	var bob := float(spec.bob_amplitude)*sin(time*float(spec.bob_peak_speed)/float(spec.bob_amplitude))
	return Transform3D(Basis.IDENTITY,MapCatalog.vector(spec.axis)*shuttle_offset(time,spec)+Vector3.UP*bob)

func install(map_node) -> void:
	arena = map_node
	traffic=CrossingTraffic.new(self,arena)
	skeleton = Assets.find(arena.model,"Skeleton3D") as Skeleton3D
	var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(arena.config.metadata))
	deck_sections=metadata.deck_sections
	for section in metadata.deck_sections:
		if not section.has("motion"):continue
		section["bone"] = skeleton.find_bone("Deck_"+String(section.name))
		assert(section.bone>=0,"Missing authored carrier bone")
		sections.append(section)
	for fixture in arena.fixtures:
		var mount: Node = fixture.node
		while mount!=null and not mount.has_meta("moving_platform"):mount=mount.get_parent()
		if mount==null:continue
		contacts.append({"fixture":fixture,"local":fixture.node.to_local(fixture.point)})

func sample(time: float) -> void:
	for section in sections:
		var transform := transform_at(time,section)
		skeleton.set_bone_pose_position(int(section.bone),transform.origin)
		skeleton.set_bone_pose_rotation(int(section.bone),transform.basis.get_rotation_quaternion())
	skeleton.force_update_all_bone_transforms()
	for contact in contacts:
		var fixture: Dictionary = contact.fixture
		fixture.point = fixture.node.to_global(contact.local)
	for fixture in arena.fixtures:
		if fixture.kind!="thruster":continue
		var marker: Dictionary={}
		for candidate in arena.markers:
			if candidate.name==fixture.id:marker=candidate;break
		for section in sections:
			if marker.get("deck","")!=section.name:continue
			if section.motion.kind!="shuttle":continue
			var velocity := shuttle_offset(time+0.02,section.motion)-shuttle_offset(time,section.motion)
			# Clips are named for exhaust direction, opposite to thrust.
			# Convert world travel into the native mounted thruster frame.
			var direction: Vector3=fixture.node.global_basis.inverse()*(Vector3.FORWARD if velocity>0 else Vector3.BACK)
			var clip := "vector_front" if direction.z>0 else "vector_back"
			if String(fixture.motion.channels.main.clip)!=clip:fixture.motion.play(clip,true)
	if arena.game.authority and not navigation_points.is_empty():update_navigation(time)

func capture_navigation() -> void:
	navigation_points.clear();boundary_points.clear();dynamic_edges.clear();local_routes.clear()
	deck_navigation.clear()
	waypoint_order.clear();moving_navigation.clear()
	connection_queue.clear();connection_cursor=0
	connection_results.clear();connection_pending=false
	for navigation in [arena.traversal.graph,arena.traversal.basic_graph]:navigation.corridor_nodes.clear()
	var graph: AStar3D=arena.nav
	var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(arena.config.metadata))
	for id in graph.get_point_ids():
		var point := graph.get_point_position(id)
		var deck_name := ""
		var near_edge := false
		for section in metadata.deck_sections:
			var local := Vector2(point.x-float(section.position[0]),-point.z-float(section.position[1]))
			for rect in section.rects:
				if local.x<float(rect[0])-.05 or local.x>float(rect[2])+.05 or local.y<float(rect[1])-.05 or local.y>float(rect[3])+.05:continue
				deck_name=String(section.name)
				near_edge=minf(minf(local.x-float(rect[0]),float(rect[2])-local.x),minf(local.y-float(rect[1]),float(rect[3])-local.y))<1.25
				break
			if not deck_name.is_empty():break
		navigation_points[id]={"rest":point,"deck":deck_name}
		if deck_name in arena.config.moving_decks:moving_navigation.append(id)
		if not deck_navigation.has(deck_name):deck_navigation[deck_name]=[]
		deck_navigation[deck_name].append(id)
		var corridor:=1 if deck_name=="Junction" else 2 if "Floater" in deck_name else 0
		for navigation in [arena.traversal.graph,arena.traversal.basic_graph]:navigation.corridor_nodes[id]=corridor
		if near_edge:boundary_points.append(id)
	# Inter-deck routes are evaluated against current physical support and arc
	# clearance; never retain a connection into a former platform position.
	for id in graph.get_point_ids():
		for other in graph.get_point_connections(id):
			var edge:=Vector2i(id,other)
			if arena.traversal.actions.get(edge,"") in ["jump","charged_jump"] and (on_launch_pad(graph.get_point_position(id)) or on_launch_pad(graph.get_point_position(other))):
				remove_edge(edge)
				continue
			if navigation_points[id].deck==navigation_points[other].deck:continue
			if navigation_points[id].deck not in arena.config.moving_decks and navigation_points[other].deck not in arena.config.moving_decks:continue
			remove_edge(Vector2i(id,other))
	for table in [arena.traversal.entries,arena.traversal.destinations,arena.traversal.jump_waypoints]:
		for edge in table:
			if not navigation_points.has(edge.x) or not navigation_points.has(edge.y):continue
			var deck_name: String=navigation_points[edge.x].deck
			if deck_name!=navigation_points[edge.y].deck or deck_name not in arena.config.moving_decks:continue
			local_routes.append({"table":table,"edge":edge,"deck":deck_name,"rest":table[edge]})
	next_links=0.0

func on_launch_pad(point: Vector3) -> bool:
	for fixture in arena.fixtures:
		if fixture.kind!="jump_pad":continue
		if Vector2(point.x-fixture.point.x,point.z-fixture.point.z).length()<1.25:return true
	return false

func remove_edge(edge: Vector2i) -> void:
	for graph in [arena.traversal.graph,arena.traversal.basic_graph]:
		if graph.are_points_connected(edge.x,edge.y,false):graph.disconnect_points(edge.x,edge.y,false)
	for table in [arena.traversal.actions,arena.traversal.entries,arena.traversal.destinations,arena.traversal.jump_waypoints,arena.traversal.crouched_jumps]:table.erase(edge)

func bind_route(route: Array) -> void:
	for step in route:
		for field in ["point","from","entry","via"]:
			var point: Vector3=step.get(field,Vector3.INF)
			if point==Vector3.INF:continue
			var id: int=arena.nav.get_closest_point(point)
			if not navigation_points.has(id):continue
			var deck_name: String=navigation_points[id].deck
			for section in sections:
				if section.name!=deck_name:continue
				var frame:=transform_at(arena.game.elapsed,section)
				step[field+"_carrier"]={"deck":deck_name,"local":frame.affine_inverse()*point}

func advance_route(route: Array) -> void:
	var frames: Dictionary={}
	for section in sections:frames[section.name]=transform_at(arena.game.elapsed,section)
	for step in route:
		for field in ["point","from","entry","via"]:
			if not step.has(field+"_carrier"):continue
			var frame: Dictionary=step[field+"_carrier"]
			step[field]=frames[frame.deck]*frame.local

func jump_reachable(step: Dictionary,height: float) -> bool:
	var effective: float=arena.game.jump_release_height(height)
	var speed:=sqrt(2.0*arena.game.gravity*effective)
	var flight: float=effective/speed+(speed+sqrt(speed*speed+2.0*arena.game.gravity*effective))/arena.game.gravity
	var landing: Vector3=step.point
	if step.has("point_carrier"):
		var frame: Dictionary=step.point_carrier
		for section in sections:
			if section.name==frame.deck:landing=transform_at(arena.game.elapsed+flight,section)*frame.local
	if step.from.distance_to(landing)>ArenaTuning.RUN_SPEED*flight*.9:return false
	return arena.traversal.arc_clear(step.from,step.point,height)

func update_navigation(time: float) -> void:
	var frames: Dictionary={}
	for section in sections:frames[section.name]=transform_at(time,section)
	for id in moving_navigation:
		var info: Dictionary=navigation_points[id]
		if not frames.has(info.deck):continue
		var point: Vector3=frames[info.deck]*info.rest
		arena.traversal.graph.set_point_position(id,point)
		arena.traversal.basic_graph.set_point_position(id,point)
	for route in local_routes:route.table[route.edge]=frames[route.deck]*route.rest
	# Paths cache node IDs; their coordinates are read live by the route builder.
	# Connection refresh below invalidates paths when docking links change.
	for graph in [arena.traversal.graph,arena.traversal.basic_graph]:
		if not graph.portal_nodes.is_empty():
			graph.heuristic_fields.clear();graph.target_costs.clear()
	if connection_cursor>=connection_queue.size() and time>=next_links:
		next_links=time+0.5
		prepare_connections()
	# Spread collision/arc checks across physics ticks instead of doing a
	# complete docking rebuild in one frame. Deck poses still update at 60 Hz.
	var deadline:=Time.get_ticks_usec()+1500
	while connection_cursor<connection_queue.size():
		var edge:=connection_queue[connection_cursor]
		connection_cursor+=1
		var p: Vector3=arena.nav.get_point_position(edge.x)
		var q: Vector3=arena.nav.get_point_position(edge.y)
		var kind:=""
		if not on_launch_pad(p) and not on_launch_pad(q):
			if p.distance_to(q)<1.8 and absf(p.y-q.y)<.25 and arena.traversal.supported(p.lerp(q,.5)) and arena.traversal.movement_clear(p,q):kind="walk"
			elif p.distance_squared_to(q)<=49.0:
				if arena.traversal.arc_clear(p,q,ArenaTuning.NORMAL_JUMP_HEIGHT) and arena.traversal.arc_clear(q,p,ArenaTuning.NORMAL_JUMP_HEIGHT):kind="jump"
				elif arena.traversal.arc_clear(p,q,ArenaTuning.CHARGED_JUMP_HEIGHT) and arena.traversal.arc_clear(q,p,ArenaTuning.CHARGED_JUMP_HEIGHT):kind="charged_jump"
		if not kind.is_empty():connection_results[edge]=kind
		if Time.get_ticks_usec()>=deadline:break
	if connection_pending and connection_cursor>=connection_queue.size():commit_connections()

func invalidate_paths() -> void:
	for graph in [arena.traversal.graph,arena.traversal.basic_graph]:graph.refresh_portal_metric()

func prepare_connections() -> void:
	connection_queue.clear();connection_cursor=0
	connection_results.clear();connection_pending=true
	var buckets: Dictionary={}
	for id in boundary_points:
		var p: Vector3=arena.nav.get_point_position(id)
		var key:=Vector2i(floori(p.x/7.0),floori(p.z/7.0))
		if not buckets.has(key):buckets[key]=[]
		buckets[key].append(id)
	var checked: Dictionary={}
	for id in boundary_points:
		var info: Dictionary=navigation_points[id]
		if info.deck not in arena.config.moving_decks:continue
		var p: Vector3=arena.nav.get_point_position(id)
		var key:=Vector2i(floori(p.x/7.0),floori(p.z/7.0))
		var nearest: Dictionary={}
		for dx in range(-1,2):
			for dz in range(-1,2):
				for other in buckets.get(key+Vector2i(dx,dz),[]):
					var deck_name: String=navigation_points[other].deck
					if deck_name==info.deck:continue
					var q: Vector3=arena.nav.get_point_position(other)
					var distance:=p.distance_squared_to(q)
					if distance>49.0:continue
					if not nearest.has(deck_name) or distance<nearest[deck_name].distance:nearest[deck_name]={"id":other,"distance":distance}
		for destination in nearest.values():
			var other: int=destination.id
			var edge:=Vector2i(mini(id,other),maxi(id,other))
			if checked.has(edge):continue
			checked[edge]=true
			connection_queue.append(edge)

func commit_connections() -> void:
	# Publish one consistent graph revision after the staged physical checks.
	# Retain unchanged edges and invalidate cached paths once per revision.
	var changed:=false
	for edge in dynamic_edges.duplicate():
		var key:=Vector2i(mini(edge.x,edge.y),maxi(edge.x,edge.y))
		if String(connection_results.get(key,""))==String(arena.traversal.actions.get(edge,"")):continue
		remove_edge(edge);dynamic_edges.erase(edge);changed=true
	for edge: Vector2i in connection_results:
		var kind: String=connection_results[edge]
		if String(arena.traversal.actions.get(edge,""))==kind:continue
		arena.traversal.link(arena.nav.get_point_position(edge.x),arena.nav.get_point_position(edge.y),kind,true)
		dynamic_edges.append(edge);dynamic_edges.append(Vector2i(edge.y,edge.x));changed=true
	if changed:invalidate_paths()
	connection_pending=false

func walk_reachable(step: Dictionary) -> bool:
	var source: Vector3=step.from
	var destination: Vector3=step.point
	return source.distance_to(destination)<1.8 and absf(source.y-destination.y)<.25 and arena.traversal.supported(source.lerp(destination,.5)) and arena.traversal.movement_clear(source,destination)

func remote_tick(dt: float) -> void:
	if arena.game.phase!="Active":return
	if not is_equal_approx(last_remote_clock,arena.game.elapsed):
		last_remote_clock=arena.game.elapsed
		remote_ahead=0.0
	else:remote_ahead=minf(remote_ahead+dt,0.1)
	sample(last_remote_clock+remote_ahead)
