extends GutTest

func graph(native: bool) -> TraversalGraph.TraversalAStar:
	var result := TraversalGraph.TraversalAStar.new()
	result.native_costs_enabled = native
	for id in range(20):
		result.add_point(id, Vector3(id % 5, 0, id / 5) * 8.0)
	for id in range(20):
		if id % 5 < 4: result.connect_points(id,id+1)
		if id < 15: result.connect_points(id,id+5)
	result.connect_points(0,19,false)
	result.transitions[Vector2i(0,19)] = "portal"
	result.connect_points(15,4,false)
	result.transitions[Vector2i(15,4)] = "portal"
	result.refresh_portal_metric()
	return result

func compare_routes(native: TraversalGraph.TraversalAStar, legacy: TraversalGraph.TraversalAStar):
	for from_id in range(20):
		for to_id in range(20):
			assert_eq(native.get_id_path(from_id,to_id), legacy.get_id_path(from_id,to_id),
				"Native and legacy portal routing: %d -> %d" % [from_id,to_id])

func test_native_routes_match_legacy_with_directed_portals_and_barricades():
	var native := graph(true)
	var legacy := graph(false)
	assert_eq(native.get_id_path(0,19),PackedInt64Array([0,19]))
	assert_ne(native.get_id_path(19,0),PackedInt64Array([19,0]),"Portal is directional")
	compare_routes(native,legacy)
	for id in [6,7,12,15]:
		native.set_point_disabled(id)
		legacy.set_point_disabled(id)
	compare_routes(native,legacy)

func test_point_edits_and_empty_portals_invalidate_native_costs():
	var native := graph(true)
	var legacy := graph(false)
	native.get_id_path(0,19) # Populate the first metric/heuristic caches.
	native.set_point_position(19,Vector3(200,0,200))
	legacy.set_point_position(19,Vector3(200,0,200))
	legacy.refresh_portal_metric() # Native point edits invalidate automatically.
	compare_routes(native,legacy)
	for solver in [native,legacy]:
		solver.transitions.clear()
		solver.refresh_portal_metric()
	compare_routes(native,legacy)

func test_clear_does_not_retain_old_portal_connections():
	var solver := PortalAStar3D.new()
	solver.add_point(0,Vector3.ZERO)
	solver.add_point(1,Vector3(100,0,0))
	solver.add_point(2,Vector3(1,0,0))
	solver.connect_points(0,1)
	solver.connect_points(0,2)
	solver.connect_points(2,1)
	solver.configure_portal_connections(PackedInt64Array([0,1]),0.0)
	assert_eq(solver.get_id_path(0,1),PackedInt64Array([0,1]))
	solver.clear()
	solver.add_point(0,Vector3.ZERO)
	solver.add_point(1,Vector3(10,0,0),5.0)
	solver.add_point(2,Vector3(9,0,0))
	solver.connect_points(0,1)
	solver.connect_points(0,2)
	solver.connect_points(2,1)
	assert_eq(solver.get_id_path(0,1),PackedInt64Array([0,2,1]),"Old zero-cost portal must not survive clear")
