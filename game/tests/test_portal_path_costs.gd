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
