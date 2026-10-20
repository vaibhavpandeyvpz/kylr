extends GutTest

func test_faceoff_upper_floor_weapons_use_freestanding_cradles():
	var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/faceoff/faceoff_rig.json"))
	var count := 0
	for marker in metadata.markers:
		if marker.role != "weapon" or marker.level != "upper" or marker.building not in ["bastion", "laboratory"]:
			continue
		count += 1
		assert_eq(marker.asset, "item_cradle", marker.building + " first-floor weapon fixture")
		var host: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/faceoff/faceoff_architecture_%s_rig.json" % marker.building))
		assert_almost_eq(float(marker.position_blender[2]), float(host.upper_floor_m.elevation), .0001, "Cradle base meets the authored floor")
		for hole in metadata.holes:
			assert_ne(hole.marker, marker.name, "Freestanding cradle does not leave a recessed holder pit")
	assert_eq(count, 2, "Both Faceoff first-floor weapons are covered")

func test_faceoff_native_corner_walls_block_robot_capsules_both_ways():
	for asset in ["laboratory", "bastion"]:
		var world := Node3D.new()
		add_child_autofree(world)
		var suffix: String = "_architecture_" + asset
		var prop := Assets.model("maps", "faceoff", suffix)
		world.add_child(prop)
		CollisionRig.install(prop, "maps", "faceoff", null, suffix + "_col")
		var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/faceoff/faceoff%s_rig.json" % suffix))
		var floor_height: float = metadata.architecture_dimensions.rooms[0].floor_m
		var body := CharacterBody3D.new()
		body.collision_layer = 2
		body.collision_mask = 1
		var capsule := CapsuleShape3D.new()
		capsule.radius = .32
		capsule.height = 1.72
		var shape := CollisionShape3D.new()
		shape.shape = capsule
		shape.position.y = .86
		body.add_child(shape)
		world.add_child(body)
		await get_tree().physics_frame
		await get_tree().physics_frame
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				var direction := Vector3(sx, 0, sz).normalized()
				for entering in [false, true]:
					for step_lift in [0.0, 0.25]:
						# A legal 25 cm step clears the foundation band. The wall
						# must still stop the capsule above it, not just its feet.
						var distance := 7.8 if entering else 5.0
						body.position = Vector3(sx * distance, floor_height + .01 + step_lift, sz * distance)
						await get_tree().physics_frame
						var hit := body.move_and_collide(direction * (-4.0 if entering else 4.0))
						assert_not_null(hit, "%s corner %s/%s entering=%s step=%s must block a full robot capsule" % [asset, sx, sz, entering, step_lift])

func test_faceoff_rack_gizmos_face_into_both_rooms():
	var map := Assets.model("maps","faceoff")
	add_child_autofree(map)
	var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/faceoff/faceoff_rig.json"))
	var count := 0
	for building in ["bastion","laboratory"]:
		var host: Node3D
		for marker in metadata.markers:
			if marker.get("source_asset","") == building:
				host = Assets.socket(map,"Gizmo_"+String(marker.name).replace("-","_"))
		assert_not_null(host)
		if host == null: continue
		for marker in metadata.markers:
			if marker.asset != "storage_rack" or marker.building != building: continue
			var rack := Assets.socket(map,"Gizmo_"+String(marker.name).replace("-","_"))
			assert_not_null(rack)
			if rack == null: continue
			count += 1
			var back := -rack.global_basis.z.normalized()
			assert_gt(back.dot(host.global_basis.x.normalized()),0.9999,building+" rack back faces its wall; shelves face the room")
	assert_eq(count,4,"Both racks in both buildings retain their exported wall orientation")
