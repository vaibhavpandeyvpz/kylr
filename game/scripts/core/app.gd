extends Node3D
const ResourcePreparation=preload("res://scripts/core/resource_preparation.gd")
const LoadingScreen=preload("res://scripts/ui/loading_screen.gd")
signal startup_finished
var startup_complete := false
var starting_match := false
var loading_screen
var loading_reports: Array[Dictionary] = []
var prefs: Preferences
var ui: ArenaUI
var match_node: ArenaMatch
var preview: Node3D
var preview_viewport: SubViewport
var preview_surface: TextureRect
var preview_turntable: Node3D
var preview_robot: Node3D
var preview_camera: Camera3D
var api
var online_ui: OnlineUI
var music: ArenaMusic
var preview_animator: AnimationPlayer
var preview_victory_id := ""
var closing := false
var leaving := false

func _ready():
	set_meta("menu_studio_host",true)
	get_tree().auto_accept_quit=false
	loading_screen=get_meta("startup_loading_screen") if has_meta("startup_loading_screen") else null
	if loading_screen==null:
		loading_screen=LoadingScreen.new()
		add_child(loading_screen)
	await loading_screen.paint()
	var startup_started := Time.get_ticks_usec()
	prefs=Preferences.new(get_meta("preferences_path","user://preferences.cfg"))
	prefs.apply_display()
	ui=ArenaUI.new()
	ui.app=self
	add_child(ui)
	ui.root.resized.connect(resize_preview)
	api = OnlineClient.new()
	add_child(api)
	api.changed.connect(func(): preview_victory_id = preview_victory(api.player.get("loadout",{}).get("emote","")))
	online_ui = OnlineUI.new()
	online_ui.app = self
	online_ui.ui = ui
	online_ui.api = api
	add_child(online_ui)
	music = ArenaMusic.new()
	music.app = self
	add_child(music)
	loading_screen.reduced_motion=prefs.values.reduced_motion
	await ResourcePreparation.menu(get_tree())
	make_preview()
	ui.main_menu()
	var ready: Dictionary=await prepare_rendering()
	loading_reports.append({"stage":"menu","seconds":(Time.get_ticks_usec()-startup_started)/1000000.0,"max_frame_gap_ms":loading_screen.max_frame_gap_ms,"rendering":ready})
	loading_screen.finish()
	startup_complete=true
	startup_finished.emit()
	if not get_meta("automated_profile",false) and DisplayServer.get_name()!="headless" and "--smoke" not in OS.get_cmdline_user_args():
		ResourcePreparation.match_resources(get_tree(),String(prefs.values.map))
	if OS.has_feature("debug") and "--capture" in OS.get_cmdline_user_args():
		get_tree().create_timer(float(argument("capture-at", "27" if "--smoke" in OS.get_cmdline_user_args() else "4"))).timeout.connect(func():
			if match_node:
				if "--overview" in OS.get_cmdline_user_args():
					match_node.set_process(false)
					match_node.camera_rig.host.set_process(false)
					match_node.camera.global_position=Vector3(62,46,70)
					match_node.camera.look_at(Vector3(0,7,0))
					ui.hide()
					for child in match_node.get_children():
						if child is FirstPersonRig: child.set_process(false); child.hide()
				print("CAPTURE camera=",match_node.camera.global_transform," local=",match_node.local_robot.position)
				print("MAP bounds ",match_node.map.model.get_aabb() if match_node.map.model is VisualInstance3D else "root")
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png("res://reports/preview.png")
			request_quit())
	if OS.has_feature("debug") and "--smoke" in OS.get_cmdline_user_args():
		prefs.values.name="TestPilot"
		prefs.values.count=int(argument("robots","10"))
		prefs.values.type=MatchTypes.ALL.find(argument("type","DM"))
		if argument("view", "") in ["fpv", "tpv"]: prefs.values.third_person=argument("view", "") == "tpv"
		start_match()
		get_tree().create_timer(float(argument("duration","32"))).timeout.connect(func():
			print("SMOKE phase=",match_node.phase," robots=",match_node.robots.size()," navigation=",match_node.map.nav.get_point_count())
			var fixture: Dictionary=match_node.local_robot.spawn_fixture
			print("SPAWN point=",fixture.point," prop=",fixture.node.global_position," mount=",fixture.mount.global_position," robot=",match_node.local_robot.global_position)
			for robot in match_node.robots:
				if robot.brain: print("BT ",robot.display_name," intent=",robot.brain.goal_kind," route=",robot.brain.path.size()," kills=",robot.kills," deaths=",robot.deaths)
			print("AUDIO ",match_node.audio.metrics)
			request_quit())
	if OS.has_feature("debug") and "--profile-rendered" in OS.get_cmdline_user_args():
		var profile = load("res://scripts/debug/rendered_combat_profile.gd").new()
		profile.app = self
		get_tree().root.add_child.call_deferred(profile)

func _notification(what):
	if what==NOTIFICATION_WM_CLOSE_REQUEST: request_quit()

func request_quit():
	if closing: return
	closing=true
	get_tree().paused=false
	if music: music.shutdown()
	if ui: ui.close_page()
	if online_ui: await online_ui.shutdown_views()
	if match_node:
		if match_node.online: online_ui.dispose_transport()
		else: match_node.free()
		match_node=null
	retire_preview()
	# Allow the audio mixer to release stopped voices before engine teardown.
	var deadline := Time.get_ticks_msec()+100
	while Time.get_ticks_msec()<deadline:
		await get_tree().process_frame
	get_tree().quit()

func argument(key: String, fallback: String) -> String:
	for entry in OS.get_cmdline_user_args():
		if entry.begins_with("--"+key+"="): return entry.get_slice("=",1)
	return fallback

func make_preview():
	if is_instance_valid(preview): return
	preview_viewport=MenuStudio.create(get_tree(),Vector2i(get_viewport().get_visible_rect().size))
	preview_surface=TextureRect.new()
	preview_surface.name="MainMenuPortrait"
	preview_surface.texture=preview_viewport.get_texture()
	preview_surface.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	preview_surface.mouse_filter=Control.MOUSE_FILTER_IGNORE
	ui.root.add_child(preview_surface)
	ui.root.move_child(preview_surface,0)
	preview_surface.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var canvas := ColorRect.new()
	canvas.color=MenuSkin.CANVAS
	canvas.show_behind_parent=true
	canvas.mouse_filter=Control.MOUSE_FILTER_IGNORE
	preview_surface.add_child(canvas)
	canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	preview=Node3D.new()
	preview_viewport.add_child(preview)
	preview_turntable=Node3D.new()
	preview_turntable.name="PreviewTurntable"
	preview.add_child(preview_turntable)
	preview_robot=Assets.model("characters","tensor")
	preview_turntable.add_child(preview_robot)
	Assets.paint(preview_robot,Color("566f7e"),Color("dae0db"),"projector")
	var skeleton:=Assets.find(preview_robot,"Skeleton3D")
	var animator:=AnimationPlayer.new()
	preview_animator = animator
	skeleton.get_parent().add_child(animator)
	var library:=AnimationLibrary.new()
	var idle := Assets.animation("common/idle")
	if idle:
		idle = idle.duplicate()
		idle.loop_mode = Animation.LOOP_NONE
		library.add_animation("common_idle",idle)
	animator.add_animation_library("",library)
	preview_victory_id = preview_victory(api.player.get("loadout",{}).get("emote",""))
	animator.animation_finished.connect(func(clip):
		if clip == "common_idle": preview_emote(preview_victory_id)
		else: animator.play("common_idle",0.2))
	animator.play("common_idle")
	var floor:=MeshInstance3D.new()
	var cylinder:=CylinderMesh.new()
	cylinder.top_radius=1.5
	cylinder.bottom_radius=1.6
	cylinder.height=0.15
	floor.mesh=cylinder
	var regolith:=Assets.regolith_material()
	# Anchor the grain to the turntable so it rotates with the platform.
	regolith.uv1_world_triplanar=false
	floor.material_override=regolith
	preview_turntable.add_child(floor)
	floor.position.y=-cylinder.height*0.5
	preview_camera=Camera3D.new()
	preview.add_child(preview_camera)
	preview_camera.position=Vector3(0,1.2,3.5)
	preview_camera.look_at(Vector3(-0.65,0.85,0))
	preview_camera.fov=45
	preview_camera.current=true
	var preview_host := PhantomCameraHost.new()
	preview_camera.add_child(preview_host)
	var preview_pcam := PhantomCamera3D.new()
	preview_pcam.name = "PreviewPCam"
	preview_pcam.tween_on_load = false
	preview_pcam.global_transform = preview_camera.global_transform
	var preview_lens := Camera3DResource.new()
	preview_lens.fov = 45.0
	preview_pcam.camera_3d_resource = preview_lens
	preview.add_child(preview_pcam)
	preview_pcam.priority = 10
	prefs.apply_rendering(self)
	call_deferred("benchmark_quality")

func resize_preview():
	if is_instance_valid(preview_viewport): preview_viewport.size=Vector2i(ui.root.size).max(Vector2i.ONE)

func retire_preview():
	if is_instance_valid(preview_surface):
		preview_surface.hide()
		preview_surface.texture=null
		preview_surface.queue_free()
	if is_instance_valid(preview_viewport):
		preview_viewport.render_target_update_mode=SubViewport.UPDATE_DISABLED
		preview_viewport.queue_free()
	preview_surface=null
	preview_viewport=null
	if is_instance_valid(preview): preview.free()
	preview = null
	preview_robot = null
	preview_turntable = null
	preview_camera = null
	preview_animator = null

func benchmark_quality():
	if prefs.values.quality_benchmarked or DisplayServer.get_name() == "headless" or "--smoke" in OS.get_cmdline_user_args() or "--capture" in OS.get_cmdline_user_args(): return
	var stage := preview
	var times: Array[float] = []
	var previous := Time.get_ticks_usec()
	for frame in 40:
		await get_tree().process_frame
		if not is_instance_valid(stage) or stage != preview or closing: return
		var now := Time.get_ticks_usec()
		if frame >= 10: times.append(float(now-previous)/1000.0)
		previous=now
	# Do not overwrite edits made while the startup sample was running.
	if ui.screen != "main" or prefs.values.quality_benchmarked: return
	times.sort()
	var median: float = times[times.size()/2]
	var quality := 0 if median>24.0 else 2 if median<12.0 else 1
	prefs.values.quality=quality
	for detail in Preferences.QUALITY_PRESETS[quality]: prefs.values[detail]=Preferences.QUALITY_PRESETS[quality][detail]
	prefs.values.quality_benchmarked=true
	prefs.apply_rendering(self)
	prefs.save()

func prepare_rendering() -> Dictionary:
	var ready: Dictionary=await ResourcePreparation.wait_for_rendering(get_tree(),get_viewport())
	print("RENDERER_ACTIVE ",Preferences.active_renderer_label(self))
	return ready

func apply_rendering_with_loading() -> void:
	loading_screen.begin("Preparing graphics…")
	await loading_screen.paint()
	prefs.apply_rendering(self)
	await prepare_rendering()
	loading_screen.finish()

func start_match():
	if starting_match: return
	starting_match=true
	if not startup_complete: await startup_finished
	var started := Time.get_ticks_usec()
	loading_screen.begin("Preparing match…")
	await loading_screen.paint()
	await ResourcePreparation.match_resources(get_tree(),String(prefs.values.map))
	retire_preview()
	# Keep native rendering during asynchronous scene assembly.
	get_viewport().scaling_3d_mode=Viewport.SCALING_3D_MODE_BILINEAR
	get_viewport().scaling_3d_scale=1.0
	match_node=ArenaMatch.new()
	match_node.async_scene_loading=true
	match_node.loading_hold=true
	if has_meta("profile_roster_seed"):
		match_node.set_meta("profile_roster_seed",get_meta("profile_roster_seed"))
	match_node.map_id=prefs.values.map
	match_node.match_type=MatchTypes.ALL[prefs.values.type]
	match_node.difficulty=prefs.values.difficulty
	match_node.count=prefs.values.count
	match_node.goal=prefs.values.goal
	match_node.time_limit=prefs.values.minutes*60.0
	if "--smoke" in OS.get_cmdline_user_args(): match_node.time_limit=float(argument("limit-seconds",str(match_node.time_limit)))
	match_node.local_name=prefs.values.name
	match_node.third_person=prefs.values.third_person
	match_node.fov=prefs.values.fov
	match_node.reduced_motion=prefs.values.reduced_motion
	match_node.on_ready = func(): prefs.apply_rendering(self)
	match_node.message.connect(ui.show_notice)
	match_node.completed.connect(ui.results)
	add_child(match_node)
	while not match_node.initialization_complete: await get_tree().process_frame
	ui.start_hud()
	var ready: Dictionary=await prepare_rendering()
	loading_reports.append({"stage":"match","map":match_node.map_id,"seconds":(Time.get_ticks_usec()-started)/1000000.0,"max_frame_gap_ms":loading_screen.max_frame_gap_ms,"rendering":ready})
	match_node.loading_hold=false
	loading_screen.finish()
	starting_match=false

func leave_match():
	if leaving: return
	if match_node and match_node.online:
		get_tree().paused = false
		await online_ui.cancel()
		return
	leaving=true
	get_tree().paused=false
	if match_node:
		match_node.phase="Finished"
		ui.clear_page("leaving")
		if ui.hud: ui.hud.hide()
		var duration: float=match_node.map.shutdown()
		await get_tree().create_timer(duration).timeout
		if closing: return
	loading_screen.begin()
	await loading_screen.paint()
	if match_node: match_node.free(); match_node=null
	ui.retire_control(ui.hud)
	ui.hud=null
	make_preview()
	ui.main_menu()
	var ready: Dictionary=await prepare_rendering()
	if ready.ready: loading_screen.finish()
	leaving=false

func _process(dt):
	if match_node: match_node.reduced_motion=prefs.values.reduced_motion
	if match_node and match_node.callouts: match_node.callouts.frequency = int(prefs.values.callouts)
	if is_instance_valid(preview_viewport):
		var visible := is_instance_valid(preview_surface) and preview_surface.is_visible_in_tree()
		preview_viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS if visible else SubViewport.UPDATE_DISABLED
		if visible and not prefs.values.reduced_motion: preview_turntable.rotation.y+=dt*0.15
	if get_meta("automated_profile",false): return
	if starting_match or not startup_complete: return
	if match_node and match_node.local_robot and ui.screen=="match":
		var r=match_node.local_robot
		r.move_input=Input.get_vector("left","right","forward","backward")
		r.wants_walk=Input.is_action_pressed("walk")
		r.wants_crouch=Input.is_action_pressed("crouch")
		r.wants_sprint=Input.is_action_pressed("sprint") and not r.wants_walk
		r.wants_fire=Input.is_action_pressed("fire")
		r.wants_secondary=Input.is_action_pressed("secondary")
		r.jump_held=Input.is_action_pressed("charged_jump")
	else:
		if match_node and match_node.local_robot:
			var r: ArenaRobot = match_node.local_robot
			r.move_input=Vector2.ZERO
			r.wants_sprint=false
			r.wants_walk=false
			r.wants_crouch=false
			r.wants_fire=false
			r.wants_secondary=false
			r.jump_buffer=0.0
			r.jump_held=false
			r.jump_release=false

func _unhandled_input(event):
	if starting_match or not startup_complete: return
	if event is InputEventKey and event.pressed and event.keycode==KEY_ESCAPE:
		if ui.screen=="match": ui.pause_menu()
		elif ui.screen=="pause": ui.resume()
		return
	if not match_node or not match_node.local_robot or ui.screen!="match": return
	var r: ArenaRobot = match_node.local_robot
	var slot_index := numbered_slot(event)
	if event is InputEventMouseMotion and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED and not r.spawn_look_locked():
		r.yaw-=event.relative.x*prefs.values.sensitivity
		r.pitch=clampf(r.pitch-event.relative.y*prefs.values.sensitivity*(-1 if prefs.values.invert else 1),-PI/4,PI/4)
	if match_node.online and is_instance_valid(online_ui) and is_instance_valid(online_ui.transport):
		var transport: OnlineTransport = online_ui.transport
		if slot_index>=0: transport.discrete.slot="slot:%d" % (slot_index+1)
		if event.is_action_pressed("jump") and not event.is_echo(): transport.discrete.jump = true
		if event.is_action_released("charged_jump"): transport.discrete.release = true
		if event.is_action_pressed("reload"): transport.discrete.reload = true
		if event.is_action_pressed("pistol"): transport.discrete.slot = "pistol"
		if event.is_action_pressed("pickup"): transport.discrete.slot = "slot:2"
		if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]: transport.discrete.slot = "slot:%d" % (r.owned_weapons.find(r.cycle_weapon(1 if event.button_index==MOUSE_BUTTON_WHEEL_DOWN else -1))+1)
		if event.is_action_pressed("view") and r.can_act():
			match_node.third_person = not match_node.third_person
			prefs.values.third_person = match_node.third_person
			prefs.save()
		return
	if event.is_action_pressed("jump") and not event.is_echo(): r.jump_buffer=ArenaTuning.JUMP_BUFFER
	if event.is_action_released("charged_jump"): r.jump_release=true
	if event.is_action_pressed("reload"): r.start_reload()
	if event.is_action_pressed("view") and r.can_act():
		match_node.third_person=not match_node.third_person
		prefs.values.third_person=match_node.third_person
		prefs.save()
	if r.can_act() and r.reload_time<=0:
		if slot_index>=0 and slot_index<r.owned_weapons.size(): r.select_weapon(r.owned_weapons[slot_index])
		if event.is_action_pressed("pistol"): r.select_weapon("pistol")
		if event.is_action_pressed("pickup") and r.owned_weapons.size()>1: r.select_weapon(r.owned_weapons[1])
		if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			r.select_weapon(r.cycle_weapon(1 if event.button_index==MOUSE_BUTTON_WHEEL_DOWN else -1))

func open_online():
	prefs.values.mode="Online Multiplayer"
	prefs.save()
	online_ui.open()

func preview_loadout(loadout: Dictionary):
	if not preview: make_preview()
	Assets.paint(preview_robot,Color(OnlineTransport.PALETTE[loadout.primary]),Color(OnlineTransport.PALETTE[loadout.secondary]),loadout.head,false,loadout.get("upper_body","default"))
	preview_victory_id = preview_victory(loadout.get("emote",""))

func preview_victory(id: String = "") -> String:
	var choices: Array = ContentRegistry.character("tensor").emotes
	return id if id in choices else String(choices[0])

func preview_emote(id: String):
	if not is_instance_valid(preview_animator): return
	id = preview_victory(id)
	var library := preview_animator.get_animation_library("")
	if not library.has_animation(id):
		var clip := Assets.animation("common/"+id)
		if clip == null: return
		clip.loop_mode = Animation.LOOP_NONE
		library.add_animation(id,clip)
	preview_animator.play(id,0.2)

# The first two slots retain their configurable actions; 3–0 address slots 3–10.
static func numbered_slot(event: InputEvent) -> int:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode>=KEY_3 and event.keycode<=KEY_9: return event.keycode-KEY_1
		if event.keycode==KEY_0: return 9
	return -1
