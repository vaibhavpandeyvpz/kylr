extends SceneTree
func _initialize():
	for path in ["res://assets/models/characters/tensor/tensor.fbx", "res://assets/models/characters/tensor/tensor_col.fbx", "res://assets/models/maps/skyfall/skyfall.glb", "res://assets/models/weapons/pistol/pistol_col.fbx"]:
		var scene = load(path).instantiate()
		root.add_child(scene)
		print("ASSET ", path)
		scene.print_tree_pretty()
		for a in scene.find_children("*", "AnimationPlayer", true, false):
			print("ANIM ", a.get_animation_list())
			for key in a.get_animation_list():
				var anim = a.get_animation(key)
				if anim.get_track_count(): print("TRACK ",anim.track_get_path(0))
		scene.free()
	quit()
