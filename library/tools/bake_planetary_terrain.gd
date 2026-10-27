extends SceneTree
## Terrain3D authoring API produces real displaced vertices for Blender handoff.
func _initialize(): run.call_deferred()

func run():
	var arguments := OS.get_cmdline_user_args()
	assert(arguments.size()==2,"height field directory and map ID required")
	var directory := arguments[0]
	var map_id := arguments[1]
	var record: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(directory.path_join(map_id+".json")))
	var bytes := FileAccess.get_file_as_bytes(directory.path_join(map_id+".rf"))
	var image := Image.create_from_data(record.resolution,record.resolution,false,Image.FORMAT_RF,bytes)
	var results: Dictionary={"version":"1.0.2","parts":[]}
	var passes: Array=[false] if record.get("single_grid",false) else [true,false]
	for inner: bool in passes:
		var terrain := Terrain3D.new()
		root.add_child(terrain)
		terrain.data.change_region_size(64)
		terrain.material.world_background=Terrain3DMaterial.NONE
		terrain.collision.mode=Terrain3DCollision.DISABLED
		# Two extra samples retain real heights/normals at the final 64 m edge.
		var selected := image.get_region(Rect2i(192,192,130,130)) if inner else image
		terrain.data.import_images([selected,null,null],Vector3(-64 if inner else -256,0,-64 if inner else -256),0.0,1.0)
		var mesh := terrain.bake_mesh(0 if inner else int(record.get("outer_lod",2)))
		assert(mesh!=null)
		var arrays := mesh.surface_get_arrays(0)
		var vertices: Array=[]
		for vertex: Vector3 in arrays[Mesh.ARRAY_VERTEX]: vertices.append([vertex.x,vertex.y,vertex.z])
		results.parts.append({"inner":inner,"vertices":vertices,"indices":Array(arrays[Mesh.ARRAY_INDEX])})
		terrain.queue_free()
		await process_frame
	var output := FileAccess.open(directory.path_join(map_id+"_baked.json"),FileAccess.WRITE)
	output.store_string(JSON.stringify(results));output.close()
	print("TERRAIN3D_BAKED ",map_id," parts=",results.parts.size())
	quit()
