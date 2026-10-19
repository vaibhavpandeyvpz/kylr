class_name ArenaMap
extends Node3D
signal scene_loaded
var loading_complete := false
static var navigation_snapshots: Dictionary = {}
var navigation_cache_hit := false
class PickupStatusPair extends RefCounted:
	var ready: StandardMaterial3D
	var recharging: StandardMaterial3D
	var updated_time := -INF

class PickupIndicator extends RefCounted:
	var mesh: MeshInstance3D
	var surface: int
	var styles: PickupStatusPair

var game
var model: Node3D
var markers: Array = []
var fixtures: Array = []
var fixture_indices: Dictionary = {}
const INTERACTION_KINDS := ["portal","jump_pad","speed_ramp","pressure_plate","repair_station"]
var spawns: Array = []
var nav := AStar3D.new()
var nav_points: Array[Vector3] = []
var assembly: AnimationPlayer
var screen_labels: Array = []
var pickup_labels: Array[Dictionary] = []
var pickup_status_time := 0.0
var pickup_status_styles: Dictionary = {}
var event_warned := false
var event_done := false
var config: Dictionary
var stadium: Node3D
var traversal: TraversalGraph
var play_transform := Transform3D.IDENTITY
var machinery: Array[PropMotion] = []
var jumbotron: JumbotronMotion
var shutting_down := false
static var profile_ticks := false
static var tick_costs: Dictionary = {}

static func profile_stage(stage: String, started: int) -> int:
	var now := Time.get_ticks_usec()
	tick_costs[stage] = int(tick_costs.get(stage,0)) + now - started
	return now

var navigation_region: NavigationRegion3D

func _ready():
	if game.get("async_scene_loading")==true:
		_load_async.call_deferred()
	else:
		_initialize_scene()
		_populate_fixtures()
		_finish_scene()

func _initialize_scene() -> void:
	config = MapCatalog.find(game.map_id)
	model = Assets.model("maps",config.model)
	add_child(model)
	stadium = model
	finish_lunar_surface(model)
	play_transform = model.global_transform
	assembly = Assets.find(model,"AnimationPlayer")
	# Merge the channels belonging to each authored section's action.
	var merged := Animation.new()
	merged.length = 5.0
	for key in assembly.get_animation_list():
		var clip := assembly.get_animation(key)
		for track in clip.get_track_count():
			var path := clip.track_get_path(track)
			var target_name := String(path).get_slice(":",0).get_slice("/",String(path).get_slice(":",0).count("/"))
			if ":" in String(path):
				if not String(key).begins_with("RIG_"): continue
			elif not String(key).begins_with(target_name): continue
			var exists := false
			for t in merged.get_track_count():
				if merged.track_get_path(t) == path and merged.track_get_type(t) == clip.track_get_type(track): exists = true
			if exists: continue
			clip.copy_track(track,merged)
			var index := merged.get_track_count() - 1
			for k in range(merged.track_get_key_count(index)-1,-1,-1):
				merged.track_set_key_time(index,k,merged.track_get_key_time(index,k) * 5.0 / 3.0)
	var library := AnimationLibrary.new()
	library.add_animation("assemble",merged)
	assembly.add_animation_library("runtime",library)
	assembly.play("runtime/assemble")
	assembly.seek(5.0,true)
	assembly.pause()
	CollisionRig.install(model,"maps",config.model)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(config.metadata))
	markers = data.markers

func _populate_fixtures() -> void:
	for marker in markers:
		if marker.role == "platform" or marker.get("load_at_start",false): make_fixture(marker)
	for marker in markers:
		make_fixture(marker)

func _finish_scene() -> void:
	var jumbo := Assets.model("environments","jumbotron")
	var jumbo_marker: Dictionary=markers.filter(func(marker):return marker.role=="jumbotron")[0]
	var jumbo_mount := Assets.socket(model,"Gizmo_"+String(jumbo_marker.name).replace("-","_"))
	assert(jumbo_mount != null,"Map requires an authored jumbotron placement")
	jumbo_mount.add_child(jumbo)
	jumbo.transform = Transform3D.IDENTITY
	jumbotron = JumbotronMotion.new()
	jumbotron.install(jumbo,game)
	ScoreboardDisplay.new().install(jumbo,game)
	add_world()

	loading_complete=true
	scene_loaded.emit()

func _load_async() -> void:
	_initialize_scene()
	await get_tree().process_frame
	var batch_started := Time.get_ticks_usec()
	for pass_index in 2:
		for marker in markers:
			if pass_index==0 and not (marker.role=="platform" or marker.get("load_at_start",false)): continue
			make_fixture(marker)
			if Time.get_ticks_usec()-batch_started>=8000:
				await get_tree().process_frame
				batch_started=Time.get_ticks_usec()
	_finish_scene()

func start_assembly():
	jumbotron.start()

func motion_for(root: Node3D) -> PropMotion:
	var motion := PropMotion.new()
	motion.install(root)
	machinery.append(motion)
	return motion

func shutdown() -> float:
	if shutting_down: return 0.0
	shutting_down = true
	abort_all_repairs("shutdown")
	var duration := jumbotron.shutdown()
	for fixture in fixtures:
		if fixture.kind == "repair_station": update_repair_status(fixture)
		if fixture.kind == "portal":
			fixture.usable = false
			update_portal_status(fixture)
			var state: Dictionary = fixture.motion.channels.main
			var remaining: float = state.player.get_animation(state.clip).length-state.time if not state.done and not (state.loop and fixture.motion.reduced_motion) else 0.0
			duration = maxf(duration,remaining+state.player.get_animation("deactivate").length)
			fixture.motion.at_boundary("deactivate")
	return duration

func start_map_assembly():
	assembly.play("runtime/assemble")
	assembly.seek(0,true)

func start_loadout():
	for marker in markers:
		make_fixture(marker)
	for flag in game.flags:
		flag.base_effect.visible = game.match_type == "CTF"

func world_point(coordinates: Array) -> Vector3:
	return play_transform * MapCatalog.vector(coordinates)

func flag_base(team: int) -> Dictionary:
	var mount: Node3D
	var trigger: Area3D
	var home := world_point(config.flag_bases[team])
	if config.has("flag_markers"):
		var id: String = config.flag_markers[team]
		mount = Assets.socket(model, "Gizmo_" + id.replace("-", "_"))
		assert(mount != null, "Missing flag base gizmo: " + id)
		for marker in markers:
			if marker.name == id: home = world_point(marker.position_godot)
		trigger = CollisionRig.install_trigger(model, "maps", config.model, config.flag_capture_meshes[team])
	else:
		# Older maps retain their catalog bases until they author capture meshes.
		mount = Marker3D.new()
		mount.name = "FlagBase%d" % team
		model.add_child(mount)
		mount.position = MapCatalog.vector(config.flag_bases[team])
		trigger = Area3D.new()
		trigger.name = "FlagCaptureTrigger%d" % team
		trigger.collision_layer = 0
		trigger.collision_mask = 2
		mount.add_child(trigger)
		var collision := CollisionShape3D.new()
		var cylinder := CylinderShape3D.new()
		cylinder.radius = 1.0
		cylinder.height = 0.1
		cylinder.margin = 0.001
		collision.shape = cylinder
		collision.position.y = 0.05
		trigger.add_child(collision)
	var effect := FlagBaseEffect.new()
	effect.name = "FlagBaseEffect%d" % team
	mount.add_child(effect)
	effect.configure(game.team_colors[team], game.reduced_motion)
	effect.hide()
	return {"home": home, "trigger": trigger, "effect": effect}

func make_fixture(marker: Dictionary):
	var role: String = marker.role
	if role in ["flag_base","jumbotron"]: return
	var id: String = marker.name
	if fixture_by_id(id) != null: return
	var socket_name: String = config.get("fixture_mounts", {}).get(id, "Gizmo_" + id.replace("-","_"))
	var mount := Assets.socket(model,socket_name)
	if marker.has("parent_fixture"):
		var parent_fixture=fixture_by_id(marker.parent_fixture)
		assert(parent_fixture!=null,"Native placement parent must be imported first")
		mount=Assets.socket(parent_fixture.node,marker.parent_socket)
		assert(mount!=null,"Missing native prop placement socket: "+String(marker.parent_socket))
	if mount == null:
		if role.begins_with("ammo_"):
			for side in ["_L","_R"]:
				var pair := Assets.socket(model,socket_name + side)
				if pair: pickup_fixture(marker,pair,"ammo",weapon_id(role.trim_prefix("ammo_")))
		return
	var point := world_point(marker.position_godot)
	if role in ["weapon","energy","shield","ammo"]:
		pickup_fixture(marker,mount,role,marker.get("weapon", "") if marker.get("weapon") != null else "")
		return
	if role in ["prop","pulse_gun","platform"]:
		var suffix: String = marker.get("asset_suffix","")
		var instance := Assets.model(marker.category,marker.asset,suffix)
		mount.add_child(instance)
		instance.transform = Transform3D.IDENTITY
		finish_lunar_surface(instance)
		if not marker.get("no_collision",false): CollisionRig.install(instance,marker.category,marker.asset,null,suffix+"_col")
		ArchitectureLights.install(instance,marker.category,marker.asset,suffix)
		var placement := {"id":id,"kind":role,"point":point,"node":instance,"cooldown":0.0,"elapsed":0.0,"occupant":null,"inside":[],"open":true,"trigger":null}
		fixtures.append(placement)
		placement["asset_suffix"]=suffix
		placement["budget_excluded"]=marker.get("budget_excluded",false)
		if role == "pulse_gun":
			var controller := PulseGunController.new()
			controller.install(instance,game,int(marker.team))
			placement["controller"] = controller
		elif marker.category == "architecture" or marker.get("source_category","")=="architecture": open_architecture(instance,marker.get("open_actions",[]))
		if marker.get("source_category","")=="architecture":
			var native_meta: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/%s/%s%s_rig.json"%[config.model,config.model,suffix]))
			if native_meta.has("cargo_lift_m"):
				var lift:=ArchitectureLift.new();lift.install(game,placement,native_meta);placement["lift_controller"]=lift
		return
	if role.begins_with("weapon_") and role != "weapon_wall":
		pickup_fixture(marker,mount,"weapon",weapon_id(role.trim_prefix("weapon_")))
		return
	if role.begins_with("core_"):
		pickup_fixture(marker,mount,role.trim_prefix("core_"),"")
		return
	var asset: String = marker.get("asset", {"spawn":"spawn_point","portal":"portal_gate"}.get(role,role))
	if asset not in ["spawn_point","stasis_chamber","portal_gate","jump_pad","speed_ramp","pressure_plate","barricade","repair_station","thruster","pillar"]: return
	var category: String = marker.get("category", "environments" if asset in ["thruster","pillar"] else "gameplay")
	var prop := Assets.model(category,asset)
	mount.add_child(prop)
	finish_lunar_surface(prop)
	var fixture := {"id":id,"kind":role,"point":point,"node":prop,"cooldown":0.0,"elapsed":0.0,"occupant":null,"inside":[],"open":true,"trigger":null}
	fixtures.append(fixture)
	if role == "jump_pad":
		var pulse := JumpPadEnergyPulse.new()
		prop.add_child(pulse)
		pulse.set_reduced_motion(game.reduced_motion)
		fixture["energy_pulse"] = pulse
	if role != "thruster": CollisionRig.install(prop,category,asset)
	if role == "pressure_plate":
		fixture.trigger = CollisionRig.install_trigger(prop,category,asset,"SK_PressurePlateTrigger")
	elif role == "speed_ramp":
		fixture.trigger = CollisionRig.install_trigger(prop,category,asset,"SK_SpeedRampTrigger")
		fixture["launch_mount"] = Assets.socket(prop,"LaunchOrigin")
		var ramp_meta: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/gameplay/speed_ramp/speed_ramp_rig.json"))
		var axis: Array=ramp_meta.authoring_belt.axis
		fixture["launch_axis"]=Vector3(axis[0],axis[2],-axis[1])
		var arrows:=SpeedRampEnergyArrows.new()
		arrows.configure(ramp_meta,game.reduced_motion)
		prop.add_child(arrows)
		fixture["energy_arrows"]=arrows
		fixture["motion"] = motion_for(prop)
		fixture.motion.play("convey",true)
	elif role == "repair_station":
		fixture.trigger = CollisionRig.install_trigger(prop,category,asset,"SK_RepairStationPadTrigger")
		fixture["geometry_valid"] = true
		fixture["geometry_colliders"] = prop.find_children("*", "StaticBody3D", true, false)
		fixture["exit_required"] = []
		prop.tree_exiting.connect(set_repair_geometry_valid.bind(fixture, false))
		fixture.trigger.tree_exiting.connect(set_repair_geometry_valid.bind(fixture, false))
		var status_label := Label3D.new()
		status_label.name = "RepairStatus"
		status_label.position = Vector3(0, 2.8, 0)
		status_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		status_label.font = HudSkin.DISPLAY_FONT
		status_label.font_size = 48
		status_label.pixel_size = 0.005
		status_label.outline_size = 12
		prop.add_child(status_label)
		fixture["status_label"] = status_label
		fixture["repair_lights"] = []
		fixture["barrier_meshes"] = []
		for mesh in prop.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var source := mesh.get_active_material(surface) as StandardMaterial3D
				if source != null and Assets.material_role(source.resource_name) == "M_Shield":
					var barrier := ShaderMaterial.new()
					barrier.shader = preload("res://shaders/shield.gdshader")
					barrier.set_shader_parameter("tint", Color("6fe5ea"))
					mesh.material_override = barrier
					mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
					mesh.hide()
					fixture.barrier_meshes.append(mesh)
				if source == null or Assets.material_role(source.resource_name) != "M_RepairStatus": continue
				var indicator := source.duplicate() as StandardMaterial3D
				mesh.set_surface_override_material(surface,indicator)
				fixture.repair_lights.append(indicator)
		update_repair_status(fixture)
		fixture["weld_fx"] = RepairWelding.new()
		fixture.weld_fx.install(game,fixture)
	match role:
		"spawn":
			var player_mount := Assets.socket(prop,"PlayerMount")
			assert(player_mount != null,"Spawn asset must export PlayerMount: " + asset)
			spawns.append({"id":id,"point":player_mount.global_position,"team":0 if id.begins_with("A") else 1,"node":prop,"mount":player_mount,
				"duration":1.5 if asset == "stasis_chamber" else 104.0/30.0,"reveal_after":0.6 if asset == "stasis_chamber" else 42.0/30.0,"action":"open" if asset == "stasis_chamber" else "deploy"})
			Assets.play(prop,"close")
			if asset=="stasis_chamber":
				fixture["stasis"]=true;fixture["open"]=false;fixture["close_pending"]=false
				var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/gameplay/stasis_chamber/stasis_chamber_rig.json"))
				var bounds: Dictionary=metadata.door_swept_bounds_m
				fixture["swept_bounds"]=AABB(Vector3(bounds.lo[0],bounds.lo[2],-bounds.hi[1]),Vector3(bounds.hi[0]-bounds.lo[0],bounds.hi[2]-bounds.lo[2],bounds.hi[1]-bounds.lo[1]))
				var animator:=Assets.find(prop,"AnimationPlayer") as AnimationPlayer
				animator.seek(animator.current_animation_length,true);animator.pause()
				fixture["motion"]=motion_for(prop);fixture.motion.play("close")
				var state: Dictionary=fixture.motion.channels.main
				state.time=state.player.get_animation("close").length;fixture.motion.sample(state);state.done=true
		"thruster":
			fixture["motion"] = motion_for(prop)
			fixture.motion.play("idle",true)
			var origin := Assets.socket(prop,"ExhaustOrigin")
			fixture["audio_mount"]=origin
			if origin:
				var plume := NozzleExhaust.new()
				plume.length_m = 5.5
				plume.radius_m = 0.75
				plume.tint = Color("ff7529")
				origin.add_child(plume)
				fixture["plume"] = plume
				for mesh in prop.find_children("*", "MeshInstance3D", true, false):
					if String(mesh.name).contains("ThrusterExhaust"):
						var mat := ShaderMaterial.new()
						mat.shader = OriginalEffect.THERMAL
						mat.set_shader_parameter("turbulence_texture",preload("res://assets/models/effects/combat_effects/turbulence_rgba.png"))
						mat.set_shader_parameter("secondary_color",plume.tint)
						mat.set_shader_parameter("emission",0.65)
						mesh.material_override = mat
		"portal":
			fixture["motion"] = motion_for(prop)
			fixture["usable"] = false
			fixture["inner_lights"] = []
			fixture["fields"] = []
			for mesh in prop.find_children("*","MeshInstance3D",true,false):
				for surface in mesh.mesh.get_surface_count():
					var source := mesh.get_active_material(surface) as StandardMaterial3D
					if source != null and Assets.material_role(source.resource_name) == "M_PortalStatus":
						var indicator := source.duplicate() as StandardMaterial3D
						mesh.set_surface_override_material(surface,indicator)
						fixture.inner_lights.append(indicator)
				if String(mesh.name).contains("Field"):
					var glow := PortalVfx.install(mesh)
					fixture.fields.append(mesh)
					fixture.fields.append(glow)
			fixture.motion.finished.connect(portal_animation_finished.bind(fixture))
			fixture.motion.play("activate",false,"active",true)
			update_portal_status(fixture)
		"pillar":
			Assets.play(prop,"open")
			var player := Assets.find(prop,"AnimationPlayer") as AnimationPlayer
			player.seek(float(marker.get("support_open_time_s",1.5)),true)
			player.pause()
			ArchitectureLights.share_fixed_pose_meshes(prop)
		"barricade": Assets.play(prop,"lower")

func open_architecture(instance: Node3D, selected: Array = []) -> void:
	var player := Assets.find(instance,"AnimationPlayer") as AnimationPlayer
	if player == null: return
	var opened := Animation.new()
	opened.length = 0.05
	var paths := {}
	for key in player.get_animation_list():
		var action := String(key).get_slice("/",String(key).count("/"))
		if not (action == "open" or action.ends_with("_open") or action.begins_with("open_")): continue
		if not selected.is_empty() and action not in selected: continue
		var clip := player.get_animation(key)
		for track in clip.get_track_count():
			var path := clip.track_get_path(track)
			if clip.track_get_key_count(track) == 0: continue
			var channel := String(path)+"/"+str(clip.track_get_type(track))
			var value = clip.track_get_key_value(track,clip.track_get_key_count(track)-1)
			var active: bool = value != clip.track_get_key_value(track,0)
			if paths.has(channel):
				if active:
					opened.track_set_key_value(int(paths[channel]),0,value)
				continue
			clip.copy_track(track,opened)
			var index := opened.get_track_count()-1
			paths[channel] = index
			while opened.track_get_key_count(index)>0: opened.track_remove_key(index,0)
			opened.track_insert_key(index,0,value)
	var library := AnimationLibrary.new()
	library.add_animation("open_all",opened)
	player.add_animation_library("map",library)
	player.play("map/open_all")
	player.seek(0,true)
	player.pause()

func weapon_id(id: String) -> String:
	return {"lightning":"lightning_gun","emp":"emp_gun","rocket":"rocket_launcher"}.get(id,id)

func pickup_fixture(marker: Dictionary, mount: Node3D, kind: String, weapon: String):
	if fixture_by_id(marker.name + String(mount.name)) != null: return
	var prop: Node3D
	var payload: Node3D
	var trigger: Area3D
	if kind == "ammo":
		prop = Node3D.new()
		mount.add_child(prop)
		payload = Assets.model("weapons",weapon,"_ammo")
		prop.add_child(payload)
		trigger = CollisionRig.install_pickup_area(payload,"weapons",weapon)
	else:
		var asset: String = marker.get("asset", "weapon_holder" if kind == "weapon" else "item_table")
		prop = Assets.model("gameplay",asset)
		mount.add_child(prop)
		CollisionRig.install(prop,"gameplay",asset)
		var socket := Assets.socket(prop,"WeaponMount" if kind == "weapon" and asset == "weapon_holder" else "ItemMount")
		assert(socket != null,"Missing authored payload gizmo: "+asset)
		if kind == "weapon":
			payload = Assets.model("weapons",weapon)
			socket.add_child(payload)
			CollisionRig.install(payload,"weapons",weapon)
			var ammo := Assets.socket(payload,"AmmoMount")
			if ammo: ammo.add_child(Assets.model("weapons",weapon,"_ammo"))
		else:
			payload = CoreOrb.new(kind)
			socket.add_child(payload)
	var point := world_point(marker.get("pickup_position_godot",marker.position_godot))
	var fixture := {"id":marker.name + String(mount.name),"kind":kind,"weapon":weapon,"node":prop,"payload":payload,"point":point,"cooldown":0.0,"elapsed":0.0,"occupant":null,"inside":[],"ready":kind == "ammo","status_materials":[],"trigger":trigger}
	fixtures.append(fixture)
	fixture["deploy_action"] = "close" if marker.get("asset", "") == "item_cradle" else "deploy"
	fixture["payload_colliders"]=payload.find_children("*","StaticBody3D",true,false)
	if marker.get("asset", "")=="item_cradle":
		fixture["claw_colliders"]=prop.find_children("SK_ItemCradleClaw*","StaticBody3D",true,false)
		assert(fixture.claw_colliders.size()==4,"Item cradle requires four separately named claw colliders")
		set_pickup_collision(fixture,false)
	if kind != "ammo":
		fixture["status_slots"] = []
		for mesh in prop.find_children("*", "MeshInstance3D", true, false):
			for surface in mesh.mesh.get_surface_count():
				var source := mesh.get_active_material(surface) as StandardMaterial3D
				if source == null or Assets.material_role(source.resource_name) != "M_Emissive": continue
				var slot := PickupIndicator.new()
				slot.mesh = mesh
				slot.surface = surface
				slot.styles = pickup_status_pair(source)
				mesh.set_surface_override_material(surface,slot.styles.recharging)
				fixture.status_materials.append(slot.styles.recharging)
				fixture.status_slots.append(slot)
	if kind != "ammo":
		fixture["motion"] = motion_for(prop)
		if kind == "weapon" and marker.get("asset", "weapon_holder") == "weapon_holder":
			fixture.motion.fit_weapon_grip(PropMotion.weapon_grip_width(payload))
		fixture.motion.finished.connect(pickup_animation_finished.bind(fixture))
		if fixture.deploy_action=="close":
			fixture.motion.play("close",false,"",false,"main",fixture.motion.channels.main.player.get_animation("close").length)
		else:fixture.motion.play(fixture.deploy_action)
		if payload is CoreOrb: motion_for(payload.visual).play("spin",true)
	var label := Label3D.new()
	prop.add_child(label)
	label.text = Arsenal.WEAPONS[weapon].title if kind == "weapon" else weapon.replace("_"," ") + " ammo" if kind == "ammo" else kind.capitalize() + " Core"
	label.position.y = 1.6
	label.font_size = 24
	label.pixel_size = 0.0035
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color("c7e1e8")
	label.no_depth_test = false
	label.visibility_range_end = 12.0
	label.visibility_range_end_margin = 3.0
	label.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	label.outline_size = 5
	pickup_labels.append({"label":label,"fixture":fixture})

func pickup_animation_finished(clip: StringName, fixture: Dictionary):
	var name := String(clip)
	var deployed: String = fixture.get("deploy_action", "deploy")
	if (name == deployed or name.ends_with("/"+deployed) or name.ends_with("|"+deployed)) and fixture.cooldown == 0:
		fixture.ready = true
		fixture.payload.show()
		set_pickup_collision(fixture,true)
		if deployed == "deploy": fixture.motion.play("spin", true)

func set_pickup_collision(fixture: Dictionary, enabled: bool) -> void:
	if fixture.get("pickup_collision_enabled")==enabled: return
	fixture["pickup_collision_enabled"]=enabled
	# Hiding a weapon's mesh does not disable its physical bodies.
	for body: StaticBody3D in fixture.get("claw_colliders",[])+fixture.get("payload_colliders",[]):
		body.set_deferred("collision_layer",1 if enabled else 0)

func portal_animation_finished(clip: StringName, fixture: Dictionary) -> void:
	if clip == "activate" and not shutting_down:
		fixture.usable = true
		update_portal_status(fixture)

func update_portal_status(fixture: Dictionary) -> void:
	var other = portal_peer(fixture.id)
	var available: bool = fixture.usable and game.phase == "Active" and other != null and other.get("usable",false)
	if fixture.has("portal_status_available") and fixture.portal_status_available == available: return
	fixture["portal_status_available"] = available
	var color := Color("60ef98") if available else Color("ff514e")
	for indicator in fixture.inner_lights:
		indicator.albedo_color = color.darkened(0.6)
		indicator.emission_enabled = true
		indicator.emission = color
		indicator.emission_energy_multiplier = 6.0
	for field in fixture.fields: field.visible = available

func update_repair_status(fixture: Dictionary) -> void:
	if not fixture.has("repair_lights"): return
	var available: bool = game.phase == "Active" and not shutting_down and fixture.get("geometry_valid", true) and fixture.occupant == null and fixture.cooldown <= 0.0
	var color := Color("60ef98") if available else Color("ff514e")
	if not fixture.has("repair_status_available") or fixture.repair_status_available != available:
		fixture["repair_status_available"] = available
		for indicator in fixture.repair_lights:
			indicator.albedo_color = color.darkened(0.6)
			indicator.emission_enabled = true
			indicator.emission = color
			indicator.emission_energy_multiplier = 6.0
	for mesh in fixture.get("barrier_meshes", []):
		if is_instance_valid(mesh): mesh.visible = repair_feedback(fixture).barrier
	if is_instance_valid(fixture.get("status_label")):
		var state := repair_feedback(fixture)
		fixture.status_label.text = "REPAIR STATION / " + state.label.to_upper()
		if state.seconds > 0: fixture.status_label.text += "\n%.1f s" % state.seconds
		fixture.status_label.modulate = Color("8bdead") if state.state == "ready" else Color("ffc36a")

func repair_feedback(f: Dictionary) -> Dictionary:
	var state := "unavailable"
	var label := "Unavailable"
	var seconds := 0.0
	var barrier := false
	if game.phase == "Active" and not shutting_down and f.get("geometry_valid", true):
		if is_instance_valid(f.occupant):
			if f.elapsed < 1.0:
				state = "activating"
				label = "Shield Activating"
				seconds = 1.0 - f.elapsed
			elif f.elapsed < 6.0:
				state = "welding"
				label = "Repairing"
				seconds = 6.0 - f.elapsed
				barrier = true
			else:
				state = "deactivating"
				label = "Shield Deactivating"
				seconds = maxf(0.0, 7.0 - f.elapsed)
				barrier = true
		elif f.cooldown > 0:
			state = "recharging"
			label = "Recharging"
			seconds = f.cooldown
		else:
			state = "ready"
			label = "Ready"
	return {"state": state, "label": label, "seconds": seconds, "barrier": barrier}

func update_repair_audio(f: Dictionary) -> void:
	if not is_instance_valid(game.audio): return
	var state: String = repair_feedback(f).state
	game.audio.set_loop("repair_ready_" + f.id, "repair_ready", f.point, state == "ready")
	var tip := Assets.socket(f.node, "TorchTip") if is_instance_valid(f.get("node")) else null
	game.audio.set_loop("welding_" + f.id, "repair_weld", tip.global_position if tip != null and tip.is_inside_tree() else f.point, state == "welding")

func _process(dt):
	pickup_status_time += dt
	RenderingServer.global_shader_parameter_set("arena_sky_time", fmod(pickup_status_time, 3600.0))
	var viewer: Vector3 = game.camera.global_position if game.camera != null else Vector3.ZERO
	for motion in machinery:
		motion.set_budget(game.reduced_motion,motion.asset.global_position.distance_to(viewer))
	for entry in pickup_labels:
		var label: Label3D = entry.label
		var fixture: Dictionary = entry.fixture
		var distance: float=label.global_position.distance_to(viewer)
		label.visible=game.local_robot != null and distance<5.0 and can_collect(fixture,game.local_robot)
	for fixture in fixtures:
		if fixture.kind == "portal":
			update_portal_status(fixture)
			PortalVfx.set_reduced_motion(fixture.fields, game.reduced_motion)
		if fixture.has("plume"): fixture.plume.set_budget(game.reduced_motion,fixture.node.global_position.distance_to(viewer))
		if fixture.has("energy_pulse"): fixture.energy_pulse.set_reduced_motion(game.reduced_motion)
		if fixture.has("energy_arrows"): fixture.energy_arrows.set_reduced_motion(game.reduced_motion)
		if fixture.has("status_materials"): update_pickup_status(fixture, pickup_status_time)
		if fixture.kind=="thruster" and fixture.get("audio_mount")!=null:
			game.audio.set_loop("thruster_"+fixture.id,"thruster_bed",fixture.audio_mount.global_position,game.phase=="Active")
		elif fixture.kind=="repair_station":
			update_repair_status(fixture)
			update_repair_audio(fixture)
			if is_instance_valid(fixture.get("status_label")):
				fixture.status_label.visible = game.phase == "Active" and fixture.node.global_position.distance_to(viewer) < 12.0

func pickup_status_pair(source: StandardMaterial3D) -> PickupStatusPair:
	var id := source.get_instance_id()
	if pickup_status_styles.has(id): return pickup_status_styles[id]
	var pair := PickupStatusPair.new()
	pair.ready = source.duplicate()
	pair.recharging = source.duplicate()
	for material in [pair.ready,pair.recharging]:
		var color := Color("60ef98") if material == pair.ready else Color("ff514e")
		material.albedo_color = color.darkened(0.6)
		material.emission = color
		material.emission_enabled = true
	pair.ready.emission_energy_multiplier = 4.0
	pickup_status_styles[id] = pair
	return pair

func update_pickup_status(fixture: Dictionary, time: float) -> void:
	var ready: bool = fixture.ready and fixture.cooldown <= 0.0 and fixture.payload.visible
	var changed: bool = not fixture.has("pickup_status_ready") or fixture.pickup_status_ready != ready
	fixture["pickup_status_ready"] = ready
	if fixture.has("status_slots"):
		var slots: Array = fixture.status_slots
		for index in slots.size():
			var slot: PickupIndicator = slots[index]
			var styles := slot.styles
			if changed:
				var material := styles.ready if ready else styles.recharging
				if is_instance_valid(slot.mesh): slot.mesh.set_surface_override_material(slot.surface,material)
				fixture.status_materials[index] = material
			if not ready and styles.updated_time != time:
				styles.recharging.emission_energy_multiplier = 1.3 + 3.2 * (0.5 + 0.5 * sin(time * TAU * 2.0))
				styles.updated_time = time
		return
	var color := Color("60ef98") if ready else Color("ff514e")
	var energy := 4.0 if ready else 1.3 + 3.2 * (0.5 + 0.5 * sin(time * TAU * 2.0))
	for indicator in fixture.status_materials:
		if changed:
			indicator.albedo_color = color.darkened(0.6)
			indicator.emission = color
			indicator.emission_enabled = true
		if changed or not ready: indicator.emission_energy_multiplier = energy

func add_world():
	ArenaLighting.install(self)

func finish_lunar_surface(root: Node) -> void:
	for mesh in root.find_children("*", "MeshInstance3D", true, false):
		for surface in mesh.mesh.get_surface_count():
			var source := mesh.get_active_material(surface) as StandardMaterial3D
			if source == null or Assets.material_role(source.resource_name) not in ["M_Regolith", "M_RegolithLight", "M_RegolithDark"]: continue
			mesh.set_surface_override_material(surface, Assets.regolith_material(source))

func begin_spawn(spawn: Dictionary,robot: ArenaRobot) -> void:
	var fixture=fixture_by_id(spawn.id)
	if fixture!=null and fixture.get("stasis",false):
		fixture.occupant=robot;fixture.open=true;fixture.close_pending=true
		fixture.motion.play("open")
	else:Assets.play(spawn.node,spawn.get("action","deploy"))

func tick_stasis():
	for fixture in fixtures:
		if not fixture.get("stasis",false) or not fixture.close_pending:continue
		var waiting=false
		for robot in game.robots:
			if not is_instance_valid(robot) or not robot.alive:continue
			if robot.spawn_remaining>0 and robot.spawn_fixture.get("id","")==fixture.id:waiting=true;break
			var local: Vector3=fixture.node.to_local(robot.global_position)
			var capsule: CapsuleShape3D=robot.body_capsule
			var radius: float=capsule.radius+.02
			var body_box:=AABB(local-Vector3(radius,0,radius),Vector3(radius*2,capsule.height,radius*2))
			if fixture.swept_bounds.intersects(body_box):waiting=true;break
		if waiting:continue
		fixture.close_pending=false;fixture.open=false;fixture.occupant=null
		fixture.motion.play("close")

func tick(dt: float):
	var started := Time.get_ticks_usec() if profile_ticks else 0
	tick_stasis()
	if profile_ticks: started = profile_stage("stasis",started)
	for label in screen_labels:
		label.text = "KYLR / " + config.title.to_upper() + "\n" + game.match_type + "   " + game.score_text() + "\n" + game.clock_text()
	if profile_ticks: started = profile_stage("labels",started)
	if game.phase != "Active":
		abort_all_repairs("match_inactive")
		return
	for f in fixtures:
		if f.cooldown > 0:
			f.cooldown = maxf(0,f.cooldown-dt)
			if f.cooldown == 0 and f.kind == "repair_station": update_repair_status(f)
			if f.cooldown == 0 and f.has("payload"):
				f.ready = f.kind == "ammo"
				if f.get("deploy_action", "deploy")!="close":f.payload.show()
				if f.has("motion"): f.motion.play(f.get("deploy_action", "deploy"))
		if f.kind == "repair_station":
			if not repair_geometry_valid(f): set_repair_geometry_valid(f,false)
			for id in f.get("exit_required", []).duplicate():
				var previous_occupant = game.robot_by_id(id)
				if previous_occupant == null or not repair_contains(f, previous_occupant): f.exit_required.erase(id)
			tick_repair(f,dt)
		if f.kind == "barricade" and f.open:
			f.elapsed += dt
			if f.elapsed >= 30 and not occupied(f.point,2.3): set_barricade(f,false)
		# Static architecture cannot interact with robots. Avoid hundreds of
		# pointless proximity scans while retaining machinery and cooldown work.
		if not f.has("payload") and f.kind not in INTERACTION_KINDS: continue
		var inside: Array = []
		var candidates: Array = game.robots
		if f.get("trigger") != null:
			candidates = f.trigger.get_overlapping_bodies()
			if not candidates.is_empty():
				candidates = candidates.filter(func(body): return body in game.robots)
				# Keep simultaneous pickup arbitration in the same roster order.
				if candidates.size() > 1:
					candidates.sort_custom(func(a,b): return game.robots.find(a)<game.robots.find(b))
		for r in candidates:
			if not r.can_act(): continue
			if f.get("trigger") == null:
				var offset: Vector3 = r.position - f.point
				if absf(offset.y) > 1.0 or Vector2(offset.x,offset.z).length() > 0.9: continue
			inside.append(r.robot_id)
			if f.cooldown > 0: continue
			if f.has("payload"): collect(f,r)
			elif f.kind == "portal" and f.usable and r.portal_lock <= 0: teleport(f,r)
			elif f.kind == "jump_pad":
				r.begin_powered_jump(game.jump_release_height(ArenaTuning.JUMP_PAD_HEIGHT), ArenaTuning.JUMP_PAD_SPEED, true)
				f.cooldown = 0.6
				Assets.play(f.node,"launch")
				game.audio.cue("jump_pad_launch",f.point)
			elif f.kind == "speed_ramp" and r.robot_id not in f.inside and r.ramp_stage == 0:
				var link := speed_ramp_link(f.id)
				if not link.is_empty():
					r.begin_speed_ramp(f.launch_mount.global_position,speed_ramp_velocity(f,float(link.speed)))
					f.motion.play("launch",false,"convey",true)
			elif f.kind == "pressure_plate" and r.robot_id not in f.inside:
				if f.inside.is_empty(): Assets.play(f.node,"press")
				var barricade = fixture_by_id(config.get("barricade_links", {}).get(f.id, f.id.replace("plate","barricade")))
				if barricade != null and (not barricade.open or not occupied(barricade.point,2.3)): set_barricade(barricade,not barricade.open)
			elif f.kind == "repair_station": start_repair(f,r)
		if f.kind == "pressure_plate" and inside.is_empty() and not f.inside.is_empty(): Assets.play(f.node,"release")
		f.inside = inside
	if profile_ticks: started = profile_stage("fixtures",started)
	if config.event.get("type","") == "none": return
	if game.elapsed >= config.event.time-config.event.warning and not event_warned:
		event_warned = true
		game.notice("ARENA / " + config.event.title + " in %d seconds" % config.event.warning)
	if game.elapsed >= config.event.time and not event_done:
		event_done = true
		for f in fixtures:
			if f.kind == "barricade" and not occupied(f.point,2.3): set_barricade(f,false)
		game.notice("ARENA / Cover banks reconfigured")

func speed_ramp_link(id: String) -> Dictionary:
	for link in config.get("speed_ramp_links",[]):
		if link.fixture == id:return link
	return {}

func lift_near(point: Vector3):
	var nearest=null;var distance:=4.0
	for fixture in fixtures:
		if not fixture.has("lift_controller"):continue
		var surface: Vector3=fixture.lift_controller.surface.global_position
		var horizontal:=Vector2(surface.x-point.x,surface.z-point.z).length()
		if horizontal<distance:nearest=fixture;distance=horizontal
	return nearest

func speed_ramp_velocity(f: Dictionary,speed: float) -> Vector3:
	var axis: Vector3 = f.node.global_basis * f.launch_axis
	return axis.normalized()*speed*sqrt(game.gravity_multiplier)

func can_collect(f: Dictionary,r) -> bool:
	if not r.can_act() or f.cooldown > 0 or not f.ready or not f.payload.visible: return false
	match f.kind:
		"energy": return r.ep <= ArenaTuning.ENERGY_CORE_ELIGIBLE_EP
		"shield": return r.sh <= 99
		"weapon": return r.can_pickup_weapon(f.weapon)
		"ammo": return r.can_pickup_ammo(f.weapon)
	return false

func collect(f: Dictionary,r):
	if not can_collect(f,r): return
	match f.kind:
		"energy": r.ep = ArenaTuning.MAX_EP
		"shield": r.sh = 100; r.shield_time = 60
		"weapon": r.take_weapon(f.weapon)
		"ammo": r.pickup_ammo(f.weapon)
	f.cooldown = 60
	f.ready = false
	f.payload.hide()
	set_pickup_collision(f,false)
	if f.has("motion"): f.motion.at_boundary("open" if f.get("deploy_action", "deploy") == "close" else "retract")
	game.audio.cue("pickup_" + (f.kind if f.kind in ["weapon", "ammo"] else "item"),r.position,r == game.local_robot or game.online,r)
	if r == game.local_robot or game.online:
		game.notice(pickup_notice(f),r)

static func pickup_notice(f: Dictionary) -> String:
	if f.kind in ["weapon", "ammo"] and Arsenal.WEAPONS.has(f.weapon):
		return Arsenal.WEAPONS[f.weapon].title + (" ammo acquired" if f.kind == "ammo" else " acquired")
	return f.kind.capitalize() + " Core acquired"

func tick_repair(f: Dictionary,dt: float):
	if f.occupant == null and not f.get("repair_active", false): return
	var r = f.occupant
	if game.phase != "Active" or shutting_down or not is_instance_valid(r) or not r.alive or r not in game.robots or not repair_geometry_valid(f) or not repair_contains(f,r):
		abort_repair(f,"interrupted")
		return
	var previous: float = f.elapsed
	f.elapsed += dt
	if previous < 1 and f.elapsed >= 1:
		Assets.play(f.node,"repair",true)
	if previous < 6 and f.elapsed >= 6:
		r.ah = 100
		r.ep = ArenaTuning.MAX_EP
		Assets.play(f.node,"deactivate")
		game.audio.cue("repair_start_stop",f.point)
	if f.elapsed >= 7:
		release_repair(f)
		if r == game.local_robot or game.online: game.notice("Repair complete / Exit station",r)
	update_repair_status(f)
	update_repair_audio(f)

func repair_contains(f: Dictionary, r) -> bool:
	if not is_instance_valid(r): return false
	if is_instance_valid(f.get("trigger")): return f.trigger.overlaps_body(r)
	var offset: Vector3 = r.global_position - f.point
	return absf(offset.y) <= 1.0 and Vector2(offset.x, offset.z).length() <= 0.9

func repair_geometry_valid(f: Dictionary) -> bool:
	if not f.get("geometry_valid", true): return false
	var node = f.get("node")
	if not is_instance_valid(node) or node.is_queued_for_deletion() or not node.is_inside_tree() or not node.is_visible_in_tree(): return false
	var trigger = f.get("trigger")
	if not is_instance_valid(trigger) or trigger.is_queued_for_deletion() or not trigger.monitoring or trigger.collision_mask & 2 == 0: return false
	var shape_enabled := false
	for shape in trigger.get_children():
		if shape is CollisionShape3D and not shape.disabled and shape.shape != null: shape_enabled = true
	if not shape_enabled: return false
	for collider in f.get("geometry_colliders", []):
		if not is_instance_valid(collider) or collider.is_queued_for_deletion() or collider.collision_layer & 1 == 0: return false
		for shape in collider.get_children():
			if shape is CollisionShape3D and (shape.disabled or shape.shape == null): return false
	# Capture the assembled transform, never the moving opening pose.
	if not f.has("geometry_transform"): f["geometry_transform"] = node.global_transform
	return node.global_transform.is_equal_approx(f.geometry_transform)

func set_repair_geometry_valid(f: Dictionary, valid: bool) -> void:
	f["geometry_valid"] = valid
	if valid: f.erase("geometry_transform")
	else: abort_repair(f,"geometry_invalid")
	update_repair_status(f)
	update_repair_audio(f)

func start_repair(f: Dictionary, r) -> bool:
	if not r.can_act() or f.occupant != null or f.cooldown > 0 or r.ah > 50 or r.robot_id in f.get("exit_required", []) or not repair_geometry_valid(f) or not repair_contains(f,r): return false
	if Vector2(r.velocity.x,r.velocity.z).length() >= 0.2: return false
	f.occupant = r
	f["repair_active"] = true
	f.elapsed = 0.0
	r.repair = f
	r.reload_time = 0.0
	r.streaming = false
	game.combat.stop_contact(r)
	game.audio.set_loop("weapon_" + str(r.robot_id), r.equipped, r.muzzle(), false)
	var mount := Assets.socket(f.node,"PlayerMount")
	r.global_position = mount.global_position if mount != null else f.point
	if mount != null:
		var forward: Vector3 = -mount.global_basis.z.normalized()
		r.yaw = atan2(-forward.x,-forward.z)
		r.body.rotation.y = r.yaw + r.character.forward_yaw
	r.animation_lock = 0.0
	r.crouched = false
	r.body_capsule.height = 1.72
	r.body_shape.position.y = 0.86
	r.pose("common/idle")
	Assets.play(f.node,"activate")
	update_repair_status(f)
	update_repair_audio(f)
	game.audio.cue("repair_start_stop",f.point)
	return true

func release_repair(f: Dictionary) -> void:
	var r = f.occupant
	if is_instance_valid(r):
		if r.repair == f: r.repair = null
		if r.alive and r.animator != null and game.phase == "Active" and not shutting_down:
			r.pose("idle")
		if not f.has("exit_required"): f["exit_required"] = []
		if r.robot_id not in f.exit_required: f.exit_required.append(r.robot_id)
	f.occupant = null
	f["repair_active"] = false
	f.elapsed = 0.0
	f.cooldown = 60.0 if game.phase == "Active" and not shutting_down else 0.0
	if is_instance_valid(f.get("weld_fx")): f.weld_fx.stop()
	update_repair_status(f)
	update_repair_audio(f)

func abort_repair(f: Dictionary, reason: String) -> void:
	if f.occupant == null and not f.get("repair_active", false): return
	if f.elapsed < 6.0 and is_instance_valid(game.audio): game.audio.cue("repair_start_stop",f.point)
	f["last_interruption"] = reason
	release_repair(f)
	if is_instance_valid(f.get("node")) and not f.node.is_queued_for_deletion():
		# Collapse the barrier immediately; do not leave a one-second ghost shield.
		Assets.play(f.node,"deactivate")
		var player := Assets.find(f.node,"AnimationPlayer") as AnimationPlayer
		if player != null:
			player.seek(player.current_animation_length,true)
			player.pause()
		var skeleton := Assets.find(f.node,"Skeleton3D") as Skeleton3D
		if skeleton != null: skeleton.force_update_all_bone_transforms()

func abort_repair_for_robot(r, reason: String) -> void:
	for f in fixtures:
		if f.kind == "repair_station" and f.occupant == r: abort_repair(f,reason)

func abort_all_repairs(reason: String) -> void:
	for f in fixtures:
		if f.kind == "repair_station":
			abort_repair(f,reason)
			update_repair_audio(f)

func repair_hint(r) -> String:
	if not is_instance_valid(r) or not r.can_act(): return ""
	for f in fixtures:
		if f.kind != "repair_station" or r.global_position.distance_to(f.point) > 5.0: continue
		var state := repair_feedback(f)
		if state.state == "recharging": return "REPAIR STATION / RECHARGING %.0fs" % ceilf(state.seconds)
		if state.state != "ready": return "REPAIR STATION / " + state.label.to_upper()
		if r.robot_id in f.get("exit_required", []): return "REPAIR STATION / EXIT BAY BEFORE REUSE"
		return "REPAIR AVAILABLE / STOP IN BAY" if r.ah <= 50 else "REPAIR STATION / REQUIRES 50 AH OR LESS"
	return ""

func reset_repairs() -> void:
	abort_all_repairs("new_match")
	for f in fixtures:
		if f.kind != "repair_station": continue
		f.cooldown = 0.0
		f.elapsed = 0.0
		f["exit_required"] = []
		update_repair_status(f)
		update_repair_audio(f)

func portal_peer(id: String):
	for pair in config.portal_pairs:
		if pair[0] == id: return fixture_by_id(pair[1])
		if pair[1] == id: return fixture_by_id(pair[0])
	return null

func portal_exits(other: Dictionary) -> Array[Vector3]:
	var points: Array[Vector3]=[]
	var normal: Vector3=other.node.global_basis.z.normalized()
	for lateral in [0.0,-1.0,1.0]:
		var point: Vector3=other.point+normal*1.5+other.node.global_basis.x.normalized()*lateral+Vector3.UP*.05
		if traversal==null or traversal.standing_clear(point):points.append(point)
	return points

func teleport(f: Dictionary,r):
	if not f.get("usable",false): return
	var other = portal_peer(f.id)
	if other == null or not other.get("usable",false): return
	var normal: Vector3 = other.node.global_basis.z.normalized()
	for exit in portal_exits(other):
		if not occupied(exit,0.7):
			game.audio.cue("portal_enter",r.position)
			var incoming: Vector3=f.node.global_basis.z.normalized()
			if r.velocity.dot(incoming)<0:incoming=-incoming
			incoming.y=0
			var outgoing:=Vector3(normal.x,0,normal.z).normalized()
			var turn:=incoming.normalized().signed_angle_to(outgoing,Vector3.UP)
			r.velocity=r.velocity.rotated(Vector3.UP,turn)
			r.knockback_velocity=r.knockback_velocity.rotated(Vector3.UP,turn)
			r.applied_knockback=r.applied_knockback.rotated(Vector3.UP,turn)
			r.position = exit
			r.yaw = atan2(-normal.x,-normal.z)
			r.portal_lock = 0.5
			game.audio.cue("portal_exit",exit)
			return

func occupied(point: Vector3,radius: float) -> bool:
	for r in game.robots:
		if r.alive and r.position.distance_to(point) < radius: return true
	return false

func set_barricade(f: Dictionary,open: bool):
	f.open = open
	f.elapsed = 0
	Assets.play(f.node,"lower" if open else "raise")
	if traversal != null:
		traversal.sync_barricades()
		for robot in game.robots:
			if robot.brain == null: continue
			# Keep committed air travel when an unrelated plate changes a route.
			# Replanning from midair can select a different floor under the robot.
			if not robot.is_on_floor() and robot.brain.transition_index>=0: continue
			robot.brain.path.clear()
			robot.brain.path_index = 0
			robot.brain.transition_index = -1
			robot.brain.transition_launched = false
			robot.brain.airborne_goal = Vector3.INF
			robot.brain.retarget = 0.0
	game.audio.cue("barricade_open" if open else "barricade_close",f.point)

func fixture_by_id(id: String) -> Variant:
	# Native fixture IDs are unique. Store positions, not copies of mutable state.
	# Validate hits so removal/reordering/replacement cannot return a stale fixture.
	var index: int = fixture_indices.get(id,-1)
	if index >= 0 and index < fixtures.size() and fixtures[index].id == id:
		return fixtures[index]
	for current in fixtures.size():
		if fixtures[current].id == id:
			fixture_indices[id] = current
			return fixtures[current]
	fixture_indices.erase(id)
	return null

func closest_ready(robot,kind: String):
	var best = null
	var distance := INF
	for f in fixtures:
		if f.kind != ("repair_station" if kind == "repair" else kind) or f.cooldown > 0 or f.occupant != null: continue
		var d: float = robot.position.distance_to(f.point)
		if d < distance: distance = d; best = f
	return best

func zone_exit(team: int,point: Vector3) -> Vector3:
	if config.has("zone_exits"):
		return world_point(config.zone_exits[team])
	return Vector3(7.5,0,-14 if team == 0 else 14) if point.y > -3 else Vector3(0,-7.25,-11 if point.z < 0 else 11)

func patrol_point(_id: int) -> Vector3:
	if config.has("patrol_points"):
		return world_point(config.patrol_points[game.rng.randi_range(0,config.patrol_points.size()-1)])
	return Vector3(7.5 if game.rng.randf() > 0.5 else -7.5,0,game.rng.randf_range(-27,27))

func build_navigation():
	if config.get("bake_navigation",false): bake_navigation()
	traversal=TraversalGraph.new(self)
	traversal.build()
	nav=traversal.graph
	if navigation_region:
		for edge in traversal.actions:
			if traversal.actions[edge]=="speed_ramp":
				navigation_link(nav.get_point_position(edge.x),traversal.destinations[edge],false,"speed_ramp")

func build_navigation_async() -> void:
	var key := "%s:%s:%s:%s:%s:%s"%[FileAccess.get_sha256(config.metadata),JSON.stringify(config),str(play_transform),game.gravity,ArenaTuning.NORMAL_JUMP_HEIGHT,ArenaTuning.CHARGED_JUMP_HEIGHT]
	navigation_cache_hit=false
	if navigation_snapshots.has(key):
		# Region RIDs and links belong to this live map, never to the snapshot.
		if config.get("bake_navigation",false): bake_navigation()
		traversal=TraversalGraph.new(self)
		traversal.restore_snapshot(navigation_snapshots[key])
		nav=traversal.graph
		if navigation_region:
			for edge in traversal.actions:
				if traversal.actions[edge]=="speed_ramp": navigation_link(nav.get_point_position(edge.x),traversal.destinations[edge],false,"speed_ramp")
		navigation_cache_hit=true
		return
	# Keep the sampled collision world stable across yields, without disabling
	# CollisionObject nodes (which would remove them from the physics space).
	var motions: Array[Node]=[]
	var players: Array[AnimationPlayer]=[]
	for motion: PropMotion in machinery:
		if motion.is_physics_processing():
			motions.append(motion)
			motion.set_physics_process(false)
	for player: AnimationPlayer in find_children("*","AnimationPlayer",true,false):
		if player.is_playing():
			players.append(player)
			player.pause()
	if config.get("bake_navigation",false): bake_navigation()
	traversal=TraversalGraph.new(self)
	await traversal.build_async()
	navigation_snapshots[key]=traversal.snapshot()
	nav=traversal.graph
	if navigation_region:
		for edge in traversal.actions:
			if traversal.actions[edge]=="speed_ramp": navigation_link(nav.get_point_position(edge.x),traversal.destinations[edge],false,"speed_ramp")
	for player in players: player.play()
	for motion in motions: motion.set_physics_process(true)

func bake_navigation():
	if navigation_region: navigation_region.free()
	navigation_region = NavigationRegion3D.new()
	add_child(navigation_region)
	var mesh := NavigationMesh.new()
	mesh.agent_radius = 0.5
	mesh.agent_height = 2.0
	mesh.agent_max_climb = 0.25
	mesh.agent_max_slope = 40
	mesh.cell_size = 0.25
	mesh.cell_height = 0.25
	var geometry := NavigationMeshSourceGeometryData3D.new()
	for collision in model.find_children("*","CollisionShape3D",true,false):
		if collision.get_parent().get_meta("lethal_surface",false):continue
		if collision.shape is ConcavePolygonShape3D:
			geometry.add_faces(collision.shape.get_faces(),collision.global_transform)
		elif collision.shape is BoxShape3D:
			var box := BoxMesh.new()
			box.size = collision.shape.size
			geometry.add_mesh(box,collision.global_transform)
	NavigationServer3D.bake_from_source_geometry_data(mesh,geometry)
	navigation_region.navigation_mesh = mesh
	# Launch machinery can leave its contact point inside a baked floor hole.
	# Connect off-mesh actions to the nearby safe approach polygons.
	NavigationServer3D.map_set_link_connection_radius(navigation_region.get_navigation_map(),2.0)
	assert(mesh.get_polygon_count()>0,"Authored map collision must bake a walkable navmesh")
	for pair in config.portal_pairs:
		var a = fixture_by_id(pair[0])
		var b = fixture_by_id(pair[1])
		if a and b: navigation_link(a.point,b.point,true,"portal")
	for route in config.jump_links: navigation_link(world_point(route.from),world_point(route.to),false,"launch")
	for route in config.drop_links: navigation_link(world_point(route.from),world_point(route.to),false,"drop")

func navigation_link(from: Vector3,to: Vector3,both: bool,kind: String):
	var connection := NavigationLink3D.new()
	connection.bidirectional = both
	connection.start_position = from
	connection.end_position = to
	connection.set_meta("traversal_action",kind)
	navigation_region.add_child(connection)
func route(from: Vector3,to: Vector3) -> PackedVector3Array:
	if nav.get_point_count() == 0: return PackedVector3Array([to])
	return nav.get_point_path(nav.get_closest_point(from),nav.get_closest_point(to))
