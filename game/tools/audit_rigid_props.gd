extends SceneTree

func _initialize() -> void:
	for category in ["environments","gameplay","architecture"]:
		for asset in DirAccess.get_directories_at("res://assets/models/"+category):
			var path := "res://assets/models/%s/%s/%s.glb" % [category,asset,asset]
			if not ResourceLoader.exists(path): continue
			var instance := Assets.scene(path)
			for node: MeshInstance3D in instance.find_children("*","MeshInstance3D",true,false):
				if node.skin == null: continue
				var binds := {}
				for surface in node.mesh.get_surface_count():
					var arrays := node.mesh.surface_get_arrays(surface)
					var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
					var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
					for i in weights.size():
						if weights[i]>0.00001: binds[bones[i]]=true
				print("RIGID_AUDIT ",category,"/",asset," ",node.name," binds=",binds.size()," surfaces=",node.mesh.get_surface_count())
			instance.free()
	quit()
