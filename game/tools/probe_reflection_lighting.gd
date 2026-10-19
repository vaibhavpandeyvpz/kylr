extends SceneTree
var views: Array[SubViewport]=[]
func _initialize(): run.call_deferred()
func run():
	var detail_mode := "--detail" in OS.get_cmdline_user_args()
	var empty_fog_mode := "--empty-fog" in OS.get_cmdline_user_args()
	DirAccess.make_dir_recursive_absolute("res://reports/reflections")
	for strength in [0.0,0.45]:
		var view:=SubViewport.new()
		view.size=Vector2i(800,600)
		view.own_world_3d=true
		if empty_fog_mode: view.msaa_3d=Viewport.MSAA_8X
		view.render_target_update_mode=SubViewport.UPDATE_ALWAYS
		root.add_child(view)
		views.append(view)
		var map:=ArenaMap.new()
		map.add_world()
		# Transfer the lighting without running the full map initializer.
		for node in map.get_children():
			map.remove_child(node)
			view.add_child(node)
		map.free()
		var env: WorldEnvironment=view.find_child("*",false,false) as WorldEnvironment
		for child in view.get_children():
			if child is WorldEnvironment: env=child
		var sky:=env.environment.sky.sky_material as ShaderMaterial
		sky.set_shader_parameter("reduced_motion",true)
		sky.set_shader_parameter("reflection_fill_energy",strength)
		if empty_fog_mode:
			sky.set_shader_parameter("reflection_fill_energy",0.45)
			env.environment.volumetric_fog_enabled = strength == 0.0
		if detail_mode:
			sky.set_shader_parameter("reflection_fill_energy",0.45)
			sky.set_shader_parameter("reflection_detail_strength",0.0 if strength==0 else 1.0)
		for index in 3:
			var ball:=MeshInstance3D.new()
			var sphere:=SphereMesh.new()
			sphere.radius=.45
			sphere.height=.9
			ball.mesh=sphere
			var material:=StandardMaterial3D.new()
			material.metallic=1.0
			material.albedo_color=Color(.65,.68,.72)
			material.roughness=[.05,.3,.65][index]
			ball.material_override=material
			view.add_child(ball)
			ball.position.x=(index-1)*1.15
		var camera:=Camera3D.new()
		view.add_child(camera)
		camera.position=Vector3(0,0,3.5)
		camera.current=true
	await create_timer(3).timeout
	await RenderingServer.frame_post_draw
	var before:=views[0].get_texture().get_image()
	var after:=views[1].get_texture().get_image()
	before.save_png("res://reports/reflections/before.png")
	after.save_png("res://reports/reflections/after.png")
	if empty_fog_mode:
		var maximum_error := 0.0
		var changed_pixels := 0
		for y in before.get_height():
			for x in before.get_width():
				var a := before.get_pixel(x,y)
				var b := after.get_pixel(x,y)
				var error := maxf(absf(a.r-b.r),maxf(absf(a.g-b.g),absf(a.b-b.b)))
				maximum_error = maxf(maximum_error,error)
				if error > 0.0: changed_pixels += 1
		print("EMPTY_FOG_CHECK max_error=",maximum_error," changed_pixels=",changed_pixels)
		quit(0 if maximum_error == 0.0 else 1)
		return
	var sky_error:=0.0
	for y in range(10,120,5):
		for x in range(10,790,5):
			var a:=before.get_pixel(x,y)
			var b:=after.get_pixel(x,y)
			sky_error=maxf(sky_error,maxf(absf(a.r-b.r),maxf(absf(a.g-b.g),absf(a.b-b.b))))
	var old_light:=0.0
	var new_light:=0.0
	for y in range(265,335):
		for x in range(365,435):
			old_light+=before.get_pixel(x,y).get_luminance()
			new_light+=after.get_pixel(x,y).get_luminance()
	print("REFLECTION_CHECK sky_max_error=",sky_error," metal_before=",old_light/4900," metal_after=",new_light/4900)
	quit(0 if sky_error<=1.0/255.0 and (detail_mode or new_light>old_light*1.5) else 1)
