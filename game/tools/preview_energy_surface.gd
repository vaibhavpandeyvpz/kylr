extends SceneTree
## Native posed robot and repair barrier; no AI or damage simulation overrides.
const Preparation=preload("res://scripts/core/resource_preparation.gd")
var scene
var directory: String

func _initialize():run.call_deferred()

func frames(count: int):
	for frame in count:
		scene.target.animator.advance(1.0/60.0)
		await process_frame

func capture(label: String):
	await frames(45)
	await RenderingServer.frame_post_draw
	assert(root.get_texture().get_image().save_png(directory.path_join(label+".png"))==OK)
	print("ENERGY_SURFACE_CAPTURE ",label)

func run():
	root.size=Vector2i(1280,960)
	Engine.max_fps=60
	AudioServer.set_bus_mute(0,true)
	directory="res://reports/energy-surface/raster"
	DirAccess.make_dir_recursive_absolute(directory)
	scene=load("res://tools/weapon_effects_harness.gd").new()
	root.add_child(scene)
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
	scene.set_process(false);scene.set_physics_process(false);scene.set_process_unhandled_input(false)
	for node in scene.get_children():
		if node is CanvasLayer:node.hide()
	scene.local_robot.hide();scene.local_robot.set_physics_process(false);scene.local_robot.set_process(false)
	scene.target.set_process(false);scene.target.set_physics_process(false)
	scene.target.position=Vector3.ZERO;scene.target.body.rotation.y=0
	scene.target.protection=0;scene.target.spawn_remaining=0;scene.target.sh=100
	scene.target.pose("idle");scene.target.set_weapon_pose_visible(false)
	var camera:=Camera3D.new()
	scene.add_child(camera);camera.position=Vector3(2.0,1.25,3.1)
	camera.look_at(Vector3(0,.95,0));camera.fov=40;camera.make_current()
	scene.camera_rig.host.set_process(false)
	var prefs:=Preferences.new("user://energy-surface-preview.cfg")
	prefs.values=Preferences.DEFAULTS.duplicate(true)
	prefs.values.merge(Preferences.QUALITY_PRESETS[2],true)
	prefs.apply_rendering(scene)
	root.scaling_3d_scale=1.0
	var ready:=await Preparation.wait_for_rendering(self,root)
	assert(ready.ready)
	EnergySurface.update(scene.target)
	await capture("shield-primary")
	await capture("shield-primary-motion")
	scene.target.sh=0;scene.target.hit_flash=.18
	for weapon in ["pistol","lightning_gun","pulse_gun","bio_rifle","rocket_launcher","flak_cannon","emp_gun"]:
		scene.target.last_hit_weapon=weapon
		EnergySurface.update(scene.target)
		await capture("hit-"+weapon)
	EnergySurface.clear(scene.target)
	var station:=Assets.model("gameplay","repair_station")
	scene.add_child(station)
	for mesh in station.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			var source:=mesh.get_active_material(surface) as StandardMaterial3D
			if source!=null and Assets.material_role(source.resource_name)=="M_Shield":
				mesh.material_override=RepairBarrier.material()
	camera.position=Vector3(2.5,1.7,4.0)
	camera.look_at(Vector3(0,1.2,0))
	await capture("repair-shield-green")
	scene.free()
	quit()
