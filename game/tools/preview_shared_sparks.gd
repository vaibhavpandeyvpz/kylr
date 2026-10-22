extends SceneTree
## Fixed-time views of the shared tracer renderer with native Jolt collisions.
const Preparation = preload("res://scripts/core/resource_preparation.gd")

func _initialize() -> void: run.call_deferred()

func run() -> void:
	root.size=Vector2i(1280,720)
	var rt := "--rt" in OS.get_cmdline_user_args()
	var mode := "rt" if rt else "raster"
	var folder := "res://reports/shared-sparks/"+mode+"/"
	DirAccess.make_dir_recursive_absolute(folder)
	var stage := Node3D.new()
	root.add_child(stage)
	var world := WorldEnvironment.new()
	world.environment=Environment.new()
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color("101925")
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color=Color.WHITE
	world.environment.ambient_light_energy=0.5
	world.environment.glow_enabled=true
	stage.add_child(world)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position=Vector3(2.3,2.0,3.2)
	camera.look_at(Vector3(0,0.55,0))
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=2.6
	camera.current=true
	var floor := StaticBody3D.new()
	stage.add_child(floor)
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size=Vector3(6,0.1,6)
	mesh.mesh=box
	mesh.material_override=Assets.material(Color("26303a"))
	floor.add_child(mesh)
	floor.position.y=-0.05
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size=box.size
	collision.shape=shape
	floor.add_child(collision)
	var light := DirectionalLight3D.new()
	light.rotation_degrees=Vector3(-45,-30,0)
	stage.add_child(light)
	var preferences := Preferences.new("res://reports/shared-sparks-unused.cfg")
	preferences.values=Preferences.DEFAULTS.duplicate(true)
	preferences.values.merge(Preferences.QUALITY_PRESETS[3],true)
	preferences.values.quality=3
	preferences.values.ray_tracing=rt
	preferences.values.rt_upscaling=false
	preferences.apply_rendering(stage)
	await physics_frame
	var spark := ImpactSparks.new()
	stage.add_child(spark)
	var report: Array=[]
	for profile in ImpactSparks.COUNTS:
		seed(1347)
		spark.fire(Vector3(0,0.55,0),Vector3.UP,false,8.0,profile)
		spark.set_physics_process(false)
		var previous := 0.0
		for age in [0.01,0.025,0.2,0.49,0.5125,0.525]:
			spark._physics_process(age-previous)
			previous=age
			for index in spark.renderer.multimesh.visible_instance_count:
				var actual := spark.renderer.multimesh.get_instance_transform(index)
				assert(actual.basis.y.length()<=0.05001)
				assert(is_equal_approx(actual.basis.x.length(),1.0))
				assert(is_equal_approx(actual.basis.z.length(),1.0))
			var ready: Dictionary=await Preparation.wait_for_rendering(self,root,rt)
			assert(ready.ready)
			for frame in 30: await process_frame
			await RenderingServer.frame_post_draw
			var image := root.get_texture().get_image()
			var path := folder+String(profile)+"-"+str(roundi(age*10000))+".png"
			assert(image.save_png(path)==OK)
			report.append({"profile":profile,"age":age,"active":spark.renderer.multimesh.visible_instance_count,"image":path,"ready":ready})
		assert(spark.renderer.multimesh.visible_instance_count==0)
	FileAccess.open(folder+"manifest.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("SHARED_SPARKS_CAPTURE_DONE ",mode," cases=",report.size())
	stage.queue_free()
	await process_frame
	quit()
