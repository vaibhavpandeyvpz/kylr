extends SceneTree
const Preparation = preload("res://scripts/core/resource_preparation.gd")
const Observer = preload("res://scripts/debug/reconstruction_observer.gd")
var scene: Node3D
var folder: String

func _initialize() -> void: run.call_deferred()

func run() -> void:
	root.size = Vector2i(1280,720)
	var rt := OS.get_cmdline_user_args().has("--rt")
	folder = "res://reports/muzzle-3d/"+("rt" if rt else "raster")+"/"
	DirAccess.make_dir_recursive_absolute(folder)
	scene = load("res://tools/weapon_effects_harness.tscn").instantiate()
	root.add_child(scene)
	scene.automated = true
	for canvas in scene.find_children("*","CanvasLayer",true,false): canvas.visible = false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var prefs := Preferences.new("res://reports/muzzle_preview_unused.cfg")
	prefs.values.quality = 3
	for key in Preferences.QUALITY_PRESETS[3]: prefs.values[key] = Preferences.QUALITY_PRESETS[3][key]
	prefs.values.ray_tracing = rt
	prefs.apply_rendering(scene)
	var observer: CompositorEffect
	if rt:
		var world: WorldEnvironment = scene.find_children("*","WorldEnvironment",true,false)[0]
		world.compositor = Compositor.new()
		observer = Observer.new()
		world.compositor.compositor_effects = [observer]
		var ready: Dictionary = await Preparation.wait_for_rendering(self,root,true)
		assert(ready.ready)
	for frame in 90: await process_frame
	scene.set_process(false)
	scene.set_physics_process(false)
	for robot in scene.robots: robot.set_physics_process(false)
	for weapon in ["pistol","rifle","minigun","rocket_launcher"]:
		scene.select_weapon(scene.WEAPONS.find(weapon))
		scene.third_person = true
		scene.update_view_models()
		for frame in 8: await process_frame
		var socket: Node3D = Assets.socket(scene.local_robot.weapon_vfx.gun(),"Muzzle")
		if socket==null: socket = Assets.socket(scene.local_robot.weapon_vfx.gun(),"Muzzle1")
		assert(socket!=null)
		var forward := -socket.global_basis.z.normalized()
		var eye := socket.global_position+socket.global_basis.x.normalized()*0.9+Vector3.UP*0.25-forward*0.15
		scene.camera_rig.freeze_for_capture(Transform3D(Basis.looking_at(socket.global_position+forward*0.2-eye),eye))
		await shot(socket,weapon,0.3,weapon+"-side")
		eye = socket.global_position+forward*0.9+Vector3.UP*0.06
		scene.camera_rig.freeze_for_capture(Transform3D(Basis.looking_at(socket.global_position+forward*0.15-eye),eye))
		await shot(socket,weapon,0.3,weapon+"-front")
		scene.third_person = false
		if scene.first_person==null:
			var fp := FirstPersonRig.new()
			fp.robot = scene.local_robot
			fp.camera = scene.camera
			scene.first_person = fp
			scene.add_child(fp)
		scene.update_view_models()
		var aim := Basis(Vector3.UP,scene.local_robot.yaw)*Basis(Vector3.RIGHT,scene.local_robot.pitch)
		scene.camera_rig.freeze_for_capture(Transform3D(aim,scene.local_robot.eye()))
		for frame in 12: await process_frame
		socket = Assets.socket(scene.local_robot.weapon_vfx.gun(),"Muzzle")
		if socket==null: socket = Assets.socket(scene.local_robot.weapon_vfx.gun(),"Muzzle1")
		assert(socket!=null)
		await shot(socket,weapon,0.3,weapon+"-fpv")
		if weapon=="minigun":
			for index in 3: await shot(socket,weapon,0.3,"minigun-variant-"+str(index))
			for phase in [0.05,0.2,0.4,0.8]: await shot(socket,weapon,phase,"minigun-growth-"+str(roundi(phase*100)))
			clear_flashes()
			var first := make_flash(socket,weapon,0.125/0.18)
			var second := make_flash(socket,weapon,0.15)
			assert(first!=second and first.visible and second.visible)
			await save("minigun-overlap")
	clear_flashes()
	scene.select_weapon(scene.WEAPONS.find("minigun"))
	scene.third_person = false
	scene.update_view_models()
	for frame in 12: await process_frame
	scene.local_robot.set_physics_process(true)
	scene.local_robot.wants_fire = true
	var before: int = scene.local_robot.network_shots
	var overlap := 0
	DirAccess.make_dir_recursive_absolute(folder+"motion")
	for frame in 100:
		await physics_frame
		await process_frame
		var active := 0
		for burst in scene.effects.muzzle_pool:
			if burst.remaining>0 and burst.visible: active += 1
		overlap = maxi(overlap,active)
		if OS.get_cmdline_user_args().has("--motion"):
			await RenderingServer.frame_post_draw
			assert(root.get_texture().get_image().save_png(folder+"motion/%03d.png"%frame)==OK)
	scene.local_robot.wants_fire = false
	var shots: int = scene.local_robot.network_shots-before
	assert(shots>=8 and overlap>=2,"Real minigun firing must retain independent overlapping flashes")
	print("MUZZLE_FIRING shots=",shots," maximum_overlapping_flashes=",overlap)
	if observer:
		var stats: Dictionary = observer.call("stats")
		print("MUZZLE_NATIVE ",JSON.stringify(stats))
		assert(stats.frames>0 and stats.error.is_empty() and stats.adapter.get("evaluation_succeeded",false))
		observer.call("release")
	print("MUZZLE_PREVIEW_PASS rt=",rt)
	scene.queue_free()
	for frame in 4: await process_frame
	quit()

func clear_flashes() -> void:
	for burst in scene.effects.muzzle_pool:
		burst.remaining = 0
		burst.hide()
		burst.set_process(false)
		burst.effect.hide()
		burst.effect.set_process(false)

func make_flash(socket: Node3D, weapon: String, phase: float) -> PackBurst:
	scene.effects.muzzle(socket,weapon)
	var selected: PackBurst
	for burst in scene.effects.muzzle_pool:
		if burst.remaining>0 and burst.effect.age==0.0: selected = burst
	assert(selected!=null)
	selected.effect.age = selected.effect.duration*phase
	selected.effect._process(0)
	selected.effect.set_process(false)
	selected.set_process(false)
	return selected

func shot(socket: Node3D, weapon: String, phase: float, label: String) -> void:
	clear_flashes()
	make_flash(socket,weapon,phase)
	await save(label)

func save(label: String) -> void:
	for frame in 20: await process_frame
	await RenderingServer.frame_post_draw
	assert(root.get_texture().get_image().save_png(folder+label+".png")==OK)
