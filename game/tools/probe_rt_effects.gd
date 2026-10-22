extends SceneTree
const ResourcePreparation=preload("res://scripts/core/resource_preparation.gd")
const ReconstructionObserver=preload("res://scripts/debug/reconstruction_observer.gd")

var mode := "raster"
var rt := false
var rr_preset := "?"
var quality_preset := 3
var samples: Array[Dictionary] = []
var camera: Camera3D
var stage: Node3D
var effects: ArenaEffects
var report_directory := "res://reports"
var reconstruction_observer: CompositorEffect
var last_reconstruction_frames := 0
var smallest_step := INF
var largest_step := 0.0

func _process(delta: float) -> bool:
	if delta>0:
		smallest_step=minf(smallest_step,delta)
		largest_step=maxf(largest_step,delta)
	return false

func seed_particle(node: Node) -> void:
	if node is GPUParticles3D:
		# A stable authored emitter name gives both renderers the same random
		# sequence. This changes only the diagnostic fixture, never game effects.
		node.use_fixed_seed=true
		node.seed=int(String(node.name).hash())

func observe_reconstruction(parent: Node) -> bool:
	if not rt:return true
	var worlds:=parent.find_children("*","WorldEnvironment",true,false)
	if worlds.size()!=1:
		push_error("Effects fixture requires one observed environment");quit(3);return false
	var world:WorldEnvironment=worlds[0]
	if world.compositor==null:world.compositor=Compositor.new()
	reconstruction_observer=ReconstructionObserver.new()
	world.compositor.compositor_effects=world.compositor.compositor_effects+[reconstruction_observer]
	last_reconstruction_frames=0
	return true

class WeldingWorld extends Node:
	var phase := "Active"
	var map := {"shutting_down":false}
	var camera: Camera3D
	var reduced_motion := false
	var effects: ArenaEffects

func _initialize():
	node_added.connect(seed_particle)
	call_deferred("run")

func frames(count: int):
	for frame in range(count): await process_frame

func shader_paths(node: Node, result: Dictionary):
	for material in PackVfx.materials(node):
		if material.shader: result[material.shader.resource_path]=true
	for child in node.get_children():
		if child is GPUParticles3D and child.process_material is ShaderMaterial:
			result[child.process_material.shader.resource_path]=true
		shader_paths(child,result)

func unshaded_flatness(image: Image, group: Node) -> Array:
	var result:=[]
	for index in 2:
		var mesh:MeshInstance3D=group.get_child(index)
		var center:=camera.unproject_position(mesh.global_position)
		var radius:=center.distance_to(camera.unproject_position(mesh.global_position+camera.global_basis.x*.25))*.65
		var values:Array[float]=[]
		for y in range(ceili(center.y-radius),floori(center.y+radius)+1):
			for x in range(ceili(center.x-radius),floori(center.x+radius)+1):
				if Vector2(x,y).distance_to(center)>radius:continue
				values.append(image.get_pixel(x,y)[0 if index==0 else 2])
		values.sort()
		var low:=values[floori((values.size()-1)*.01)]
		var high:=values[floori((values.size()-1)*.99)]
		result.append({"p01":low,"p99":high,"spread":high-low,"samples":values.size(),"passed":low>.15 and high-low<.03})
	return result

func capture(id: String, node: Node, details: Dictionary = {}):
	await frames(24)
	await RenderingServer.frame_post_draw
	if absf(smallest_step-1.0/60.0)>0.000001 or absf(largest_step-1.0/60.0)>0.000001:
		push_error("Effects captures require --fixed-fps 60; validation overhead must not age particles differently");quit(3);return
	details["simulation_step_seconds"]={"min":smallest_step,"max":largest_step}
	details["fixed_particle_seeds"]=true
	details["rr_preset_requested"]=rr_preset
	if rt:
		var expected:=1
		var worlds:=0
		for world in root.find_children("*","WorldEnvironment",true,false):
			if world.environment==null:continue
			if not world.environment.get("pathtracing_enabled") or world.environment.get("pathtracing_denoiser")!=expected:
				push_error("Wrong RT backend in effects case: "+id);quit(3);return
			worlds+=1
		var expected_scaling:=Viewport.SCALING_3D_MODE_DLSS
		if worlds==0 or root.scaling_3d_mode!=expected_scaling or not is_equal_approx(root.scaling_3d_scale,.5):
			push_error("Wrong effects viewport configuration: "+id);quit(3);return
		var expected_aa:=Viewport.SCREEN_SPACE_AA_DISABLED
		if root.screen_space_aa!=expected_aa or root.use_taa or root.msaa_3d!=Viewport.MSAA_DISABLED:
			push_error("Wrong effects antialiasing: "+id);quit(3);return
		details.merge({"denoiser":expected,"environments":worlds,"internal_scale":root.scaling_3d_scale,"scaling_mode":root.scaling_3d_mode,"screen_space_aa":root.screen_space_aa,"taa":root.use_taa,"msaa":root.msaa_3d})
		var observation:Dictionary=reconstruction_observer.stats()
		var native:Dictionary=observation.get("adapter",{})
		var evaluated:=int(native.get("frames",0))
		if not observation.get("error","").is_empty() or native.get("backend")!="DLSS" or not native.get("viewport_renderer",false) or not native.get("evaluation_succeeded",false) or evaluated<=last_reconstruction_frames or native.get("size")!=[640,360] or native.get("output_size")!=[1280,720]:
			push_error("Missing successful native RR evaluations for effect "+id+": "+JSON.stringify(observation));quit(3);return
		last_reconstruction_frames=evaluated
		details["native_reconstruction"]=observation
	var image := root.get_texture().get_image()
	if image.is_empty() or image.get_size()!=Vector2i(1280,720):
		push_error("Invalid capture for " + id)
		quit(3)
		return
	var paths := {}
	shader_paths(node,paths)
	details.merge({"case":id,"ray_tracing":rt,"quality_preset":quality_preset,"graphics_device":RenderingServer.get_video_adapter_name(),"raster_msaa":root.msaa_3d,"shaders":paths.keys(),"width":image.get_width(),"height":image.get_height()})
	samples.append(details)
	if image.save_png(report_directory.path_join("effects-%s-%s.png" % [mode,id]))!=OK:
		push_error("Could not save effect capture: "+id);quit(3);return
	if id=="instance-uniforms-unshaded" and "--unshaded-settling" in OS.get_cmdline_user_args():
		# Keep the same surface, camera and scene history. Extra diagnostic
		# frames distinguish a persistent error from insufficient initial settling.
		var observations:=[{"frames":24,"colors":unshaded_flatness(image,node)}]
		var settled_frames:=24
		for extra in [96,240]:
			await frames(extra)
			await RenderingServer.frame_post_draw
			var settled:=root.get_texture().get_image()
			settled_frames+=extra
			observations.append({"frames":settled_frames,"colors":unshaded_flatness(settled,node)})
			if settled.save_png(report_directory.path_join("unshaded-%s-frame-%d.png"%[mode,settled_frames]))!=OK:
				push_error("Could not save unshaded diagnostic");quit(3);return
		FileAccess.open(report_directory.path_join("unshaded-settling.json"),FileAccess.WRITE).store_string(JSON.stringify({"observations":observations,"visual_quality_acceptance":false},"\t"))
	print("EFFECTS_CASE ",mode," ",id)

func set_camera(focus: Vector3, distance: float):
	camera.position=focus+Vector3(0,distance*0.22,distance)
	camera.look_at(focus)

func freeze(node: Node):
	node.set_process(false)
	if node is ImpactSparks:
		if node.elapsed<=0.0: node._physics_process(0.08)
		node.set_physics_process(false)
	if node is GPUParticles3D: node.speed_scale=0.0
	if node is AnimationPlayer: node.pause()
	for child in node.get_children(): freeze(child)

func remove_case(node: Node):
	node.queue_free()
	await frames(3)

func run():
	seed(120)
	Engine.physics_ticks_per_second=60
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--report-dir="):report_directory=argument.trim_prefix("--report-dir=")
		if argument.begins_with("--rr-preset="):rr_preset=argument.trim_prefix("--rr-preset=")
		if argument.begins_with("--quality-preset="):quality_preset=int(argument.trim_prefix("--quality-preset="))
	if quality_preset < 0 or quality_preset > 3:push_error("Invalid quality preset");quit(2);return
	if DirAccess.make_dir_recursive_absolute(report_directory)!=OK:quit(2);return
	ProjectSettings.set_setting("rendering/pathtracing/use_simple_shadows","--query-shadows" in OS.get_cmdline_user_args())
	rt="--rt" in OS.get_cmdline_user_args()
	mode="rt" if rt else "raster"
	if rr_preset not in ["?","D","E"]:push_error("Invalid RR preset diagnostic");quit(2);return
	if rt:
		if not Engine.has_singleton("Streamline"):push_error("RR preset diagnostic requires Streamline");quit(2);return
		if rr_preset!="?":
			Engine.get_singleton("Streamline").set_parameter(ClassDB.class_get_integer_constant("Streamline","STREAMLINE_PARAM_DLSS_RR_PRESET"),rr_preset)
		print("EFFECTS_RR_PRESET ",rr_preset)
	var requested_denoiser:=Preferences.DENOISER_DLSS
	if rt and not Preferences.ray_tracing_unavailable_reason(requested_denoiser).is_empty():
		push_error(Preferences.ray_tracing_unavailable_reason(requested_denoiser))
		quit(2)
		return
	root.size=Vector2i(1280,720)
	var prefs := Preferences.new("user://effects_probe_unused.cfg")
	prefs.values.quality=quality_preset
	for key in Preferences.QUALITY_PRESETS[quality_preset]:prefs.values[key]=Preferences.QUALITY_PRESETS[quality_preset][key]
	prefs.values.rt_denoiser=Preferences.DENOISER_DLSS
	prefs.values.ray_tracing=rt
	var scene = load("res://tools/weapon_effects_harness.tscn").instantiate()
	scene.projectile_speed_mps=15.0
	root.add_child(scene)
	scene.automated=true
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
	prefs.apply_rendering(scene)
	if not observe_reconstruction(scene):return
	if rt:
		var readiness:Dictionary=await ResourcePreparation.wait_for_rendering(self,root,true)
		if not readiness.ready:push_error(str(readiness));quit(6);return
	await frames(120)
	var core_only := "--core-only" in OS.get_cmdline_user_args()
	var gallery_only := "--gallery-only" in OS.get_cmdline_user_args() or core_only
	var flame_only := "--flame-only" in OS.get_cmdline_user_args()
	for index in ([] if gallery_only else range(scene.WEAPONS.size())):
		if flame_only and scene.WEAPONS[index] != "flamethrower": continue
		scene.reset_positions()
		scene.select_weapon(index)
		scene.local_robot.wants_secondary=false
		scene.local_robot.wants_fire=true
		var shots_before: int=scene.local_robot.network_shots
		for frame in range(120): await physics_frame
		if (scene.WEAPONS[index] in ["lightning_gun","flamethrower"] and scene.hits==0) or (not scene.WEAPONS[index] in ["lightning_gun","flamethrower"] and scene.local_robot.network_shots<=shots_before):
			push_error("Weapon did not fire: " + scene.WEAPONS[index])
			quit(5)
			return
		await capture("primary-"+scene.WEAPONS[index],scene,{"hits":scene.hits,"shots":scene.local_robot.network_shots})
		if flame_only:
			scene.set_process(false)
			var eye := Vector3(7,2,3)
			var inspection_pose := Transform3D(Basis.looking_at(Vector3(7,1.2,0)-eye),eye)
			scene.camera_rig.freeze_for_capture(inspection_pose)
			await frames(120)
			if root.get_camera_3d().global_position.distance_to(eye)>0.05:
				push_error("Flame inspection camera was overridden");quit(3);return
			await capture("flame-closeup",scene,{"hits":scene.hits,"shots":scene.local_robot.network_shots,"inspection_eye":[eye.x,eye.y,eye.z]})
			# Inspect the actual displayed FPV weapon socket, not just a side-on
			# gallery beam. End-on billboards can look correct from the side.
			scene.third_person=false
			var fp := FirstPersonRig.new()
			fp.robot=scene.local_robot
			fp.camera=scene.camera
			scene.first_person=fp
			scene.add_child(fp)
			scene.update_view_models()
			for view in ["long","near","up"]:
				scene.target.position=Vector3(0,0.01,0) if view=="long" else Vector3(8,0.01,0) if view=="near" else Vector3(8,6,0)
				for tick in 8: await physics_frame
				var aim_basis := Basis(Vector3.UP,scene.local_robot.yaw)*Basis(Vector3.RIGHT,scene.local_robot.pitch)
				scene.camera_rig.freeze_for_capture(Transform3D(aim_basis,scene.local_robot.eye()))
				await frames(120)
				if not scene.uses_first_person() or fp.gun!=scene.local_robot.weapon_vfx.gun():
					push_error("Flame capture did not use the displayed FPV weapon");quit(3);return
				await capture("flame-fpv-"+view,scene,{"hits":scene.hits,"displayed_muzzle":true})
		scene.local_robot.wants_fire=false
		scene.local_robot.weapon_vfx.stop_stream()
	if flame_only:
		var flame_report := FileAccess.open(report_directory.path_join("effects-%s.json" % mode),FileAccess.WRITE)
		flame_report.store_string(JSON.stringify(samples,"\t"))
		flame_report.close()
		if reconstruction_observer: reconstruction_observer.release()
		scene.queue_free()
		await frames(6)
		print("EFFECTS_CAPTURE_DONE ",mode," cases=",samples.size())
		quit()
		return
	for index in ([] if gallery_only else [3,6]):
		scene.reset_positions()
		scene.select_weapon(index)
		scene.local_robot.wants_secondary=true
		for frame in range(80): await physics_frame
		await capture("secondary-"+scene.WEAPONS[index],scene,{"shots":scene.local_robot.network_shots})
		scene.local_robot.wants_secondary=false
	scene.local_robot.wants_fire=false
	scene.local_robot.weapon_vfx.stop_stream()
	scene.effects.hide()
	scene.set_process(false)
	scene.local_robot.set_physics_process(false)
	scene.target.set_physics_process(false)
	scene.target.set_process(false)
	var target_pose := Transform3D(Basis.looking_at(Vector3(0,-0.1,-1)),scene.target.position+Vector3(0,1,2.4))
	scene.camera_rig.set_gameplay("tpv",target_pose,45,true)
	scene.shield_target=true
	scene.target.sh=100
	scene.target.hit_flash=.14
	EnergySurface.update(scene.target)
	# Wait for the shared energy-surface material in the RTX renderer.
	await frames(180)
	await capture("shield-hit",scene.target)
	# Exercise accepted damage after clearing Shield Health.
	# The target's process callbacks are disabled above, so the flash remains
	# at a fixed strength through asynchronous shader warmup and capture.
	scene.shield_target=false
	EnergySurface.clear(scene.target)
	scene.target.sh=0
	scene.target.protection=0
	var armor_hit:bool=scene.target.hit(1.0,null,"effects_probe")
	if not armor_hit or not scene.target.surface_active:
		push_error("Armor hit did not install its overlay");quit(10);return
	for armor_mesh in scene.target.surface_meshes:
		if armor_mesh.material_overlay!=scene.target.surface_material:
			push_error("Armor hit overlay missing on a body surface");quit(10);return
	scene.target.surface_material.set_shader_parameter("hit_strength",.5)
	await frames(180)
	await capture("armor-hit",scene.target,{"hit_accepted":armor_hit,"armor_overlay_meshes":scene.target.surface_meshes.size(),"armor_strength":.5,"armor_shader":scene.target.surface_material.shader.resource_path})
	if reconstruction_observer:reconstruction_observer.release()
	scene.queue_free()
	await frames(6)
	stage=Node3D.new()
	root.add_child(stage)
	ArenaLighting.install(stage,true)
	camera=Camera3D.new()
	stage.add_child(camera)
	camera.current=true
	camera.fov=50.0
	var floor := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(30,30)
	floor.mesh=plane
	floor.material_override=Assets.material(Color("454d54"))
	stage.add_child(floor)
	effects=ArenaEffects.new()
	stage.add_child(effects)
	prefs.apply_rendering(stage)
	if not observe_reconstruction(stage):return
	# A core can reach its killer in less than half a second. Check its first
	# rendered frames after the map's square pickup has prepared shared finishes.
	set_camera(Vector3(0,1,0),3.0)
	var square_core := CoreOrb.new("energy")
	stage.add_child(square_core)
	square_core.position=Vector3(-0.35,1,0)
	await frames(180)
	if rt:
		var core_readiness:Dictionary=await ResourcePreparation.wait_for_rendering(self,root,true)
		if not core_readiness.ready:push_error(str(core_readiness));quit(11);return
	await RenderingServer.frame_post_draw
	var core_background := root.get_texture().get_image()
	var dropped_core := CoreOrb.new("energy",true)
	stage.add_child(dropped_core)
	dropped_core.position=Vector3(0,1,0)
	await frames(2)
	await RenderingServer.frame_post_draw
	var core_image := root.get_texture().get_image()
	var core_center := Vector2i(camera.unproject_position(dropped_core.global_position))
	var core_pixels := 0
	for y in range(core_center.y-16,core_center.y+17):
		for x in range(core_center.x-16,core_center.x+17):
			var color := core_image.get_pixel(x,y)
			var background := core_background.get_pixel(x,y)
			if color.b-background.b>0.18 and color.g-background.g>0.18: core_pixels+=1
	if core_pixels<3:
		push_error("Dropped energy core missing during its short homing flight: "+str(core_pixels));quit(11);return
	if core_image.save_png(report_directory.path_join("core-first-"+mode+".png"))!=OK:
		push_error("Could not save the first-frame pickup capture");quit(11);return
	await capture("dropped-energy-core",dropped_core,{"first_frames":2,"visible_emissive_pixels":core_pixels})
	await remove_case(dropped_core)
	await remove_case(square_core)
	if core_only:
		FileAccess.open(report_directory.path_join("effects-"+mode+".json"),FileAccess.WRITE).store_string(JSON.stringify(samples,"\t"))
		if reconstruction_observer: reconstruction_observer.release()
		stage.queue_free()
		await frames(6)
		print("EFFECTS_CAPTURE_DONE ",mode," cases=",samples.size())
		quit()
		return
	# Two instances share a shader/material but must retain independent values.
	var shared_shader := Shader.new()
	shared_shader.code="shader_type spatial; render_mode unshaded; instance uniform vec4 effect_tint : source_color = vec4(1.0); instance uniform float effect_phase = 0.0; varying float pulse; void vertex(){ pulse=effect_phase; } void fragment(){ ALBEDO=effect_tint.rgb*(0.8+0.2*sin(pulse)); }"
	var shared_material := ShaderMaterial.new()
	shared_material.shader=shared_shader
	var uniform_group := Node3D.new()
	stage.add_child(uniform_group)
	var centers: Array[Vector3]=[]
	for index in 2:
		var sphere := MeshInstance3D.new()
		sphere.mesh=SphereMesh.new()
		sphere.mesh.radius=0.25
		sphere.mesh.height=0.5
		sphere.material_override=shared_material
		uniform_group.add_child(sphere)
		sphere.position=Vector3(-0.35 if index==0 else 0.35,1,0)
		sphere.set_instance_shader_parameter("effect_tint",Color(1,0.01,0.01) if index==0 else Color(0.01,0.01,1))
		sphere.set_instance_shader_parameter("effect_phase",float(index))
		centers.append(sphere.position)
	set_camera(Vector3(0,1,0),1.8)
	var uniform_ready := false
	for attempt in range(1800):
		await RenderingServer.frame_post_draw
		var candidate := root.get_texture().get_image()
		var left := candidate.get_pixelv(Vector2i(camera.unproject_position(centers[0])))
		var right := candidate.get_pixelv(Vector2i(camera.unproject_position(centers[1])))
		if left.r>0.15 and left.r>left.b*2.0 and right.b>0.15 and right.b>right.r*2.0:
			uniform_ready=true
			break
		await process_frame
	await capture("instance-uniforms-unshaded",uniform_group,{"ready":uniform_ready})
	var uniform_image := root.get_texture().get_image()
	for index in 2:
		var pixel := Vector2i(camera.unproject_position(centers[index]))
		var color := uniform_image.get_pixelv(pixel)
		if (index==0 and (color.r<0.15 or color.r<color.b*2.0)) or (index==1 and (color.b<0.15 or color.b<color.r*2.0)):
			push_error("Per-instance unshaded color was lost: " + str(color))
			quit(4)
			return
	await remove_case(uniform_group)
	# Opaque particle draw passes must keep particle transforms and opaque depth.
	var particle_group := Node3D.new()
	stage.add_child(particle_group)
	var particles := GPUParticles3D.new()
	particles.local_coords=true
	particles.amount=1
	particles.lifetime=60.0
	particles.preprocess=0.1
	particles.position=Vector3(0,1,0)
	var process := ParticleProcessMaterial.new()
	process.gravity=Vector3.ZERO
	process.initial_velocity_min=0.0
	process.initial_velocity_max=0.0
	particles.process_material=process
	var particle_mesh := SphereMesh.new()
	particle_mesh.radius=0.22
	particle_mesh.height=0.44
	var green := StandardMaterial3D.new()
	green.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	green.albedo_color=Color(0.01,1.0,0.01)
	particle_mesh.material=green
	particles.draw_pass_1=particle_mesh
	particle_group.add_child(particles)
	set_camera(Vector3(0,1,0),1.8)
	for attempt in range(1800):
		await RenderingServer.frame_post_draw
		var pixel := Vector2i(camera.unproject_position(particles.position))
		var color := root.get_texture().get_image().get_pixelv(pixel)
		if color.g>0.15 and color.g>color.r*1.5 and color.g>color.b*1.5: break
		await process_frame
	await capture("opaque-particle",particle_group)
	await RenderingServer.frame_post_draw
	var particle_color := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(particles.position)))
	if particle_color.g<0.15 or particle_color.g<particle_color.r*1.5:
		push_error("Opaque GPU particle missing: "+str(particle_color))
		quit(6)
		return
	var blocker := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size=Vector3(0.7,0.7,0.15)
	blocker.mesh=box
	var red := StandardMaterial3D.new()
	red.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	red.albedo_color=Color(1,0.01,0.01)
	blocker.material_override=red
	particle_group.add_child(blocker)
	blocker.position=Vector3(0,1,0.35)
	# Wait for the blocker's asynchronous RT material compilation before testing depth.
	particles.visible=false
	for attempt in range(1800):
		await RenderingServer.frame_post_draw
		var color := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(blocker.position)))
		if color.r>0.15 and color.r>color.g*1.5: break
		await process_frame
	particles.visible=true
	await frames(60)
	await capture("particle-depth-occluded",particle_group)
	await RenderingServer.frame_post_draw
	var occluded := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(particles.position)))
	if occluded.r<0.15 or occluded.r<occluded.g*1.5:
		push_error("Particle leaked through opaque depth: "+str(occluded))
		quit(7)
		return
	particles.position.z=0.75
	await frames(60)
	await capture("particle-depth-front",particle_group)
	await RenderingServer.frame_post_draw
	var foreground := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(particles.position)))
	if foreground.g<0.15 or foreground.g<foreground.r*1.5:
		push_error("Foreground particle was incorrectly hidden: "+str(foreground))
		quit(8)
		return
	await remove_case(particle_group)
	var projectiles := {"lightning-orb":LightningOrb,"fire-orb":FireOrb,"emp-charge":EmpCharge,"bio-blob":BioProjectileVisual,"pulse-round":PulseProjectileVisual,"flak-round":FlakRoundVisual,"nozzle-exhaust":NozzleExhaust,"pilot-flame":FlamePilot}
	for id in projectiles:
		var node: Node3D=projectiles[id].new()
		if id == "flak-round": node.fragmented = true
		stage.add_child(node)
		node.position=Vector3(0,1,0)
		if id in ["nozzle-exhaust","pilot-flame"]: node.rotation.y=PI/2.0
		set_camera(node.position,0.7 if id in ["lightning-orb","fire-orb","pulse-round","flak-round"] else 0.55 if id in ["emp-charge","nozzle-exhaust","pilot-flame"] else 1.6)
		if id=="pulse-round":
			var visible_round := false
			for attempt in range(1800):
				await RenderingServer.frame_post_draw
				var color := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(node.position)))
				var edge := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(node.position+camera.global_basis.x*0.012)))
				if minf(color.r,minf(color.g,color.b))>0.65 and edge.b>0.3 and edge.b>edge.r*1.2:
					visible_round=true
					break
				await process_frame
			if not visible_round:
				push_error("Pulse round did not render after shader warmup")
				quit(9)
				return
		await capture(id,node)
		await remove_case(node)
	for id in ["explosion","grenade_explosion","electric_contact","fire_contact","emp_contact","pulse_contact","bio_contact","flak_contact","impact"]:
		set_camera(Vector3(0,1,0),7.0 if id in ["explosion","grenade_explosion"] else 4.5)
		effects.call(id,Vector3(0,1,0),Vector3.BACK)
		await frames(7)
		freeze(effects)
		await capture(id,effects)
		await remove_case(effects)
		effects=ArenaEffects.new()
		stage.add_child(effects)
	for id in ["jump-pad","speed-ramp","portal","thruster","repair"]:
		var node: Node3D
		if id=="jump-pad":
			node=Assets.model("gameplay","jump_pad")
			stage.add_child(node)
			var pulse := JumpPadEnergyPulse.new()
			node.add_child(pulse)
		elif id=="speed-ramp":
			node=Assets.model("gameplay","speed_ramp")
			stage.add_child(node)
			var arrows := SpeedRampEnergyArrows.new()
			arrows.configure(JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/gameplay/speed_ramp/speed_ramp_rig.json")),false)
			node.add_child(arrows)
		elif id=="portal":
			node=Assets.model("gameplay","portal_gate")
			stage.add_child(node)
			for mesh in node.find_children("*","MeshInstance3D",true,false):
				if String(mesh.name).contains("Field"): PortalVfx.install(mesh)
		elif id=="thruster":
			node=NozzleExhaust.new()
			node.length_m=5.5
			node.radius_m=0.75
			stage.add_child(node)
			node.position=Vector3(0,2,0)
			node.rotation.y=PI/2.0
		else:
			node=Assets.model("gameplay","repair_station")
			stage.add_child(node)
			var world := WeldingWorld.new()
			world.camera=camera
			world.effects=effects
			node.add_child(world)
			var welder := RepairWelding.new()
			var occupant := ArenaRobot.new()
			# Only the alive flag is required by this isolated effect controller.
			var station := {"node":node,"occupant":occupant,"elapsed":1.0+2.0/30.0}
			welder.install(world,station)
			welder.windows=[[0,150]]
			welder._process(0.01)
			await frames(8)
			freeze(node)
			occupant.free()
		set_camera(Vector3(0,1,0),8.0 if id in ["portal","speed-ramp","thruster"] else 4.0)
		await capture(id,node)
		await remove_case(node)
	for distance in [1.0,5.0]:
		var core := CoreOrb.new("energy",true)
		stage.add_child(core)
		core.position=Vector3(0,0.2,0)
		await frames(3)
		freeze(core)
		set_camera(core.position,distance)
		await frames(120)
		await capture("energy-drop-near" if distance==1.0 else "energy-drop-distance",core,{"camera_distance_m":camera.global_position.distance_to(core.global_position),"authored_diameter_m":0.1})
		await remove_case(core)
	var report := FileAccess.open(report_directory.path_join("effects-%s.json" % mode),FileAccess.WRITE)
	report.store_string(JSON.stringify(samples,"\t"))
	report.close()
	print("EFFECTS_CAPTURE_DONE ",mode," cases=",samples.size())
	if reconstruction_observer:reconstruction_observer.release()
	stage.queue_free()
	await frames(5)
	quit()
