extends GutTest

func make_graph() -> TraversalGraph:
	var traversal := TraversalGraph.new(null)
	for navigation in [traversal.graph,traversal.basic_graph]:
		for id in 3: navigation.add_point(id,Vector3(id*2,0,0))
		navigation.connect_points(0,1)
		navigation.connect_points(1,2,false)
		navigation.connect_points(0,2,false)
	traversal.actions[Vector2i(0,2)]="portal"
	traversal.entries[Vector2i(0,2)]=Vector3.UP
	traversal.destinations[Vector2i(0,2)]=Vector3(4,0,0)
	traversal.cells[Vector3i.ZERO]=0
	traversal.jump_waypoints[Vector2i(0,1)]=Vector3(1,1,0)
	traversal.crouched_jumps[Vector2i(0,1)]=true
	return traversal

func test_snapshot_restores_directed_topology_and_transition_data() -> void:
	var source := make_graph()
	var snapshot := source.snapshot()
	var restored := TraversalGraph.new(null)
	restored.restore_snapshot(snapshot)
	assert_eq(restored.snapshot(),snapshot)
	assert_eq(restored.graph.get_id_path(0,2),PackedInt64Array([0,2]))
	assert_false(restored.graph.are_points_connected(2,1,false))
	assert_eq(restored.jump_waypoints[Vector2i(0,1)],Vector3(1,1,0))

func test_matches_do_not_share_mutable_navigation_state() -> void:
	var snapshot := make_graph().snapshot()
	var first := TraversalGraph.new(null)
	var second := TraversalGraph.new(null)
	first.restore_snapshot(snapshot)
	second.restore_snapshot(snapshot)
	first.graph.set_point_disabled(1,true)
	first.actions[Vector2i(0,2)]="walk"
	first.cells.clear()
	assert_false(second.graph.is_point_disabled(1))
	assert_eq(second.actions[Vector2i(0,2)],"portal")
	assert_eq(second.cells.size(),1)
	assert_eq(snapshot.actions[Vector2i(0,2)],"portal")
