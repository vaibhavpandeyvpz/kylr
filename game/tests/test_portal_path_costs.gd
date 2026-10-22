extends GutTest

class Dijkstra extends TraversalGraph.TraversalAStar:
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
	var solver := graph(TraversalGraph.TraversalAStar.new())
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
