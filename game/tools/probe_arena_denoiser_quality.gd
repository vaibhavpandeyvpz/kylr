extends SceneTree
## Fixed real-map views isolate lighting reconstruction from simulation/camera
## timing. This fixture measures image quality, never game FPS.
const Preparation=preload("res://scripts/core/resource_preparation.gd")
const HDRAccumulator=preload("res://tools/hdr_reference_accumulator.gd")
const DenoiserObserver=preload("res://scripts/debug/reconstruction_observer.gd")
const REFERENCE_BATCH_SPP=32
var reference_batch_spp:=REFERENCE_BATCH_SPP
var options:Dictionary={}
var game:ArenaMatch
var camera:Camera3D
var directory:String
var reference_accumulator
var reference_captures:Array=[]
var asset_placement:Dictionary={}
var denoiser_observer

func denoiser_state()->Dictionary:
	return denoiser_observer.stats() if denoiser_observer else {}

func reference_image(environment:Environment,total_spp:int,name:String)->Image:
	reference_accumulator.begin_capture()
	var remaining:=total_spp
	var batches:Array=[]
	while remaining>0:
		var batch:=mini(reference_batch_spp,remaining)
		if environment.get("pathtracing_samples_per_pixel")!=batch:
			environment.set("pathtracing_samples_per_pixel",batch)
			await process_frame
			var ready:Dictionary=await Preparation.wait_for_rendering(self,root,true)
			if not ready.ready:push_error(str(ready));quit(6);return null
		if environment.get("pathtracing_samples_per_pixel")!=batch or environment.get("pathtracing_denoiser")!=0:
			push_error("Arena reference batch configuration differs");quit(6);return null
		reference_accumulator.arm(batch)
		var expected:=total_spp-remaining+batch
		while int(reference_accumulator.stats().weight)<expected:
			await RenderingServer.frame_post_draw
			if not String(reference_accumulator.stats().error).is_empty():push_error(str(reference_accumulator.stats()));quit(6);return null
		batches.append(batch);remaining-=batch
	var completed:Dictionary=reference_accumulator.stats()
	if int(completed.weight)!=total_spp or int(completed.batches)!=batches.size():
		push_error("Arena reference accumulator did not complete its sample budget");quit(6);return null
	reference_captures.append({"name":name,"linear_hdr":true,"samples_per_internal_pixel":total_spp,"batches":batches,"completed_weight":completed.weight})
	return root.get_texture().get_image()

func apron_views(map_id:String)->Array:
	var asset:="bunker" if map_id=="skyfall" else "shelter"
	var marker:Dictionary={}
	for candidate in game.map.markers:
		if candidate.get("asset")==asset:
			marker=candidate;break
	if marker.is_empty():push_error("Missing authored apron placement: "+asset);quit(7);return []
	var fixture:Variant=game.map.fixture_by_id(String(marker.name))
	if fixture==null or not is_instance_valid(fixture.node):push_error("Authored apron fixture was not loaded");quit(7);return []
	var node:Node3D=fixture.node
	var surfaces:Array=[]
	var bounds:=AABB();var have_bounds:=false
	for part in node.find_children("*","MeshInstance3D",true,false):
		var mesh_instance:=part as MeshInstance3D
		if mesh_instance.mesh==null:continue
		for index in mesh_instance.mesh.get_surface_count():
			var material:=mesh_instance.get_active_material(index) as StandardMaterial3D
			if material==null or Assets.material_role(material.resource_name) not in ["M_Regolith","M_RegolithLight","M_RegolithDark"]:continue
			if material.albedo_texture!=Assets.REGOLITH_ALBEDO or material.normal_texture!=Assets.REGOLITH_NORMAL or material.roughness_texture!=Assets.REGOLITH_ORM or material.ao_texture!=Assets.REGOLITH_ORM or not material.normal_enabled or not material.ao_enabled or not material.uv1_triplanar or not material.uv1_world_triplanar or material.roughness_texture_channel!=BaseMaterial3D.TEXTURE_CHANNEL_GREEN or material.ao_texture_channel!=BaseMaterial3D.TEXTURE_CHANNEL_RED or material.metallic!=0.0:
				push_error("Placed apron does not use the canonical runtime PBR material");quit(7);return []
			surfaces.append({"mesh":str(node.get_path_to(mesh_instance)),"surface":index,"material":material.resource_name,"albedo":material.albedo_texture.resource_path,"normal":material.normal_texture.resource_path,"orm":material.roughness_texture.resource_path,"normal_scale":material.normal_scale,"world_triplanar":true,"uv_scale":str(material.uv1_scale),"metallic":material.metallic})
			var mesh_bounds:=mesh_instance.get_aabb()
			for endpoint in 8:
				var local:Vector3=node.to_local(mesh_instance.global_transform*mesh_bounds.get_endpoint(endpoint))
				if have_bounds:bounds=bounds.expand(local)
				else:bounds=AABB(local,Vector3.ZERO);have_bounds=true
	if surfaces.is_empty() or not have_bounds:push_error("Placed asset has no canonical regolith surface");quit(7);return []
	var extent:=maxf(5.0,maxf(bounds.size.x,bounds.size.z))
	var origin:=node.global_position
	asset_placement={"asset":asset,"fixture":String(marker.name),"node":str(node.get_path()),"world_transform":str(node.global_transform),"local_apron_bounds":str(bounds),"surfaces":surfaces,"textures":{"albedo":FileAccess.get_sha256(Assets.REGOLITH_ALBEDO.resource_path),"normal":FileAccess.get_sha256(Assets.REGOLITH_NORMAL.resource_path),"orm":FileAccess.get_sha256(Assets.REGOLITH_ORM.resource_path)},"visual_quality_accepted":false}
	return [{"name":asset+"-hero","position":node.to_global(Vector3(extent*1.15,extent*.55,extent*1.15)),"target":origin+Vector3.UP*.9},
		{"name":asset+"-ground","position":node.to_global(Vector3(extent*.8,1.6,extent*.8)),"target":origin+Vector3.UP*.15},
		{"name":asset+"-side","position":node.to_global(Vector3(extent*1.2,2.0,0)),"target":origin+Vector3.UP*.6}]

func _initialize():run.call_deferred()

func run():
	AudioServer.set_bus_mute(0,true)
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--") and "=" in argument:options[argument.get_slice("=",0).trim_prefix("--")]=argument.get_slice("=",1)
	create_timer(clampi(int(options.get("timeout-seconds","600")),60,7200)).timeout.connect(func():push_error("ARENA_QUALITY_TIMEOUT");quit(8))
	var view_set:=String(options.get("view-set","lighting"))
	if view_set not in ["lighting","regolith-aprons","sky-motion"]:quit(2);return
	var mode:=String(options.get("mode","dlss"))
	if view_set=="sky-motion" and mode=="reference":
		push_error("Moving cameras cannot use fixed-view reference accumulation");quit(2);return
	var map_id:=String(options.get("map","skyfall"))
	var output_size:=Vector2i(1920,1080) if options.get("full-hd","false")=="true" else Vector2i(640,360)
	var reference_spp:=int(options.get("reference-spp","1023"))
	# Bound each dispatch without reducing the total FP32 HDR sample budget.
	reference_batch_spp=int(options.get("reference-batch-spp",str(REFERENCE_BATCH_SPP)))
	if reference_batch_spp<1 or reference_batch_spp>REFERENCE_BATCH_SPP:quit(2);return
	var rr_preset:=String(options.get("rr-preset","?"))
	if rr_preset not in ["?","D","E"]:quit(2);return
	if rr_preset!="?":
		if not Engine.has_singleton("Streamline"):quit(2);return
		Streamline.set_parameter(Streamline.STREAMLINE_PARAM_DLSS_RR_PRESET,rr_preset)
	print("ARENA_QUALITY_RR_PRESET ",rr_preset)
	if reference_spp<128 or reference_spp>16384:quit(2);return
	if mode not in ["reference","dlss","dlss-half"] or map_id not in ["skyfall","faceoff"]:quit(2);return
	if mode!="reference" and OS.get_environment("GODOT_DLSS_DIAGNOSTICS")!="1":
		push_error("DLSS image qualification requires native evaluation diagnostics");quit(2);return
	if DisplayServer.get_name()=="headless":
		push_error("Arena quality requires a graphical run without diagnostic backend overrides");quit(2);return
	directory=String(options.get("report-dir","res://reports/performance/arena-quality"))
	DirAccess.make_dir_recursive_absolute(directory)
	var prefs:=Preferences.new(directory+"/preferences.cfg")
	prefs.values.quality=3;prefs.values.quality_benchmarked=true
	for key in Preferences.QUALITY_PRESETS[3]:prefs.values[key]=Preferences.QUALITY_PRESETS[3][key]
	# Borderless mode preserves 1080p on a 1080p desktop; a decorated window
	# is deliberately clamped to the available work area by display preferences.
	prefs.values.display_mode=1 if output_size==Vector2i(1920,1080) else 0
	prefs.values.resolution=output_size
	prefs.values.rt_denoiser=Preferences.DENOISER_DLSS
	prefs.values.rt_upscaling=mode=="dlss-half"
	prefs.values.reduced_motion=true
	if not Preferences.ray_tracing_unavailable_reason(int(prefs.values.rt_denoiser)).is_empty():
		push_error("Requested quality backend unavailable");quit(2);return
	prefs.apply_display()
	await Preparation.match_resources(self,map_id)
	game=ArenaMatch.new()
	game.map_id=map_id;game.count=2;game.async_scene_loading=true;game.loading_hold=true
	game.set_meta("profile_roster_seed",120)
	game.on_ready=func():prefs.apply_rendering(game)
	root.add_child(game)
	while not game.initialization_complete:await process_frame
	game.process_mode=Node.PROCESS_MODE_DISABLED
	for robot in game.robots:robot.hide()
	if game.first_person:game.first_person.hide()
	game.camera.current=false
	camera=Camera3D.new();camera.fov=60;camera.near=.04;camera.far=700
	root.add_child(camera);camera.current=true
	var worlds:=game.find_children("*","WorldEnvironment",true,false)
	if worlds.size()!=1:push_error("Expected one arena environment");quit(3);return
	var environment:Environment=worlds[0].environment
	if mode=="reference":
		# Raw references must bypass DLAA/SR and temporal/spatial AA after
		# accumulation, while retaining the normal glow and tone mapping.
		root.scaling_3d_mode=Viewport.SCALING_3D_MODE_BILINEAR
		root.scaling_3d_scale=1.0
		root.use_taa=false
		root.msaa_3d=Viewport.MSAA_DISABLED
		root.screen_space_aa=Viewport.SCREEN_SPACE_AA_DISABLED
		reference_accumulator=HDRAccumulator.new()
		var compositor:=Compositor.new();compositor.compositor_effects=[reference_accumulator]
		worlds[0].compositor=compositor
	else:
		denoiser_observer=DenoiserObserver.new()
		var compositor:=Compositor.new();compositor.compositor_effects=[denoiser_observer]
		worlds[0].compositor=compositor
	var denoisers:Dictionary={"reference":0,"dlss":1,"dlss-half":1}
	environment.set("pathtracing_denoiser",denoisers[mode])
	environment.set("pathtracing_samples_per_pixel",1)
	if not environment.get("pathtracing_enabled") or environment.get("pathtracing_denoiser")!=denoisers[mode]:
		push_error("Requested arena path tracer/denoiser is not active");quit(3);return
	var views:Array=[]
	if map_id=="skyfall":
		views=[{"name":"lower-deck","position":Vector3(22,23.6,22.5),"target":Vector3(12,23,22.5)},
			{"name":"roof-deck","position":Vector3(22,31.6,22.5),"target":Vector3(8,30,8)}]
	else:
		views=[{"name":"laboratory","position":Vector3(24.4,1.8,-24.4),"target":Vector3(29,1.8,-20)},
			{"name":"habitat","position":Vector3(29.65,2.1,29.4),"target":Vector3(29.65,2.1,25)}]
	if view_set=="regolith-aprons":
		views=apron_views(map_id)
		if views.size()!=3:return
	var camera_motion:=view_set=="sky-motion"
	if camera_motion:views=[views[1]]
	var cases:Array=[]
	for view in views:
		camera.position=view.position;camera.look_at(view.target)
		var base_yaw:=camera.rotation.y
		var capture_count:=32 if camera_motion else (4 if mode=="reference" else 16)
		if camera_motion:camera.rotation.y=base_yaw-deg_to_rad(0.08)*15.5
		environment.set("pathtracing_samples_per_pixel",reference_batch_spp if mode=="reference" else 1)
		# The sampling flags select shader variants. Warm the actual capture
		# configuration before asking for readiness, not a 1-SPP precursor.
		for frame in 2:await RenderingServer.frame_post_draw
		var ready:Dictionary=await Preparation.wait_for_rendering(self,root,true)
		if not ready.ready:push_error(str(ready));quit(4);return
		# Raw reference samples are independent; only temporal denoisers need
		# history accumulation. Both paths still require actual-config readiness.
		var warmup_frames:=8 if mode=="reference" else 120
		var settling:Array=[]
		var settling_images:Array[Image]=[]
		var warmup_start_usec:=Time.get_ticks_usec()
		for frame in warmup_frames:
			await RenderingServer.frame_post_draw
		var warmup_wall_seconds:=float(Time.get_ticks_usec()-warmup_start_usec)/1000000.0
		var files:Array=[]
		var images:Array[Image]=[]
		var camera_frames:Array=[]
		var reconstruction_before:=denoiser_state()
		var capture_start_usec:=Time.get_ticks_usec()
		var readback_usec:=0
		for sample_index in capture_count:
			if camera_motion:camera.rotation.y=base_yaw+deg_to_rad(0.08)*(sample_index-15.5)
			await RenderingServer.frame_post_draw
			var readback_start_usec:=Time.get_ticks_usec()
			var name:String=view.name+"-%02d.png"%sample_index
			var image:Image=await reference_image(environment,reference_spp,name) if mode=="reference" else root.get_texture().get_image()
			if image==null:return
			readback_usec+=Time.get_ticks_usec()-readback_start_usec
			if image.get_size()!=output_size:push_error("Incorrect quality output size: "+str(image.get_size()));quit(5);return
			files.append(name)
			if camera_motion:camera_frames.append({"file":name,"yaw_radians":camera.rotation.y})
			images.append(image)
		var capture_wall_seconds:=float(Time.get_ticks_usec()-capture_start_usec)/1000000.0
		if denoiser_observer:
			var state:Dictionary=denoiser_state()
			if not String(state.error).is_empty() or not state.adapter.get("evaluation_succeeded",false) or int(state.adapter.get("frames",0))<=0:
				push_error("Arena capture lacks successful native DLSS evaluation");quit(6);return
		# PNG encoding and disk writes must not change the next sample's delta
		# and therefore the denoiser's frame-rate-dependent history limits.
		# GPU readback still stalls; record its cost and never call this FPS.
		for sample_index in images.size():
			if images[sample_index].save_png(directory+"/"+files[sample_index])!=OK:quit(5);return
		for sample_index in settling_images.size():
			if settling_images[sample_index].save_png(directory+"/"+settling[sample_index].file)!=OK:quit(5);return
		cases.append({"name":view.name,"position":str(view.position),"target":str(view.target),"files":files,"camera_frames":camera_frames,"denoiser_before":reconstruction_before,"settling":settling,"denoiser":denoiser_state(),"readiness":ready,"warmup_frames":warmup_frames,"warmup_wall_seconds":warmup_wall_seconds,"warmup_render_fps":float(warmup_frames)/maxf(warmup_wall_seconds,.000001),"capture_wall_seconds":capture_wall_seconds,"capture_readback_seconds":float(readback_usec)/1000000.0 if mode!="reference" else null,"reference_accumulation_and_readback_seconds":float(readback_usec)/1000000.0 if mode=="reference" else null,"deferred_png_encoding":true})
		print("ARENA_QUALITY_CASE ",map_id," ",mode," ",view.name)
	if reference_accumulator:
		reference_accumulator.release()
		while not reference_accumulator.stats().released:await process_frame
	if denoiser_observer:
		denoiser_observer.release()
		while not denoiser_observer.stats().released:await process_frame
		worlds[0].compositor=null
		denoiser_observer=null
	var renderer:={"pathtracing_enabled":environment.get("pathtracing_enabled"),"denoiser":environment.get("pathtracing_denoiser"),"samples_per_pixel":environment.get("pathtracing_samples_per_pixel"),"max_bounces":environment.get("pathtracing_max_bounces"),"internal_scale":root.scaling_3d_scale,"scaling_mode":root.scaling_3d_mode,"taa":root.use_taa,"msaa":root.msaa_3d,"screen_space_aa":root.screen_space_aa}
	FileAccess.open(directory+"/report.json",FileAccess.WRITE).store_string(JSON.stringify({"complete":true,"capture_revision":6,"camera_motion":camera_motion,"rr_preset_requested":rr_preset,"reference_batch_spp":reference_batch_spp,"view_set":view_set,"asset_placement":asset_placement,"renderer":renderer,"mode":mode,"map":map_id,"cases":cases,"output":[output_size.x,output_size.y],"reference_spp":reference_spp,"reference_captures":reference_captures,"reference_helper_sha256":FileAccess.get_sha256("res://tools/hdr_reference_accumulator.gd"),"frozen_simulation":true,"full_game_quality_acceptance":false,"performance_acceptance":false},"\t"))
	game.free();camera.free()
	for frame in 6:await process_frame
	print("ARENA_QUALITY_CAPTURE_PASS ",map_id," ",mode)
	quit()
