extends SceneTree

# Read the actual RR guide after path tracing, rather than an RGB preview.
class GuideCapture extends CompositorEffect:
	var lock := Mutex.new()
	var requested := false
	var pixels := PackedByteArray()
	var size := Vector2i.ZERO

	func _init() -> void:
		effect_callback_type = EFFECT_CALLBACK_TYPE_POST_OPAQUE

	func request() -> void:
		lock.lock()
		pixels.clear()
		requested = true
		lock.unlock()

	func snapshot() -> Dictionary:
		lock.lock()
		var result := {"pixels":pixels.duplicate(), "size":size}
		lock.unlock()
		return result

	func _render_callback(_type: int, data: RenderData) -> void:
		lock.lock()
		if not requested:
			lock.unlock()
			return
		var buffers: RenderSceneBuffersRD = data.get_render_scene_buffers()
		if buffers.has_texture("dlss_rr", "specular_hit_dist"):
			size = buffers.get_internal_size()
			pixels = RenderingServer.get_rendering_device().texture_get_data(buffers.get_texture("dlss_rr", "specular_hit_dist"), 0)
			requested = false
		lock.unlock()

var capture := GuideCapture.new()
var results: Array = []

func _initialize() -> void:
	call_deferred("run")

func box(scene: Node3D, y: float, material: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(12, 0.1, 12)
	node.mesh = mesh
	node.material_override = material
	node.position.y = y
	scene.add_child(node)
	return node

func measure(label: String, expected: float) -> void:
	await create_timer(2.0).timeout
	capture.request()
	var deadline := Time.get_ticks_msec() + 60000
	var snapshot := capture.snapshot()
	while snapshot.pixels.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
		snapshot = capture.snapshot()
	if snapshot.pixels.is_empty():
		push_error("Missing RR specular guide readback")
		quit(2)
		return
	var image := Image.create_from_data(snapshot.size.x, snapshot.size.y, false, Image.FORMAT_RH, snapshot.pixels)
	var distance := image.get_pixel(snapshot.size.x / 2, snapshot.size.y / 2).r
	var passed := absf(distance - expected) < 0.1
	results.append({"case":label, "distance_m":distance, "expected_m":expected, "passed":passed})
	print("SPECULAR_GUIDE ", JSON.stringify(results.back()))

func run() -> void:
	root.size = Vector2i(800,600)
	root.scaling_3d_scale = 0.5
	root.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS
	var scene := Node3D.new()
	root.add_child(scene)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color.BLACK
	environment.set("pathtracing_enabled", true)
	environment.set("pathtracing_denoiser", 1)
	environment.set("pathtracing_max_bounces", 3)
	var world := WorldEnvironment.new()
	world.environment = environment
	var compositor := Compositor.new()
	compositor.compositor_effects = [capture]
	world.compositor = compositor
	scene.add_child(world)
	var mirror := StandardMaterial3D.new()
	mirror.metallic = 1.0
	mirror.roughness = 0.0
	box(scene, -0.05, mirror)
	var opaque := StandardMaterial3D.new()
	box(scene, 7.05, opaque)
	var near := box(scene, 5.05, opaque)
	var camera := Camera3D.new()
	scene.add_child(camera)
	camera.position = Vector3(0,3,0)
	camera.look_at(Vector3.ZERO, Vector3.FORWARD)
	camera.current = true
	var deadline := Time.get_ticks_msec() + 60000
	while RenderingServer.viewport_get_render_info(root.get_viewport_rid(), RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_RT_TLAS_INSTANCES) < 3:
		if Time.get_ticks_msec() > deadline:
			push_error("Specular guide probe did not reach a populated RT scene")
			quit(2)
			return
		await create_timer(0.1).timeout
	await measure("nearest_opaque", 5.0)
	var shader := Shader.new()
	shader.code = "shader_type spatial; uniform bool hidden=true; void fragment(){ if(hidden) discard; ALBEDO=vec3(0.8); ROUGHNESS=1.0; }"
	var cutout := ShaderMaterial.new()
	cutout.shader = shader
	near.material_override = cutout
	await measure("procedural_discard", 7.0)
	cutout.set_shader_parameter("hidden", false)
	await measure("uniform_restores_nearest", 5.0)
	var passed := results.size() == 3 and results.all(func(row): return row.passed)
	var file := FileAccess.open("res://reports/specular-guide.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"passed":passed, "cases":results}))
	world.compositor = null
	quit(0 if passed else 1)
