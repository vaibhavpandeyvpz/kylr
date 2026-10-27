class_name MapCarriers
extends RefCounted
## Gameplay motion samples the replicated match clock, independently of
## decorative animation budgets and Reduced Motion.
var arena
var skeleton: Skeleton3D
var sections: Array = []
var deck_sections: Array=[]
var contacts: Array = []
var spawn_contacts: Array=[]
var vector_thrusters: Array=[]
var rigid_groups: Dictionary={}
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
var bob_candidates: Array[Vector2i]=[]
var last_navigation_time: float=-INF
var world_frames: Dictionary={}
var launch_pads: Array=[]
var fixture_decks: Dictionary={}
var sections_by_name: Dictionary={}
var collision_groups: Dictionary={}

static func shuttle_offset(time: float, spec: Dictionary) -> float:
	var distance := float(spec.distance)
	var phase := fposmod(float(spec.start)+time*float(spec.speed),2.0*distance)
	return (phase if phase<=distance else 2.0*distance-phase)-float(spec.start)

static func transform_at(time: float, section: Dictionary) -> Transform3D:
	var spec: Dictionary = section.motion
	var origin := Vector3(float(section.position[0]),float(section.position[2]),-float(section.position[1]))
	if spec.kind=="bob":
		return Transform3D(Basis.IDENTITY,Vector3.UP*float(spec.bob_amplitude)*sin(TAU*time/float(spec.period)))
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
	var sockets: Dictionary={}
	for marker in arena.markers:sockets["Gizmo_"+String(marker.name).replace("-","_")]=marker.get("deck","")
	for section in metadata.deck_sections:
		if not section.has("motion"):continue
		section["bone"] = skeleton.find_bone("Deck_"+String(section.name))
		assert(section.bone>=0,"Missing authored carrier bone")
		section["rest_global"]=skeleton.get_bone_global_rest(int(section.bone))
		var parent:=skeleton.get_bone_parent(int(section.bone))
		section["parent_rest_inverse"]=skeleton.get_bone_global_rest(parent).affine_inverse() if parent>=0 else Transform3D.IDENTITY
		sections.append(section)
		sections_by_name[section.name]=section
		rigid_groups[section.name]=section.motion.get("group",section.name)
	for fixture in arena.fixtures:
		if fixture.kind=="jump_pad":launch_pads.append(fixture)
		var mount: Node = fixture.node
		while mount!=null and not mount.has_meta("moving_platform"):mount=mount.get_parent()
		if mount==null:continue
		fixture_decks[fixture.id]=sockets.get(String(mount.name),"")
		contacts.append({"fixture":fixture,"local":fixture.node.to_local(fixture.point),"deck":sockets.get(String(mount.name),""),"rest":fixture.point})
	for spawn in arena.spawns:
		var mount: Node=spawn.node
		while mount!=null and not mount.has_meta("moving_platform"):mount=mount.get_parent()
		if mount!=null:spawn_contacts.append({"spawn":spawn,"local":spawn.node.to_local(spawn.point),"deck":sockets.get(String(mount.name),""),"rest":spawn.point})
	var markers: Dictionary={}
	for marker in arena.markers:markers[marker.name]=marker
	for fixture in arena.fixtures:
		if fixture.kind!="thruster":continue
		for section in sections:
			if section.motion.kind=="shuttle" and markers.get(fixture.id,{}).get("deck","")==section.name:
				vector_thrusters.append({"fixture":fixture,"motion":section.motion})

func sample(time: float) -> void:
	world_frames.clear()
	for section in sections:
		var frame:=transform_at(time,section)
		world_frames[section.name]=frame
		var transform: Transform3D=section.parent_rest_inverse*frame*section.rest_global
		skeleton.set_bone_pose_position(int(section.bone),transform.origin)
		skeleton.set_bone_pose_rotation(int(section.bone),transform.basis.get_rotation_quaternion())
	skeleton.force_update_all_bone_transforms()
	for contact in contacts:
		var fixture: Dictionary = contact.fixture
		fixture.point = world_frames[contact.deck]*contact.rest if arena.config.get("vertical_bobbing_only",false) and world_frames.has(contact.deck) else fixture.node.to_global(contact.local)
		if fixture.kind=="repair_station":
			var current: Transform3D=world_frames.get(contact.deck,Transform3D.IDENTITY)
			var previous: Transform3D=contact.get("repair_frame",Transform3D.IDENTITY)
			contact.repair_frame=current
			if arena.game.authority and is_instance_valid(fixture.occupant) and float(fixture.elapsed)>=1.0:
				var patient=fixture.occupant
				var delta:=current*previous.affine_inverse()
				patient.global_position=delta*patient.global_position
				var yaw:=delta.basis.get_euler().y
				patient.yaw+=yaw;patient.body.rotation.y+=yaw

	for contact in spawn_contacts:
		contact.spawn.point=world_frames[contact.deck]*contact.rest if arena.config.get("vertical_bobbing_only",false) and world_frames.has(contact.deck) else Assets.socket_world_transform(contact.spawn.node)*contact.local
	if arena.config.get("vertical_bobbing_only",false):update_flags(time)
	for drive in vector_thrusters:
		var fixture: Dictionary=drive.fixture
		var velocity := shuttle_offset(time+0.02,drive.motion)-shuttle_offset(time,drive.motion)
		# Clips name exhaust direction, opposite to the native mounted thrust.
		var direction: Vector3=fixture.node.global_basis.inverse()*(Vector3.FORWARD if velocity>0 else Vector3.BACK)
		var clip := "vector_front" if direction.z>0 else "vector_back"
		if String(fixture.motion.channels.main.clip)!=clip:fixture.motion.play(clip,true)
	if arena.game.authority and not navigation_points.is_empty():update_navigation(time)

func fixture_transform(fixture: Dictionary) -> Transform3D:
	var transform:=Assets.socket_world_transform(fixture.node)
	var deck: String=fixture_decks.get(fixture.id,"")
	return world_frames[deck].affine_inverse()*transform if world_frames.has(deck) else transform

func update_flags(time: float) -> void:
	for flag in arena.game.flags:
		var home: Vector3=Assets.socket_world_transform(flag.base_effect.get_parent()).origin
		var delta: Vector3=home-flag.home
		flag.home=home
		if flag.state=="home":
			flag.point+=delta;flag.node.global_position+=delta
		if flag.state!="dropped" or flag.falling:
			flag.erase("dropped_carrier");continue
		if not flag.has("dropped_carrier") and not navigation_points.is_empty():
			var step: Dictionary={"point":flag.point}
			bind_route([step])
			if step.has("point_carrier"):flag.dropped_carrier=step.point_carrier
		if flag.has("dropped_carrier"):
			for section in sections:
				if section.name!=flag.dropped_carrier.deck:continue
				var point: Vector3=transform_at(time,section)*flag.dropped_carrier.local
				flag.node.global_position+=point-flag.point;flag.point=point

func same_rigid_group(a: String,b: String) -> bool:
	if a==b:return true
	return rigid_groups.has(a) and rigid_groups.has(b) and rigid_groups[a]==rigid_groups[b]

func capture_navigation() -> void:
	navigation_points.clear();boundary_points.clear();dynamic_edges.clear();local_routes.clear()
	deck_navigation.clear()
	waypoint_order.clear();moving_navigation.clear()
	connection_queue.clear();connection_cursor=0
	connection_results.clear();connection_pending=false
	bob_candidates.clear()
	for navigation in [arena.traversal.graph,arena.traversal.basic_graph]:navigation.corridor_nodes.clear()
	var graph: AStar3D=arena.nav
	var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(arena.config.metadata))
	for id in graph.get_point_ids():
		var point := graph.get_point_position(id)
		var deck_name := ""
		var near_edge := false
		for section in metadata.deck_sections:
			if section.get("motion",{}).get("kind","")=="bob" and absf(point.y-float(section.position[2]))>1.25:continue
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
			if arena.config.get("vertical_bobbing_only",false):
				if same_rigid_group(navigation_points[id].deck,navigation_points[other].deck):continue
				if arena.traversal.actions.get(edge,"") in ["portal","launch","speed_ramp","drop"]:continue
			if navigation_points[id].deck not in arena.config.moving_decks and navigation_points[other].deck not in arena.config.moving_decks:continue
			remove_edge(Vector2i(id,other))
	for source_key in ["entries","destinations","jump_waypoints"]:
		var table: Dictionary=arena.traversal.get(source_key)
		for edge in table:
			if not navigation_points.has(edge.x) or not navigation_points.has(edge.y):continue
			var deck_name: String=navigation_points[edge.x].deck
			if arena.config.get("vertical_bobbing_only",false):
				if source_key!="entries":deck_name=navigation_points[edge.y].deck
			elif deck_name!=navigation_points[edge.y].deck:continue
			if deck_name not in arena.config.moving_decks:continue
			local_routes.append({"table":table,"edge":edge,"deck":deck_name,"rest":table[edge]})
	next_links=0.0;last_navigation_time=-INF
	if arena.config.get("vertical_bobbing_only",false):
		prepare_connections();next_links=.5

func finish_initial_connections() -> void:
	if not arena.config.get("vertical_bobbing_only",false):return
	while connection_cursor<connection_queue.size():process_connections(8000)
	arena.traversal.prepare_portal_walks()
	last_navigation_time=arena.game.elapsed

func finish_initial_connections_async() -> void:
	if not arena.config.get("vertical_bobbing_only",false):return
	while connection_cursor<connection_queue.size():
		process_connections(8000)
		await arena.get_tree().process_frame
		if not is_instance_valid(arena) or not arena.is_inside_tree():return
	arena.traversal.prepare_portal_walks()
	last_navigation_time=arena.game.elapsed

func on_launch_pad(point: Vector3) -> bool:
	if launch_pads.is_empty():
		for fixture in arena.fixtures:
			if fixture.kind=="jump_pad":launch_pads.append(fixture)
	for fixture in launch_pads:
		if arena.config.get("vertical_bobbing_only",false) and absf(point.y-fixture.point.y)>.6:continue
		if Vector2(point.x-fixture.point.x,point.z-fixture.point.z).length()<1.25:return true
	return false

func world_point_for(id: int) -> Vector3:
	var info: Dictionary=navigation_points.get(id,{})
	if info.is_empty():return arena.nav.get_point_position(id)
	if not world_frames.has(info.deck):return info.rest
	return world_frames[info.deck]*info.rest

func query_point(point: Vector3) -> Vector3:
	var nearest:=INF;var deck:=""
	for section in sections:
		var offset: Vector3=world_frames.get(section.name,Transform3D.IDENTITY).origin
		for rect in section.rects:
			var dx:=maxf(maxf(float(rect[0])-point.x,point.x-float(rect[2])),0)
			var dz:=maxf(maxf(float(rect[1])+point.z,-point.z-float(rect[3])),0)
			var dy:=point.y-float(section.position[2])-offset.y
			var distance:=dx*dx+dz*dz+dy*dy
			if distance<nearest:nearest=distance;deck=section.name
	return point-world_frames.get(deck,Transform3D.IDENTITY).origin

func remove_edge(edge: Vector2i) -> void:
	for graph in [arena.traversal.graph,arena.traversal.basic_graph]:
		if graph.are_points_connected(edge.x,edge.y,false):
			graph.disconnect_points(edge.x,edge.y,false);graph.path_cache.clear()
		if graph is TraversalGraph.PortalTraversalAStar:graph.sync_native_edge(edge.x,edge.y)
	for table in [arena.traversal.actions,arena.traversal.entries,arena.traversal.destinations,arena.traversal.jump_waypoints,arena.traversal.crouched_jumps]:table.erase(edge)

func bind_route(route: Array) -> void:
	var bob: bool=arena.config.get("vertical_bobbing_only",false)
	var inverses: Dictionary={}
	for step in route:
		for field in ["point","from","entry","via"]:
			var point: Vector3=step.get(field,Vector3.INF)
			if point==Vector3.INF:continue
			var hint: String="_point_node" if field=="point" else "_from_node" if field in ["from","entry"] else ""
			var id: int=int(step.get(hint,-1)) if bob else -1
			if id<0:id=arena.nav.get_closest_point(query_point(point) if bob else point)
			if not navigation_points.has(id):continue
			var deck_name: String=navigation_points[id].deck
			if not sections_by_name.has(deck_name):
				for section in sections:
					if section.name==deck_name:sections_by_name[deck_name]=section;break
			if not sections_by_name.has(deck_name):continue
			if not inverses.has(deck_name):
				var frame: Transform3D=world_frames[deck_name] if bob and world_frames.has(deck_name) else transform_at(arena.game.elapsed,sections_by_name[deck_name])
				inverses[deck_name]=frame.affine_inverse()
			step[field+"_carrier"]={"deck":deck_name,"local":inverses[deck_name]*point}
		step.erase("_point_node");step.erase("_from_node")

func advance_route(route: Array) -> void:
	var frames: Dictionary=world_frames
	if not arena.config.get("vertical_bobbing_only",false) or frames.is_empty():
		frames={}
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
	if arena.config.get("vertical_bobbing_only",false):
		var discriminant: float=speed*speed+2.0*arena.game.gravity*(effective-(landing.y-step.from.y))
		if discriminant<0:return false
		flight=effective/speed+(speed+sqrt(discriminant))/arena.game.gravity
	if step.has("point_carrier"):
		var frame: Dictionary=step.point_carrier
		for section in sections:
			if section.name==frame.deck:landing=transform_at(arena.game.elapsed+flight,section)*frame.local
	var distance: float=Vector2(step.from.x-landing.x,step.from.z-landing.z).length() if arena.config.get("vertical_bobbing_only",false) else step.from.distance_to(landing)
	if distance>ArenaTuning.RUN_SPEED*flight*.9:return false
	return arena.traversal.arc_clear(step.from,step.point,height)

func update_navigation(time: float) -> void:
	if time==last_navigation_time and connection_cursor>=connection_queue.size() and time<next_links:return
	last_navigation_time=time
	var frames: Dictionary={}
	for section in sections:frames[section.name]=transform_at(time,section)
	for id in ([] if arena.config.get("vertical_bobbing_only",false) else moving_navigation):
		var info: Dictionary=navigation_points[id]
		if not frames.has(info.deck):continue
		var point: Vector3=frames[info.deck]*info.rest
		arena.traversal.graph.set_point_position(id,point)
		arena.traversal.basic_graph.set_point_position(id,point)
		for graph in [arena.traversal.graph,arena.traversal.basic_graph]:
			if graph is TraversalGraph.PortalTraversalAStar and graph.native_planner!=null:
				graph.native_planner.walking.set_point_position(id,point)
	for route in local_routes:route.table[route.edge]=frames[route.deck]*route.rest
	# Paths cache node IDs; their coordinates are read live by the route builder.
	# Connection refresh below invalidates paths when docking links change.
	if not arena.config.get("vertical_bobbing_only",false):
		for graph in [arena.traversal.graph,arena.traversal.basic_graph]:
			if graph is TraversalGraph.PortalTraversalAStar and graph.native_planner!=null:graph.native_planner.invalidate_walks()
			if not graph.portal_nodes.is_empty():
				graph.heuristic_fields.clear();graph.target_costs.clear()
	if connection_cursor>=connection_queue.size() and time>=next_links:
		next_links=time+(2.0 if arena.config.get("vertical_bobbing_only",false) else 0.5)
		prepare_connections()
	# Spread collision/arc checks across physics ticks instead of doing a
	# complete docking rebuild in one frame. Deck poses still update at 60 Hz.
	process_connections(250 if arena.config.get("vertical_bobbing_only",false) else 1500)

func process_connections(budget_usec: int) -> void:
	var deadline:=Time.get_ticks_usec()+budget_usec
	while connection_cursor<connection_queue.size():
		var edge:=connection_queue[connection_cursor]
		connection_cursor+=1
		var p: Vector3=arena.traversal.position_of(edge.x)
		var q: Vector3=arena.traversal.position_of(edge.y)
		var kind:=""
		if arena.config.get("vertical_bobbing_only",false):
			if not on_launch_pad(p) and not on_launch_pad(q):
				for direction in [edge,Vector2i(edge.y,edge.x)]:
					var a: Vector3=world_point_for(direction.x)
					var b: Vector3=world_point_for(direction.y)
					var action:=connection_kind(a,b)
					if not action.is_empty():connection_results[direction]=action
		elif not on_launch_pad(p) and not on_launch_pad(q):
			if p.distance_to(q)<1.8 and absf(p.y-q.y)<.25 and arena.traversal.supported(p.lerp(q,.5)) and arena.traversal.movement_clear(p,q):kind="walk"
			elif p.distance_squared_to(q)<=49.0:
				if arena.traversal.arc_clear(p,q,ArenaTuning.NORMAL_JUMP_HEIGHT) and arena.traversal.arc_clear(q,p,ArenaTuning.NORMAL_JUMP_HEIGHT):kind="jump"
				elif arena.traversal.arc_clear(p,q,ArenaTuning.CHARGED_JUMP_HEIGHT) and arena.traversal.arc_clear(q,p,ArenaTuning.CHARGED_JUMP_HEIGHT):kind="charged_jump"
		if not kind.is_empty():connection_results[edge]=kind
		if Time.get_ticks_usec()>=deadline:break
	if connection_pending and connection_cursor>=connection_queue.size():commit_connections()

func invalidate_paths() -> void:
	for graph in [arena.traversal.graph,arena.traversal.basic_graph]:
		if graph is TraversalGraph.PortalTraversalAStar and graph.native_routes:graph.refresh_moving_topology()
		else:graph.refresh_portal_metric()

func connection_kind(a: Vector3,b: Vector3) -> String:
	if a.distance_squared_to(b)<3.24 and absf(a.y-b.y)<.25 and arena.traversal.supported(a.lerp(b,.5)) and arena.traversal.movement_clear(a,b):return "walk"
	if arena.traversal.arc_clear(a,b,ArenaTuning.NORMAL_JUMP_HEIGHT):return "jump"
	if arena.traversal.arc_clear(a,b,ArenaTuning.CHARGED_JUMP_HEIGHT):return "charged_jump"
	return ""

func prepare_connections() -> void:
	connection_queue.clear();connection_cursor=0
	connection_results.clear();connection_pending=true
	if arena.config.get("vertical_bobbing_only",false) and not bob_candidates.is_empty():
		connection_queue.assign(bob_candidates);return
	var radius: float=float(arena.config.get("jump_search_radius",7.0))
	var buckets: Dictionary={}
	for id in boundary_points:
		var p: Vector3=arena.nav.get_point_position(id)
		var key:=Vector2i(floori(p.x/radius),floori(p.z/radius))
		if not buckets.has(key):buckets[key]=[]
		buckets[key].append(id)
	var checked: Dictionary={}
	for id in boundary_points:
		var info: Dictionary=navigation_points[id]
		if info.deck not in arena.config.moving_decks:continue
		var p: Vector3=arena.nav.get_point_position(id)
		var key:=Vector2i(floori(p.x/radius),floori(p.z/radius))
		var nearest: Dictionary={}
		for dx in range(-1,2):
			for dz in range(-1,2):
				for other in buckets.get(key+Vector2i(dx,dz),[]):
					var deck_name: String=navigation_points[other].deck
					if deck_name==info.deck:continue
					if arena.config.get("vertical_bobbing_only",false):
						if same_rigid_group(info.deck,deck_name):continue
						if arena.traversal.actions.get(Vector2i(id,other),"") in ["portal","launch","speed_ramp","drop"]:continue
						if arena.traversal.actions.get(Vector2i(other,id),"") in ["portal","launch","speed_ramp","drop"]:continue
					var q: Vector3=arena.nav.get_point_position(other)
					var distance:=p.distance_squared_to(q)
					var candidate_key: Variant=deck_name
					if arena.config.get("vertical_bobbing_only",false):
						distance=Vector2(p.x-q.x,p.z-q.z).length_squared()
						var sector:=posmod(roundi(atan2(q.z-p.z,q.x-p.x)*4/PI),8)
						candidate_key="%s:%d:%d"%[deck_name,sector,1 if distance>20.25 else 0]
					if distance>radius*radius:continue
					if not nearest.has(candidate_key) or distance<nearest[candidate_key].distance:nearest[candidate_key]={"id":other,"distance":distance}
		for destination in nearest.values():
			var other: int=destination.id
			var edge:=Vector2i(mini(id,other),maxi(id,other))
			if checked.has(edge):continue
			checked[edge]=true
			connection_queue.append(edge)
	if arena.config.get("vertical_bobbing_only",false):bob_candidates.assign(connection_queue)

func commit_connections() -> void:
	if arena.config.get("vertical_bobbing_only",false):
		commit_directed_connections();return
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

func commit_directed_connections() -> void:
	for edge in dynamic_edges.duplicate():
		if connection_results.has(edge):continue
		remove_edge(edge);dynamic_edges.erase(edge)
	for edge: Vector2i in connection_results:
		var kind: String=connection_results[edge]
		if String(arena.traversal.actions.get(edge,""))==kind:continue
		arena.traversal.link(arena.nav.get_point_position(edge.x),arena.nav.get_point_position(edge.y),kind,false)
		if edge not in dynamic_edges:dynamic_edges.append(edge)
	# Rest-frame costs and portal positions are unchanged. Link/remove update
	# only planners whose connectivity changed; action flips retain full paths.
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
