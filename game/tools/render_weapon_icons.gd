extends SceneTree
func _initialize(): call_deferred("render_icons")

func render_icons():
	DirAccess.make_dir_recursive_absolute("res://assets/ui/weapons")
	var viewport := SubViewport.new()
	viewport.size=Vector2i(256,128)
	viewport.transparent_bg=true
	viewport.own_world_3d=true
	viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=0.52
	camera.position=Vector3(2,0.175,0)
	camera.look_at(Vector3(0,0.175,0))
	camera.current=true
	var material := StandardMaterial3D.new()
	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color=Color.WHITE
	for id in ContentRegistry.weapons():
		var gun := Assets.model("weapons",id)
		viewport.add_child(gun)
		var mount := Assets.socket(gun,"AmmoMount")
		if mount: mount.add_child(Assets.model("weapons",id,"_ammo"))
		for mesh in gun.find_children("*","MeshInstance3D",true,false): mesh.material_override=material
		await process_frame
		await RenderingServer.frame_post_draw
		viewport.get_texture().get_image().save_png("res://assets/ui/weapons/"+id+".png")
		gun.free()
	viewport.free()
	quit()
