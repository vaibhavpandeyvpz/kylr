extends GutTest

func test_cargo_container_cradle_rests_on_native_floor():
	var game := ArenaMatch.new()
	game.map_id="faceoff";game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	await wait_physics_frames(5)
	var host: Dictionary=fixture(game,"common-container-143_1757")
	var cradle: Dictionary=fixture(game,"common-item_cradle-143_1758")
	assert_false(host.is_empty())
	assert_false(cradle.is_empty())
	var container: Node3D=host.node
	var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/architecture/container/container_rig.json"))
	var floor_y: float=metadata.architecture_dimensions.rooms[0].floor_m
	assert_almost_eq(container.to_local(cradle.point).y,floor_y,.001,"Pickup origin rests on the raised cargo floor")
	assert_almost_eq(container.to_local(cradle.node.global_position).y,floor_y,.001,"Native cradle base is above the floor")

func fixture(game: ArenaMatch,prefix: String) -> Dictionary:
	for item in game.map.fixtures:
		if String(item.id).begins_with(prefix): return item
	assert_true(false,"Missing fixture: "+prefix)
	return {}

func test_habitat_ammo_is_in_front_of_cradle_with_clear_native_floor_access():
	var game := ArenaMatch.new()
	game.map_id="faceoff";game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	await wait_physics_frames(5)
	game.map.build_navigation()
	var host: Dictionary=fixture(game,"common-habitat_pod-143_1784")
	assert_false(host.is_empty())
	var pod: Node3D=host.node
	assert_gt(pod.global_basis.z.normalized().dot((-pod.global_position).normalized()),.99,"Native pod front faces the map centre")
	var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/architecture/habitat_pod/habitat_pod_rig.json"))
	var floor_y: float=metadata.architecture_dimensions.rooms[0].floor_m
	assert_gt(floor_y,.74,"Raised cabin has visible ground clearance")
	var cradle: Dictionary=fixture(game,"common-item_cradle-143_1785")
	assert_lt(pod.to_local(cradle.point).z,-.7,"Cradle is at the rear of the native pod")
	for side in ["L","R"]:
		var ammo: Dictionary=fixture(game,"common-rocket_launcher-2001_14-"+side)
		var local: Vector3=pod.to_local(ammo.point)
		assert_gt(local.z,.6,"Rocket ammo faces the map centre")
		assert_almost_eq(local.y,floor_y,.001,"Ammo rests on the raised native floor")
		var start: Vector3=pod.to_global(Vector3(0,floor_y+.015,1.10))
		var finish: Vector3=ammo.point+Vector3.UP*.015
		assert_true(game.map.traversal.supported(finish),"Ammo approach is supported by the native floor")
		assert_true(game.map.traversal.standing_clear(finish),"Robot fits at the ammo")
		assert_true(game.map.traversal.movement_clear(start,finish),"Cradle does not obstruct the path to ammo")
