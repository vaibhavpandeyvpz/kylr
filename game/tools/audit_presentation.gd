extends SceneTree
func _initialize(): call_deferred("audit")
func audit():
	for entry in [["weapons","pistol"],["environments","jumbotron"]]:
		var scene := Assets.model(entry[0],entry[1])
		root.add_child(scene)
		await process_frame
		await process_frame
		for mesh in scene.find_children("*","MeshInstance3D",true,false):
			for i in mesh.mesh.get_surface_count():
				var mat = mesh.get_active_material(i)
				if mat is StandardMaterial3D: print(entry[1]," ",mesh.name," ",mat.resource_name," color ",mat.albedo_color," emission ",mat.emission_energy_multiplier," enabled ",mat.emission_enabled)
		scene.free()
	quit()
