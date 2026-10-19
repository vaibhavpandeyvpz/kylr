extends SceneTree
func _initialize():
	call_deferred("audit")
func audit():
	for suffix in ["","_col"]:
		var scene=load("res://assets/models/maps/faceoff/faceoff"+suffix+".glb").instantiate()
		root.add_child(scene)
		print("MAP ",suffix)
		var skeleton=Assets.find(scene,"Skeleton3D")
		if skeleton==null:
			scene.print_tree_pretty()
			scene.free()
			continue
		print("Skeleton transform ",skeleton.global_transform)
		for i in skeleton.get_bone_count():
			print("bone ",skeleton.get_bone_name(i)," rest ",skeleton.get_bone_global_rest(i).origin," pose ",skeleton.get_bone_global_pose(i).origin)
		for mesh in scene.find_children("*","MeshInstance3D",true,false):
			print("mesh ",mesh.name," transform ",mesh.global_transform," bounds ",mesh.mesh.get_aabb())
			if mesh.skin:
				print("skin bind0 name ",mesh.skin.get_bind_name(0)," bone ",mesh.skin.get_bind_bone(0)," pose ",mesh.skin.get_bind_pose(0))
		var player=Assets.find(scene,"AnimationPlayer")
		if player:
			for key in player.get_animation_list():
				var anim=player.get_animation(key)
				print("CLIP ",key," length ",anim.length)
				for t in anim.get_track_count():
					if anim.track_get_type(t)==Animation.TYPE_POSITION_3D:
						print(anim.track_get_path(t)," FIRST ",anim.track_get_key_value(t,0)," LAST ",anim.track_get_key_value(t,anim.track_get_key_count(t)-1))
		scene.free()
	quit()
