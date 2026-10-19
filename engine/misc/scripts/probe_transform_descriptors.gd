class_name TransformDescriptorProbe
extends SceneTree
## Exercise repeated transform bindings and buffer replacement between frames.
## Deterministic raster captures are correctness evidence, not FPS measurements.

var output := ""

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output=argument.trim_prefix("--output=")
	if output.is_empty() or DirAccess.dir_exists_absolute(output):
		push_error("Pass a fresh absolute --output directory")
		quit(1)
		return
	run.call_deferred()

func run() -> void:
	if DirAccess.make_dir_recursive_absolute(output)!=OK:
		quit(1)
		return
	root.size=Vector2i(640,480)
	root.use_hdr_2d=true
	RenderingServer.positional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_HARD)
	RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_HARD)
	var stage := Node3D.new()
	root.add_child(stage)
	var world := WorldEnvironment.new()
	world.environment=Environment.new()
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color(0.01,0.02,0.03)
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color=Color.WHITE
	world.environment.ambient_light_energy=0.25
	world.environment.reflected_light_source=Environment.REFLECTION_SOURCE_DISABLED
	stage.add_child(world)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position=Vector3(6,8,10)
	camera.look_at(Vector3.ZERO)
	camera.current=true
	var light := DirectionalLight3D.new()
	light.rotation_degrees=Vector3(-60,-25,0)
	light.shadow_enabled=true
	stage.add_child(light)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(12,12)
	floor_mesh.mesh=plane
	stage.add_child(floor_mesh)
	var skeleton := Skeleton3D.new()
	stage.add_child(skeleton)
	skeleton.add_bone("Root")
	var skin := Skin.new()
	skin.add_bind(0,Transform3D.IDENTITY)
	var mesh := ArrayMesh.new()
	var box := BoxMesh.new()
	box.size=Vector3(0.55,0.8,0.55)
	for surface in 8:
		var arrays := box.get_mesh_arrays()
		var vertices: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
		for index in vertices.size(): vertices[index]+=Vector3((surface%4)*0.7-3.3,0.5,(surface/4)*0.8-0.8)
		arrays[Mesh.ARRAY_VERTEX]=vertices
		var bones := PackedInt32Array()
		var weights := PackedFloat32Array()
		bones.resize(vertices.size()*4)
		weights.resize(vertices.size()*4)
		for index in vertices.size(): weights[index*4]=1.0
		arrays[Mesh.ARRAY_BONES]=bones
		arrays[Mesh.ARRAY_WEIGHTS]=weights
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
		var material := StandardMaterial3D.new()
		material.albedo_color=Color(0.8,0.15,0.05) if surface%2==0 else Color(0.05,0.2,0.8,0.65)
		if surface%2: material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
		mesh.surface_set_material(surface,material)
	for index in 2:
		var instance := MeshInstance3D.new()
		instance.mesh=mesh
		instance.skin=skin
		instance.skeleton=NodePath("..")
		instance.position.z=index*1.8
		instance.custom_aabb=AABB(Vector3(-5,-1,-2),Vector3(10,6,6))
		skeleton.add_child(instance)
	var multimesh := MultiMesh.new()
	multimesh.transform_format=MultiMesh.TRANSFORM_3D
	multimesh.mesh=box
	var multi_instance := MultiMeshInstance3D.new()
	multi_instance.multimesh=multimesh
	stage.add_child(multi_instance)
	var particles := GPUParticles3D.new()
	particles.lifetime=1.0
	particles.visibility_aabb=AABB(Vector3(-6,-1,-6),Vector3(12,6,12))
	particles.draw_pass_1=box
	var process := ShaderMaterial.new()
	process.shader=Shader.new()
	process.shader.code="shader_type particles; render_mode disable_velocity; void start(){TRANSFORM=mat4(1.0); TRANSFORM[3].xyz=vec3(float(INDEX%8u)*0.45-1.5,0.5,-3.0-float(INDEX/8u)*0.5); VELOCITY=vec3(0.0);} void process(){}"
	particles.process_material=process
	stage.add_child(particles)
	var captures: Array=[]
	var counts := [4,64,2,32]
	for phase in counts.size():
		var count: int=counts[phase]
		skeleton.clear_bones()
		for index in count: skeleton.add_bone("Root" if index==0 else "Bone%d"%index)
		skeleton.set_bone_pose_position(0,Vector3(0,phase*0.3,0))
		# clear_bones also removes registered SkinReferences. Rebind the skin so
		# each phase exercises a live replacement rather than detached geometry.
		for instance: MeshInstance3D in skeleton.get_children():
			instance.skin=null
			instance.skin=skin
		skeleton.force_update_all_bone_transforms()
		multimesh.instance_count=count
		for index in count:
			multimesh.set_instance_transform(index,Transform3D(Basis.IDENTITY,Vector3(1+(index%8)*0.5,0.4,(index/8)*0.5-1.5)))
		particles.amount=count
		particles.restart()
		for frame in 120: await process_frame
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		var red_pixels := 0
		var blue_pixels := 0
		for y in image.get_height():
			for x in image.get_width():
				var pixel := image.get_pixel(x,y)
				if pixel.r>0.08 and pixel.r>pixel.g*2.0 and pixel.r>pixel.b*2.0: red_pixels+=1
				if pixel.b>0.08 and pixel.b>pixel.g*2.0 and pixel.b>pixel.r*2.0: blue_pixels+=1
		if red_pixels<40 or blue_pixels<40:
			image.save_png(output.path_join("missing_skin_phase%d.png"%phase))
			push_error("Skinned geometry was not visibly exercised")
			quit(2)
			return
		image.save_png(output.path_join("phase%d.png"%phase))
		image.convert(Image.FORMAT_RGBAF)
		FileAccess.open(output.path_join("phase%d.rgba32f"%phase),FileAccess.WRITE).store_buffer(image.get_data())
		captures.append({"phase":phase,"count":count,"red_pixels":red_pixels,"blue_pixels":blue_pixels,"width":image.get_width(),"height":image.get_height(),"bytes":image.get_data().size()})
	FileAccess.open(output.path_join("captures.json"),FileAccess.WRITE).store_string(JSON.stringify({"captures":captures,"performance_acceptance":false},"\t"))
	stage.queue_free()
	await process_frame
	print("TRANSFORM_DESCRIPTORS_CAPTURED phases=",captures.size())
	quit()
