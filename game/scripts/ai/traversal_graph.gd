class_name TraversalGraph
extends RefCounted
var arena
var jump_waypoints: Dictionary={}
var crouched_jumps: Dictionary={}
var planning_cache_enabled := true
var planning_queries_active := false
var planning_movement_queries: Dictionary = {}
var reuse_query_shapes := false
var movement_capsule: CapsuleShape3D
var standing_capsule: CapsuleShape3D

func begin_planning_queries() -> void:
	assert(not planning_queries_active)
	planning_movement_queries.clear()
	planning_queries_active = planning_cache_enabled

func end_planning_queries() -> void:
	planning_queries_active = false
	planning_movement_queries.clear()
static var profile_paths := false
static var path_stats: Dictionary = {}
class TraversalAStar extends PortalAStar3D:
	var transitions: Dictionary={}
	var portal_nodes: Array[int]=[]
	var portal_metric: Array=[]
	var target_costs: Dictionary={}
	var heuristic_fields: Dictionary={}
	var path_cache: Dictionary={}
	func cached_path(from_id: int,to_id: int) -> PackedInt64Array:
		var key:=Vector2i(from_id,to_id)
		if not path_cache.has(key):
			if path_cache.size()>=1024:path_cache.erase(path_cache.keys()[0])
			var started := Time.get_ticks_usec() if TraversalGraph.profile_paths else 0
			path_cache[key]=get_id_path(from_id,to_id)
			if TraversalGraph.profile_paths:
				var elapsed := Time.get_ticks_usec()-started
				TraversalGraph.path_stats["calls"] = int(TraversalGraph.path_stats.get("calls",0))+1
				TraversalGraph.path_stats["total_us"] = int(TraversalGraph.path_stats.get("total_us",0))+elapsed
				TraversalGraph.path_stats["max_us"] = maxi(int(TraversalGraph.path_stats.get("max_us",0)),elapsed)
		return path_cache[key]
	func _compute_cost(from_id: int,to_id: int) -> float:
		if transitions.get(Vector2i(from_id,to_id))=="portal":return 3.0
		return get_point_position(from_id).distance_to(get_point_position(to_id))
	func refresh_portal_metric():
		path_cache.clear()
		if native_costs_enabled:
			var connections := PackedInt64Array()
			for edge in transitions:
				if transitions[edge] == "portal":
					connections.append(edge.x)
					connections.append(edge.y)
			configure_portal_connections(connections, 3.0)
			return
		portal_nodes.clear();portal_metric.clear();target_costs.clear();heuristic_fields.clear()
		for edge in transitions:
			if transitions[edge]!="portal":continue
			for endpoint in [edge.x,edge.y]:
				if endpoint not in portal_nodes:portal_nodes.append(endpoint)
		for i in portal_nodes.size():
			var row: Array[float]=[]
			for j in portal_nodes.size():
				row.append(3.0 if transitions.get(Vector2i(portal_nodes[i],portal_nodes[j]))=="portal" else get_point_position(portal_nodes[i]).distance_to(get_point_position(portal_nodes[j])))
			portal_metric.append(row)
		for k in portal_nodes.size():
			for i in portal_nodes.size():
				for j in portal_nodes.size():portal_metric[i][j]=minf(portal_metric[i][j],portal_metric[i][k]+portal_metric[k][j])
	func _estimate_cost(from_id: int,to_id: int) -> float:
		if heuristic_fields.has(to_id) and heuristic_fields[to_id].has(from_id):return heuristic_fields[to_id][from_id]
		if not heuristic_fields.has(to_id):
			if heuristic_fields.size()>=96:heuristic_fields.erase(heuristic_fields.keys()[0])
			heuristic_fields[to_id]={}
		var destination:=get_point_position(to_id)
		if not target_costs.has(to_id):
			var tails: Array[float]=[]
			for i in portal_nodes.size():
				var best:=INF
				for j in portal_nodes.size():best=minf(best,portal_metric[i][j]+get_point_position(portal_nodes[j]).distance_to(destination))
				tails.append(best)
			target_costs[to_id]=tails
		var source:=get_point_position(from_id)
		var result:=source.distance_to(destination)
		for i in portal_nodes.size():result=minf(result,source.distance_to(get_point_position(portal_nodes[i]))+target_costs[to_id][i])
		heuristic_fields[to_id][from_id]=result
		return result

var graph:=TraversalAStar.new()
var basic_graph:=TraversalAStar.new()
var actions: Dictionary={}
var cells: Dictionary={}
var entries: Dictionary={}
var destinations: Dictionary={}
var portal_points: Array[Vector3]=[]

func _init(map):
	arena=map
	graph.transitions=actions
	basic_graph.transitions=actions

func build():
	_begin_build()
	var bounds: Dictionary=arena.config.navigation
	for level in bounds.levels:
		for x in range(bounds.min_x,bounds.max_x+1): _sample_column(level,x,bounds)
	var columns := _collect_columns()
	for cell in cells: _connect_cell(cell,columns)
	_build_links()
	for cell in cells: _discover_gaps(cell)

func build_async() -> void:
	_begin_build()
	var bounds: Dictionary=arena.config.navigation
	var batch_started := Time.get_ticks_usec()
	for level in bounds.levels:
		for x in range(bounds.min_x,bounds.max_x+1):
			_sample_column(level,x,bounds)
			if Time.get_ticks_usec()-batch_started>=8000:
				await arena.get_tree().process_frame
				batch_started=Time.get_ticks_usec()
	var columns := _collect_columns()
	for cell in cells:
		_connect_cell(cell,columns)
		if Time.get_ticks_usec()-batch_started>=8000:
			await arena.get_tree().process_frame
			batch_started=Time.get_ticks_usec()
	_build_links()
	for cell in cells:
		_discover_gaps(cell)
		if Time.get_ticks_usec()-batch_started>=8000:
			await arena.get_tree().process_frame
			batch_started=Time.get_ticks_usec()

func _begin_build() -> void:
	for fixture in arena.fixtures:
		if fixture.kind=="portal": portal_points.append(fixture.point)

func snapshot() -> Dictionary:
	var topology: Array[Dictionary]=[]
	for navigation in [graph,basic_graph]:
		var points: Array[Dictionary]=[]
		for id in navigation.get_point_ids():
			points.append({"id":id,"point":navigation.get_point_position(id),"connections":navigation.get_point_connections(id)})
		topology.append({"points":points,"portal_nodes":navigation.portal_nodes.duplicate()})
	return {"topology":topology,"cells":cells.duplicate(true),"actions":actions.duplicate(true),"entries":entries.duplicate(true),"destinations":destinations.duplicate(true),"jump_waypoints":jump_waypoints.duplicate(true),"crouched_jumps":crouched_jumps.duplicate(true),"portal_points":portal_points.duplicate()}

func restore_snapshot(data: Dictionary) -> void:
	cells=data.cells.duplicate(true)
	actions=data.actions.duplicate(true)
	entries=data.entries.duplicate(true)
	destinations=data.destinations.duplicate(true)
	jump_waypoints=data.jump_waypoints.duplicate(true)
	crouched_jumps=data.crouched_jumps.duplicate(true)
	portal_points.assign(data.portal_points)
	for index in 2:
		var navigation=graph if index==0 else basic_graph
		navigation.transitions=actions
		for point in data.topology[index].points: navigation.add_point(point.id,point.point)
		for point in data.topology[index].points:
			for connection in point.connections: navigation.connect_points(point.id,connection,false)
		navigation.portal_nodes.assign(data.topology[index].portal_nodes)
		navigation.refresh_portal_metric()

func _sample_column(level: float,x: int,bounds: Dictionary) -> void:
	for z in range(bounds.min_z,bounds.max_z+1):
		var point:=Vector3(x,level,z)
		_sample_surface(point,level+0.4,level-0.45)
		if is_zero_approx(level) and bounds.has("terrain_scan"):
			_sample_surface(point,float(bounds.terrain_scan[1]),float(bounds.terrain_scan[0]))

func _sample_surface(point: Vector3,top: float,bottom: float) -> void:
	var surface: Dictionary=arena.game.combat.ray(Vector3(point.x,top,point.z),Vector3(point.x,bottom,point.z),[],1)
	if surface.is_empty() or surface.normal.y<0.65:return
	point.y=surface.position.y+0.015
	# Quantize support rather than the half-centimetre-boundary foot clearance.
	var cell:=Vector3i(roundi(point.x),roundi(float(surface.position.y)*100),roundi(point.z))
	if cells.has(cell) or not supported(point) or not standing_clear(point):return
	if not arena.game.combat.clear(point+Vector3.UP*0.4,point+Vector3.UP*1.7):return
	var id:=graph.get_available_point_id()
	graph.add_point(id,point)
	basic_graph.add_point(id,point)
	cells[cell]=id

func _collect_columns() -> Dictionary:
	var columns: Dictionary={}
	for cell in cells:
		var column:=Vector2i(cell.x,cell.z)
		if not columns.has(column):columns[column]=[]
		columns[column].append(cells[cell])
	return columns

func _connect_cell(cell: Vector3i,columns: Dictionary) -> void:
	for offset in [Vector2i(1,0),Vector2i(0,1),Vector2i(1,1),Vector2i(-1,1)]:
		var column: Vector2i=Vector2i(cell.x,cell.z)+offset
		for b in columns.get(column,[]):
			var a: int=cells[cell]
			var start:=graph.get_point_position(a)
			var finish:=graph.get_point_position(b)
			if absf(start.y-finish.y)>0.25 and not continuous_grade(start,finish):continue
			if supported(start.lerp(finish,0.5)) and not crosses_portal(start,finish) and movement_clear(start,finish):
				graph.connect_points(a,b)
				basic_graph.connect_points(a,b)

func continuous_grade(start: Vector3,finish: Vector3) -> bool:
	# Larger height differences are walkable only along supported slopes, never
	# by treating a tall stair, ledge or gap as a shallow step.
	if not arena.config.navigation.has("terrain_scan"):return false
	var horizontal:=Vector2(finish.x-start.x,finish.z-start.z).length()
	if horizontal<0.001 or absf(finish.y-start.y)>horizontal*tan(deg_to_rad(40.0)):return false
	for sample in range(9):
		var point:=start.lerp(finish,float(sample)/8.0)
		var hit: Dictionary=arena.game.combat.ray(point+Vector3.UP*.2,point-Vector3.UP*.2,[],1)
		if hit.is_empty() or hit.normal.y<cos(deg_to_rad(40.0)) or absf(hit.position.y-point.y)>.12:return false
	return true

func _build_links() -> void:
	for pair in arena.config.portal_pairs:
		var from=arena.fixture_by_id(pair[0])
		var to=arena.fixture_by_id(pair[1])
		if from and to:
			add_portal_links(from,to)
			add_portal_links(to,from)
	for ramp in arena.config.get("walk_routes",[]): add_walk_route(ramp)
	for spawn in arena.spawns:
		if spawn.action=="open":add_spawn_exit(spawn)
	for jump in arena.config.jump_links:
		var entry: Vector3=arena.world_point(jump.from)
		link(entry,arena.world_point(jump.to),"launch",false,entry)
	for jump in arena.config.get("normal_jump_links",[]):
		var from: Vector3=arena.world_point(jump.from);var to: Vector3=arena.world_point(jump.to)
		for endpoint in [0,1]:
			var point: Vector3=from if endpoint==0 else to
			var floor: Dictionary=arena.game.combat.ray(point+Vector3.UP*.8,point-Vector3.UP*.45,[],1)
			if not floor.is_empty():point.y=floor.position.y+.015
			if endpoint==0:from=point
			else:to=point
		if standing_clear(from) and standing_clear(to) and supported(from) and supported(to):
			link(from,to,"jump",false,from)
			if jump.has("via"):jump_waypoints[Vector2i(graph.get_closest_point(from),graph.get_closest_point(to))]=arena.world_point(jump.via)
			if jump.get("crouch",false):crouched_jumps[Vector2i(graph.get_closest_point(from),graph.get_closest_point(to))]=true
	for drop in arena.config.drop_links: link(arena.world_point(drop.from),arena.world_point(drop.to),"drop",false)
	for lift in arena.config.get("lift_links",[]):
		link(arena.world_point(lift.lower_exit),arena.world_point(lift.upper_exit),"lift",true)
	for ramp in arena.config.get("speed_ramp_links",[]):
		var fixture=arena.fixture_by_id(ramp.fixture)
		if fixture == null:continue
		var destination: Vector3=arena.world_point(ramp.to)
		var impulse: Vector3=arena.speed_ramp_velocity(fixture,float(ramp.speed))
		var lip: Vector3=fixture.launch_mount.global_position
		var discriminant: float=impulse.y*impulse.y+2*arena.game.gravity*(lip.y-destination.y)
		if discriminant<0:continue
		var flight: float=(impulse.y+sqrt(discriminant))/arena.game.gravity
		var landing: Vector3=lip+impulse*flight-Vector3.UP*arena.game.gravity*flight*flight/2
		var clear:=landing.distance_to(destination)<0.8 and supported(destination)
		for sample in range(1,20):
			var time: float=flight*sample/20
			if not standing_clear(lip+impulse*time-Vector3.UP*arena.game.gravity*time*time/2):clear=false;break
		if clear:
			var forward:=Vector3(impulse.x,0,impulse.z).normalized()
			link(fixture.point-forward*0.9,destination,"speed_ramp",false,fixture.point+forward*0.1)

func _discover_gaps(cell: Vector3i) -> void:
	for step in [Vector3i(1,0,0),Vector3i(-1,0,0),Vector3i(0,0,1),Vector3i(0,0,-1)]:
		if cells.has(cell+step) and graph.are_points_connected(cells[cell],cells[cell+step]): continue
		for distance in range(1,8):
			if not cells.has(cell+step*distance): continue
			if graph.are_points_connected(cells[cell],cells[cell+step*distance]): break
			var a: Vector3=graph.get_point_position(cells[cell])
			var b: Vector3=graph.get_point_position(cells[cell+step*distance])
			if arc_clear(a,b,ArenaTuning.NORMAL_JUMP_HEIGHT) and arc_clear(b,a,ArenaTuning.NORMAL_JUMP_HEIGHT):
				link(a,b,"jump",true)
				break
			if arc_clear(a,b,ArenaTuning.CHARGED_JUMP_HEIGHT) and arc_clear(b,a,ArenaTuning.CHARGED_JUMP_HEIGHT):
				link(a,b,"charged_jump",true)
				break

func add_spawn_exit(spawn: Dictionary):
	# The narrow native chamber has no interior sample on a one-metre grid.
	# Reserve a directed departure along PlayerMount's native front axis.
	# Its door can be closed during the bake; spawn protection ends after open.
	var start: Vector3=spawn.mount.global_position+Vector3.UP*0.015
	var normal: Vector3=spawn.mount.global_basis.z.normalized()
	normal.y=0;normal=normal.normalized()
	var origin: Vector3=spawn.node.global_position
	var threshold: Vector3=origin+normal*1.4+Vector3.UP*0.015
	var best:=INF;var exit:=-1
	for candidate in graph.get_point_ids():
		var point:=graph.get_point_position(candidate)
		var delta:=point-origin
		if absf(delta.y)>0.2 or delta.dot(normal)<1.4:continue
		if absf(delta.dot(normal.cross(Vector3.UP)))>0.8:continue
		var distance:=point.distance_to(threshold)
		if distance>1.5 or distance>=best or not movement_clear(threshold,point):continue
		best=distance;exit=candidate
	if exit<0:return
	var first:=graph.get_available_point_id()
	var second:=first+1
	for nav in [graph,basic_graph]:
		nav.add_point(first,start);nav.add_point(second,threshold)
		nav.connect_points(first,second,false);nav.connect_points(second,exit,false)
	actions[Vector2i(first,second)]="drop"
	destinations[Vector2i(first,second)]=threshold

func supported(point: Vector3) -> bool:
	for offset in [Vector3.ZERO,Vector3(0.32,0,0),Vector3(-0.32,0,0),Vector3(0,0,0.32),Vector3(0,0,-0.32)]:
		var hit: Dictionary=arena.game.combat.ray(point+offset+Vector3.UP*0.4,point+offset-Vector3.UP*0.45,[],1)
		if hit.is_empty() or hit.normal.y<0.65: return false
	return true

func add_walk_route(points: Array):
	var previous := -1
	for segment in range(points.size()-1):
		var a: Vector3 = arena.world_point(points[segment])
		var b: Vector3 = arena.world_point(points[segment+1])
		var steps := maxi(1,ceili(a.distance_to(b)/0.5))
		for step in range(steps+1):
			var point := a.lerp(b,float(step)/steps)
			var surface: Dictionary = arena.game.combat.ray(point+Vector3.UP*0.45,point-Vector3.UP*0.45,[],1)
			if not surface.is_empty(): point.y = maxf(point.y,surface.position.y+0.015)
			if not supported(point) or not standing_clear(point): previous = -1; continue
			var neighbours: Array[int]=[]
			for candidate in graph.get_point_ids():
				if graph.get_point_position(candidate).distance_to(point)<0.8:neighbours.append(candidate)
			var id := graph.get_available_point_id()
			graph.add_point(id,point)
			basic_graph.add_point(id,point)
			if previous >= 0 and movement_clear(graph.get_point_position(previous),point):
				graph.connect_points(previous,id)
				basic_graph.connect_points(previous,id)
			for neighbour in neighbours:
				if not movement_clear(graph.get_point_position(neighbour),point):continue
				graph.connect_points(neighbour,id)
				basic_graph.connect_points(neighbour,id)
			previous = id

func movement_clear(start: Vector3,finish: Vector3) -> bool:
	if not planning_queries_active: return movement_clear_uncached(start,finish)
	if not planning_movement_queries.has(start): planning_movement_queries[start] = {}
	var destinations: Dictionary = planning_movement_queries[start]
	if destinations.has(finish):
		if profile_paths: path_stats["movement_cache_hits"] = int(path_stats.get("movement_cache_hits",0))+1
		return destinations[finish]
	var clear := movement_clear_uncached(start,finish)
	destinations[finish] = clear
	if profile_paths: path_stats["movement_cache_misses"] = int(path_stats.get("movement_cache_misses",0))+1
	return clear

func movement_clear_uncached(start: Vector3,finish: Vector3) -> bool:
	# Rays test both sides of thin authored architecture as well as the sweep.
	for height in [.4,.9,1.65]:
		if not arena.game.combat.clear(start+Vector3.UP*height,finish+Vector3.UP*height) or not arena.game.combat.clear(finish+Vector3.UP*height,start+Vector3.UP*height):return false
	var shape := movement_capsule if reuse_query_shapes else null
	if shape == null:
		shape = CapsuleShape3D.new();shape.radius=.32;shape.height=1.75
		if reuse_query_shapes: movement_capsule = shape
	var query:=PhysicsShapeQueryParameters3D.new();query.shape=shape;query.collision_mask=1;query.margin=.001
	# Shallow thresholds use the same maximum climb as the walk graph.
	query.transform=Transform3D(Basis.IDENTITY,Vector3(start.x,maxf(start.y,finish.y)+.9,start.z))
	query.motion=Vector3(finish.x-start.x,0,finish.z-start.z)
	var result: PackedFloat32Array=arena.get_world_3d().direct_space_state.cast_motion(query)
	if result.size()==2 and result[0]>.999:return true
	# A stone between grid samples can be lower than the motor's supported
	# step even when both endpoints lie on level ground. Sweep the complete
	# raised capsule, including headroom, before classifying it as a jump.
	for height in [.1,.15,.2,.25,ArenaTuning.STEP_HEIGHT]:
		if height>ArenaTuning.STEP_HEIGHT:continue
		query.transform.origin.y=maxf(start.y,finish.y)+.9+height
		if not arena.get_world_3d().direct_space_state.intersect_shape(query,1).is_empty():continue
		result=arena.get_world_3d().direct_space_state.cast_motion(query)
		if result.size()==2 and result[0]>.999:return true
	return false

func standing_clear(point: Vector3) -> bool:
	var capsule := standing_capsule if reuse_query_shapes else null
	if capsule == null:
		capsule = CapsuleShape3D.new()
		capsule.radius = 0.32
		capsule.height = 1.72
		if reuse_query_shapes: standing_capsule = capsule
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.transform = Transform3D(Basis.IDENTITY,point+Vector3.UP*0.88)
	query.collision_mask = 1
	query.margin = 0.001
	return arena.get_world_3d().direct_space_state.intersect_shape(query,1).is_empty()

func arc_clear(a: Vector3,b: Vector3,height := ArenaTuning.NORMAL_JUMP_HEIGHT) -> bool:
	if crosses_portal(a,b): return false
	var effective_height: float = arena.game.jump_release_height(height)
	var gravity: float = arena.game.gravity
	var jump_speed: float = sqrt(2.0 * gravity * effective_height)
	var powered: float = effective_height / jump_speed
	var coast: float = (jump_speed + sqrt(jump_speed * jump_speed + 2.0 * gravity * effective_height)) / gravity
	var flight: float = powered + coast
	if a.distance_to(b)>ArenaTuning.RUN_SPEED*flight*0.9: return false
	var previous:=a+Vector3.UP*0.9
	for i in range(1,13):
		var t:=float(i)/12
		var elapsed := flight*t
		var released := maxf(0.0, elapsed-powered)
		var rise := jump_speed*elapsed if elapsed <= powered else effective_height+jump_speed*released-0.5*gravity*released*released
		var next:=a.lerp(b,t)+Vector3.UP*(0.9+rise)
		if not standing_clear(next-Vector3.UP*.9) or not arena.game.combat.clear(previous,next): return false
		previous=next
	return supported(b)

func crosses_portal(a: Vector3,b: Vector3) -> bool:
	var edge: Vector3=b-a
	if edge.length_squared()<0.001: return false
	for portal in portal_points:
		if absf(portal.y-a.y)>1.0 or absf(portal.y-b.y)>1.0: continue
		var t: float=(portal-a).dot(edge)/edge.length_squared()
		t=clampf(t,0,1)
		if (a+edge*t).distance_to(portal)<1.1: return true
	return false

func portal_anchor(fixture: Dictionary,side: float) -> Vector3:
	var normal: Vector3=fixture.node.global_basis.z.normalized()*side
	var desired: Vector3=fixture.point+normal*1.5
	var best:=INF;var result:=Vector3.INF
	for id in graph.get_point_ids():
		var point:=graph.get_point_position(id)
		var delta: Vector3=point-fixture.point
		if absf(delta.y)>0.6 or delta.length()<1.2 or delta.dot(normal)<1.0:continue
		var distance:=point.distance_to(desired)
		if distance>3 or distance>=best:continue
		if not arena.game.combat.clear(point+Vector3.UP*.9,fixture.point+Vector3.UP*.9):continue
		best=distance;result=point
	return result

func add_portal_links(from: Dictionary,to: Dictionary):
	var exit:=portal_anchor(to,1.0)
	if exit==Vector3.INF:return
	for side in [-1.0,1.0]:
		var entry:=portal_anchor(from,side)
		if entry!=Vector3.INF:link(entry,exit,"portal",false,from.point)

func link(a: Vector3,b: Vector3,kind: String,bidirectional: bool,entry := Vector3.INF,reverse_entry := Vector3.INF):
	var from:=graph.get_closest_point(a)
	var to:=graph.get_closest_point(b)
	if from<0 or to<0 or from==to: return
	graph.connect_points(from,to,bidirectional)
	if kind != "charged_jump": basic_graph.connect_points(from,to,bidirectional)
	actions[Vector2i(from,to)]=kind
	if kind in ["drop","launch","speed_ramp","lift"]:destinations[Vector2i(from,to)]=b
	if kind=="jump" and entry!=Vector3.INF:destinations[Vector2i(from,to)]=b
	if kind=="lift" and bidirectional:destinations[Vector2i(to,from)]=a
	if entry != Vector3.INF: entries[Vector2i(from,to)]=entry
	if bidirectional: actions[Vector2i(to,from)]=kind
	if bidirectional and reverse_entry != Vector3.INF: entries[Vector2i(to,from)]=reverse_entry
	if kind=="portal":
		graph.refresh_portal_metric()
		basic_graph.refresh_portal_metric()

func route(a: Vector3,b: Vector3,allow_charged := true, grounded := false) -> Array:
	var nav: TraversalAStar=graph if allow_charged else basic_graph
	var start:=nav.get_closest_point(a)
	var finish:=nav.get_closest_point(b)
	if start<0 or finish<0: return []
	# Nearest by distance can be across an interior wall or outside a lift
	# landing. A grounded robot must physically reach its first walk sample.
	if grounded and absf(a.y-nav.get_point_position(start).y)<0.8 and not movement_clear(a,nav.get_point_position(start)):
		var reachable_start := -1
		var nearest := INF
		for candidate in nav.get_point_ids():
			if nav.is_point_disabled(candidate): continue
			var point := nav.get_point_position(candidate)
			var distance := a.distance_to(point)
			if distance>2.0 or distance>=nearest or absf(point.y-a.y)>.45: continue
			if crosses_portal(a,point) or not movement_clear(a,point): continue
			nearest=distance;reachable_start=candidate
		if reachable_start<0: return []
		start=reachable_start
	var recovery := Vector3.INF
	# Knockback or a pad can leave a robot on raised cover above the sampled
	# floor. Route a short physical drop off it instead of aiming at its feet.
	var offset := a.y-nav.get_point_position(start).y
	if grounded and offset>0.8 and offset<4.0:
		var best := INF
		for id in nav.get_point_ids():
			if nav.is_point_disabled(id): continue
			var landing := nav.get_point_position(id)
			var horizontal := Vector2(landing.x-a.x,landing.z-a.z).length()
			if horizontal<1.8 or horizontal>4 or absf(landing.y-nav.get_point_position(start).y)>0.5: continue
			if not standing_clear(landing): continue
			if not arena.game.combat.clear(a+Vector3.UP*0.9,Vector3(landing.x,a.y+0.9,landing.z)): continue
			if nav.cached_path(id,finish).is_empty(): continue
			var cost := horizontal+landing.distance_to(b)*0.01
			if cost<best: best=cost; recovery=landing; start=id
	var ids:=nav.cached_path(start,finish)
	var finish_recovered:=false
	if ids.is_empty() and standing_clear(b) and supported(b):
		var best:=INF
		for candidate in nav.get_point_ids():
			if nav.is_point_disabled(candidate):continue
			var point:=nav.get_point_position(candidate)
			var distance:=point.distance_to(b)
			if distance>1.75 or absf(point.y-b.y)>.25 or distance>=best:continue
			if crosses_portal(point,b) or not movement_clear(point,b):continue
			var path:=nav.cached_path(start,candidate)
			if path.is_empty():continue
			best=distance;ids=path;finish_recovered=true
	# A closed fixture can leave the nearest sample on an isolated contact tile.
	# Recover onto a nearby clear floor sample without crossing a wall or gap.
	if ids.is_empty():
		var anchor:=nav.get_point_position(start)
		var best:=INF
		for candidate in nav.get_point_ids():
			if nav.is_point_disabled(candidate):continue
			var point:=nav.get_point_position(candidate)
			var distance:=point.distance_to(anchor)
			if distance>1.75 or absf(point.y-anchor.y)>0.25 or distance>=best:continue
			if not movement_clear(a if grounded and absf(a.y-point.y)<.45 else anchor,point):continue
			var path:=nav.cached_path(candidate,finish)
			if path.is_empty():continue
			best=distance;ids=path

	var result: Array=[]
	if recovery!=Vector3.INF: result.append({"point":recovery,"action":"drop","from":a,"entry":Vector3.INF})
	for i in ids.size():
		var edge := Vector2i(ids[i-1],ids[i]) if i>0 else Vector2i(-1,-1)
		var origin: Vector3=nav.get_point_position(ids[i-1]) if i>0 else nav.get_point_position(ids[i])
		if actions.get(edge,"")=="jump" and entries.has(edge):origin=entries[edge]
		result.append({"point":destinations.get(edge,nav.get_point_position(ids[i])),"action":actions.get(edge,"walk"),"from":origin,"entry":entries.get(edge,Vector3.INF),"via":jump_waypoints.get(edge,Vector3.INF),"crouch":crouched_jumps.get(edge,false)})
	if finish_recovered:result.append({"point":b,"action":"walk","from":result[-1].point,"entry":Vector3.INF})
	elif not result.is_empty() and result[-1].point.distance_to(b)>.05 and absf(result[-1].point.y-b.y)<.45:
		if result[-1].point.distance_to(b)>2.0 or not movement_clear(result[-1].point,b): return []
		result.append({"point":b,"action":"walk","from":result[-1].point,"entry":Vector3.INF})
	return result

func sync_barricades() -> void:
	# Cached paths include failures; opening a barrier must invalidate both.
	graph.path_cache.clear()
	basic_graph.path_cache.clear()
	# Only closed barricades can change reachability. Cache their frames once
	# per update instead of rescanning the complete imported fixture catalog.
	var blockers: Array[Transform3D]=[]
	for fixture in arena.fixtures:
		if fixture.kind=="barricade" and not fixture.open:
			blockers.append(fixture.node.global_transform.affine_inverse())
	for id in graph.get_point_ids():
		var point:=graph.get_point_position(id)
		var blocked:=false
		for inverse in blockers:
			var local: Vector3=inverse*point
			if absf(local.x)<2.3 and absf(local.z)<1.25 and absf(local.y)<1.5:
				blocked=true;break
		if graph.is_point_disabled(id)!=blocked:graph.set_point_disabled(id,blocked)
		if basic_graph.is_point_disabled(id)!=blocked:basic_graph.set_point_disabled(id,blocked)
