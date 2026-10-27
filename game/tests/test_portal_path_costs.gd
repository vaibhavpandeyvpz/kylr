extends GutTest

class Dijkstra extends TraversalGraph.PortalTraversalAStar:
	func _estimate_cost(_from: int, _to: int) -> float: return 0.0

func graph(solver: TraversalGraph.TraversalAStar) -> TraversalGraph.TraversalAStar:
	for id in range(20): solver.add_point(id,Vector3(id%5,0,id/5)*8.0)
	for id in range(20):
		if id%5<4: solver.connect_points(id,id+1)
		if id<15: solver.connect_points(id,id+5)
	for pair in [Vector2i(0,19),Vector2i(15,4)]:
		solver.connect_points(pair.x,pair.y,false)
		solver.transitions[pair]="portal"
	solver.refresh_portal_metric()
	return solver

func path_cost(solver: TraversalGraph.TraversalAStar, path: PackedInt64Array) -> float:
	var cost := 0.0
	for index in range(1,path.size()): cost+=solver._compute_cost(path[index-1],path[index])
	return cost

func test_portal_heuristic_finds_shortest_paths_with_blockers_and_point_edits():
	var solver := graph(TraversalGraph.PortalTraversalAStar.new())
	var reference := graph(Dijkstra.new())
	assert_eq(solver.get_id_path(0,19),PackedInt64Array([0,19]))
	assert_ne(solver.get_id_path(19,0),PackedInt64Array([19,0]))
	for phase in 3:
		if phase==1:
			for target in [solver,reference]:
				for id in [6,7,12,15]: target.set_point_disabled(id)
		if phase==2:
			for target in [solver,reference]:
				target.set_point_position(19,Vector3(200,0,200))
				target.refresh_portal_metric()
		for from_id in 20:
			for to_id in 20:
				assert_almost_eq(path_cost(solver,solver.get_id_path(from_id,to_id)),path_cost(reference,reference.get_id_path(from_id,to_id)),0.001)

func test_native_portal_segments_match_dijkstra_with_blockers_and_point_edits():
	var solver:=graph(TraversalGraph.PortalTraversalAStar.new()) as TraversalGraph.PortalTraversalAStar
	var reference:=graph(Dijkstra.new())
	solver.native_routes=true
	for phase in 3:
		if phase==1:
			for target in [solver,reference]:
				for id in [6,7,12,15]:target.set_point_disabled(id)
		if phase==2:
			for target in [solver,reference]:target.set_point_position(19,Vector3(200,0,200))
		for target in [solver,reference]:target.refresh_portal_metric()
		for from_id in 20:
			for to_id in 20:
				var actual:=solver.cached_path(from_id,to_id)
				var expected:=reference.get_id_path(from_id,to_id)
				assert_eq(actual.is_empty(),expected.is_empty())
				assert_almost_eq(path_cost(solver,actual),path_cost(reference,expected),.001)

func test_incremental_native_mirror_keeps_directed_edges_blockers_and_moving_costs():
	var source:=graph(Dijkstra.new())
	var planner:=NativePortalRoutes.new(source,source.transitions)
	for phase in 4:
		if phase==1:
			for id in [6,7,12]:source.set_point_disabled(id);planner.sync_disabled(id,true)
			source.disconnect_points(0,1,false);planner.sync_edge(0,1,false)
		if phase==2:
			for id in [6,7,12]:source.set_point_disabled(id,false);planner.sync_disabled(id,false)
			source.connect_points(0,1,false);planner.sync_edge(0,1,true)
		if phase==3:
			for id in 20:
				var position:=source.get_point_position(id)+Vector3.UP*sin(id*.3)*.25
				source.set_point_position(id,position);planner.walking.set_point_position(id,position)
			planner.invalidate_walks()
		for from_id in 20:
			for to_id in 20:
				var actual:=planner.path(from_id,to_id)
				var expected:=source.get_id_path(from_id,to_id)
				assert_eq(actual.is_empty(),expected.is_empty())
				assert_almost_eq(path_cost(source,actual),path_cost(source,expected),.001)

func test_enabling_a_directed_terminal_rejoins_its_incoming_component():
	var source:=AStar3D.new()
	source.add_point(0,Vector3.ZERO);source.add_point(1,Vector3.RIGHT)
	source.connect_points(0,1,false);source.set_point_disabled(1)
	var planner:=NativePortalRoutes.new(source,{})
	assert_true(planner.path(0,1).is_empty())
	planner.sync_disabled(1,false)
	assert_eq(planner.path(0,1),PackedInt64Array([0,1]))
	assert_true(planner.path(1,0).is_empty())
	planner.sync_edge(0,1,false)
	assert_true(planner.path(0,1).is_empty())

func test_native_portal_solver_can_choose_a_shorter_walk():
	var solver:=TraversalGraph.PortalTraversalAStar.new()
	for id in 3:solver.add_point(id,Vector3(id,0,0))
	solver.connect_points(0,1);solver.connect_points(1,2);solver.connect_points(0,2,false)
	solver.transitions[Vector2i(0,2)]="portal";solver.refresh_portal_metric();solver.native_routes=true
	assert_eq(solver.cached_path(0,2),PackedInt64Array([0,1,2]))

func test_native_portals_bridge_separate_walking_components_directionally():
	var solver:=TraversalGraph.PortalTraversalAStar.new()
	for id in 4:solver.add_point(id,Vector3(id*10,0,0))
	solver.connect_points(0,1);solver.connect_points(2,3);solver.connect_points(1,2,false)
	solver.transitions[Vector2i(1,2)]="portal";solver.refresh_portal_metric();solver.native_routes=true
	assert_eq(solver.cached_path(0,3),PackedInt64Array([0,1,2,3]))
	assert_true(solver.cached_path(3,0).is_empty())

func test_action_flip_retains_full_walking_cache_and_updates_basic_connectivity():
	var traversal:=TraversalGraph.new(null)
	for nav in [traversal.graph,traversal.basic_graph]:
		nav.native_routes=true
		for id in 3:nav.add_point(id,Vector3(id,0,0))
	traversal.link(Vector3.ZERO,Vector3.RIGHT,"jump",false)
	traversal.link(Vector3.RIGHT,Vector3.RIGHT*2,"walk",false)
	assert_eq(traversal.graph.cached_path(0,2),PackedInt64Array([0,1,2]))
	assert_eq(traversal.basic_graph.cached_path(0,2),PackedInt64Array([0,1,2]))
	var full: NativePortalRoutes=traversal.graph.native_planner
	var basic: NativePortalRoutes=traversal.basic_graph.native_planner
	var walks:=full.walks.size();var ids:=traversal.graph.path_cache.size()
	traversal.link(Vector3.ZERO,Vector3.RIGHT,"charged_jump",false)
	assert_same(traversal.graph.native_planner,full)
	assert_eq(full.walks.size(),walks,"Unchanged full-graph paths remain cached")
	assert_eq(traversal.graph.path_cache.size(),ids)
	assert_true(traversal.basic_graph.cached_path(0,2).is_empty())
	assert_false(basic.walking.are_points_connected(0,1,false))
	assert_eq(traversal.actions[Vector2i(0,1)],"charged_jump")
	traversal.link(Vector3.ZERO,Vector3.RIGHT,"jump",false)
	assert_eq(traversal.basic_graph.cached_path(0,2),PackedInt64Array([0,1,2]))
	assert_eq(traversal.graph.cached_path(0,2),PackedInt64Array([0,1,2]))

func test_unrelated_edges_retain_endpoint_walks_and_shortcuts_invalidate_them():
	var source:=AStar3D.new()
	var points: Array[Vector3]=[Vector3(0,0,0),Vector3(1,0,0),Vector3(1,0,10),Vector3(4,0,10),Vector3(4,0,0),Vector3(5,0,0),Vector3(100,0,100),Vector3(101,0,100)]
	for id in points.size():source.add_point(id,points[id])
	for id in 5:source.connect_points(id,id+1)
	source.connect_points(0,5,false)
	var planner:=NativePortalRoutes.new(source,{Vector2i(0,5):"portal"});planner.prepare()
	assert_eq(planner.anchor_walks.size(),4)
	assert_almost_eq(float(planner.walk(5,0).cost),25.0,.001)
	planner.sync_edge(6,7,true)
	assert_eq(planner.anchor_walks.size(),4,"A distant edge cannot shorten these endpoint walks")
	planner.sync_edge(6,7,false)
	assert_eq(planner.anchor_walks.size(),4,"Unrelated removal retains exact shortest walks")
	planner.sync_edge(2,3,false)
	assert_false(planner.anchor_walks.has(Vector2i(0,5)))
	assert_true(planner.anchor_walks.has(Vector2i(5,0)),"The unaffected reverse walk stays cached")
	planner.sync_edge(4,1,true)
	assert_false(planner.anchor_walks.has(Vector2i(5,0)),"A possible shorter walk invalidates its old cost")
	assert_almost_eq(float(planner.walk(5,0).cost),5.0,.001)
