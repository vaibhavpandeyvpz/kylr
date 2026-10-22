extends SceneTree
const Preparation = preload("res://scripts/core/resource_preparation.gd")
func _initialize() -> void: run.call_deferred()

func run() -> void:
	root.size = Vector2i(1280,720)
	var mode := "raster"
	var stage := Node3D.new()
	root.add_child(stage)
	ArenaLighting.install(stage,true)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(0,0.3,1.0)
	camera.look_at(Vector3(0,0.3,0))
	camera.current = true
	var wall := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(1.0,0.7,0.05)
	wall.mesh = box
	wall.position.y = 0.3
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color(0.6,0.6,0.6)
	wall.material_override = material
	stage.add_child(wall)
	var effects := ArenaEffects.new()
	stage.add_child(effects)
	var prefs := Preferences.new("user://surface_marks_unused.cfg")
	prefs.values.quality = 2
	for key in Preferences.QUALITY_PRESETS[2]: prefs.values[key] = Preferences.QUALITY_PRESETS[2][key]
	prefs.apply_rendering(stage)
	var points: Array[Vector3] = []
	for index in 6:
		var point := Vector3((index%3-1)*0.23,0.17+floori(index/3.0)*0.26,0.025)
		points.append(point)
		effects.impact(point,Vector3.BACK,false,wall)
		var mark: MeshInstance3D = effects.decals[-1]
		mark.set_process(false)
		mark.set_instance_shader_parameter("atlas_cell",[0,7,18,31,46,63][index])
	for frame in 180: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	var passed := true
	for point in points:
		var color := image.get_pixelv(Vector2i(camera.unproject_position(point)))
		passed = passed and maxf(color.r,maxf(color.g,color.b)) < 0.3
	image.save_png("res://reports/surface-marks-"+mode+".png")
	effects.decals[0].set_instance_shader_parameter("progress",1.0)
	for frame in 12: await process_frame
	await RenderingServer.frame_post_draw
	var faded := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(points[0])))
	passed = passed and minf(faded.r,minf(faded.g,faded.b)) > 0.5
	var native := {}
	print("SURFACE_MARKS mode=",mode," variants=6 fade=1 passed=",passed," native=",JSON.stringify(native))
	stage.queue_free()
	for frame in 6: await process_frame
	quit(0 if passed else 1)
