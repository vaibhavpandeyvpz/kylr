extends GutTest

func check_mount(map_id: String,height: float) -> void:
	var root: Node3D=Assets.model("maps",map_id)
	add_child_autofree(root)
	var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/%s/%s_rig.json"%[map_id,map_id]))
	var markers: Array=metadata.markers.filter(func(marker): return marker.role=="jumbotron")
	assert_eq(markers.size(),1)
	var marker: Dictionary=markers[0]
	assert_almost_eq(float(marker.position_godot[1]),height,0.001)
	var socket: Node3D=Assets.socket(root,"Gizmo_"+String(marker.name).replace("-","_"))
	assert_not_null(socket)
	if socket:
		assert_almost_eq(socket.global_position.y,height,0.001,"Delivered GLB placement must match source metadata")

func test_skyfall_five_metres_above_rooftop() -> void:
	check_mount("skyfall",45.0)

func test_faceoff_ten_metres_above_ground() -> void:
	check_mount("faceoff",10.0)
