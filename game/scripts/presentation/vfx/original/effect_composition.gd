class_name OriginalEffect
extends Node3D

# Independent composition built from the library's generated effect kit.
const THERMAL = preload("res://shaders/original/thermal_surface.gdshader")
const SHELL = preload("res://shaders/original/eruption_shell.gdshader")
const NOISE = preload("res://assets/models/effects/combat_effects/turbulence_rgba.png")
@export var kind := "rocket"
@export var primary_color := Color("ffdb64")
@export var secondary_color := Color("f94b0b")
@export var tertiary_color := Color("3b342e")
@export var emission := 2.6
var speed_scale := 1.0
var age := 0.0
var duration := 1.35
var playing := false
var reduced_motion := false
var surfaces: Array[Dictionary] = []
var emitters: Array[GPUParticles3D] = []
var beam_length := 1.0
var start_radius := 0.035
var end_radius := 0.17
var budget_ratio := 1.0
var _last_fit := Vector3(-1,-1,-1)
static var flash_sequence := 0
var _muzzle_recipe: Array = []

func _ready() -> void:
	if kind.begins_with("flash"):
		build_muzzle_3d()
	elif kind == "beam":
		duration = 0.0
		for index in 11:
			var volume := add_mesh("ThermalPlume"+str(index),"ThermalShell",preload("res://shaders/original/flame_stream_3d.gdshader"),"flame_volume")
			var material: ShaderMaterial = volume.material_override
			material.set_shader_parameter("layer",index if index<3 else 3 if index<7 else 4)
			material.set_shader_parameter("flare_phase",float(index-3)*PI*0.5+(PI*0.25 if index>=7 else 0.0))
			material.set_shader_parameter("density_volume",preload("res://assets/effects/original/rocket_density.tres"))
			material.set_shader_parameter("flow_material",preload("res://assets/models/effects/combat_effects/muzzle_albedo_density.png"))
			material.set_shader_parameter("flow_relief",preload("res://assets/models/effects/combat_effects/muzzle_normal_roughness.png"))
		update_length(1.0)
		playing = true
	elif kind == "exhaust":
		duration = 0.0
		for index in 3:
			var mesh_id := "FlameEnvelope" if index < 2 else "VortexSheets"
			var plume := add_mesh("ThermalPlume" + str(index),mesh_id,THERMAL,"plume")
			plume.material_override.set_shader_parameter("axial",true)
			plume.material_override.set_shader_parameter("plume_shape",1 if index < 2 else 2)
			plume.material_override.set_shader_parameter("continuous_beam",false)
			plume.material_override.set_shader_parameter("phase",index * 1.731)
			plume.material_override.set_shader_parameter("turbulence_texture",NOISE)
			plume.material_override.set_shader_parameter("effect_opacity",[0.8,0.32,0.24][index])
		update_length(1.0)
		playing = true
	elif kind == "orb":
		duration = 0.0
		for index in 3:
			var core := add_mesh("ThermalCore" + str(index),"ThermalShell" if index == 0 else "BurstShell" if index == 1 else "VortexSheets",THERMAL,"orb")
			core.scale = Vector3.ONE * [0.85,0.85,0.9][index]
			core.material_override.set_shader_parameter("turbulence_texture",NOISE)
			core.material_override.set_shader_parameter("effect_opacity",[0.9,0.35,0.3][index])
		playing = true
	else:
		if kind in ["rocket","grenade","fire_hit"]: build_combustion_impact()
		else: build_energy_impact()
	apply_palette()
	set_detail(int(get_viewport().get_meta("effect_quality",2)))
	set_process(playing and duration > 0.0)

func build_muzzle_3d() -> void:
	duration = 0.18 if kind == "flash_wide" else 0.12 if kind == "flash_big" else 0.10
	emission = 5.5
	var profile := ["flash_short","flash_long","flash_wide","flash_big"].find(kind)
	for index in 4:
		var gas := add_mesh(["MuzzleFlare","MuzzleCore","MuzzleCrown","MuzzleCurls"][index],"FlameEnvelope" if index==0 else "PressureRing" if index==2 else "VortexSheets" if index==3 else "Nozzle",preload("res://shaders/original/muzzle_flare_3d.gdshader"),"muzzle_3d")
		gas.material_override.set_shader_parameter("turbulence",NOISE)
		gas.material_override.set_shader_parameter("gas_atlas",preload("res://assets/models/effects/combat_effects/gas_atlas.png"))
		gas.material_override.set_shader_parameter("flow_material",preload("res://assets/models/effects/combat_effects/muzzle_albedo_density.png"))
		gas.material_override.set_shader_parameter("flow_relief",preload("res://assets/models/effects/combat_effects/muzzle_normal_roughness.png"))
		gas.material_override.set_shader_parameter("profile",profile)
		gas.material_override.set_shader_parameter("open_rim",index==2)
		gas.material_override.set_shader_parameter("flow_sheet",index==3)
		gas.material_override.set_shader_parameter("core_layer",index==1)
		gas.material_override.set_shader_parameter("layer_energy",[0.3,1.0,0.55,0.25][index])
		gas.material_override.set_shader_parameter("layer_scale",1.15 if index==3 else 1.0)
		gas.material_override.set_shader_parameter("effect_opacity",0.4 if index==3 else 1.0)
		gas.custom_aabb = AABB(Vector3(0,-0.75,-0.75),Vector3(1.5,1.5,1.5))
	configure_muzzle(load("res://assets/effects/muzzle/"+["pistol","rifle","minigun","rocket_launcher"][profile]+".tres"))

func configure_muzzle(profile: MuzzleFlashProfile, length_override := 0.0) -> void:
	var recipe := [profile.outer_color,profile.jet_color,profile.edge_color,profile.outer_radius,profile.jet_radius,profile.outer_length,profile.jet_length,profile.lifetime,profile.emission,length_override]
	if recipe == _muzzle_recipe: return
	_muzzle_recipe = recipe
	duration = profile.lifetime
	var fit := length_override/maxf(profile.outer_length,profile.jet_length) if length_override>0.0 else 1.0
	var radius := maxf(profile.outer_radius,profile.jet_radius)*fit*2.0
	var length := maxf(profile.outer_length,profile.jet_length)*fit
	for surface in surfaces:
		if surface.role != "muzzle_3d": continue
		for parameter in ["outer_color","jet_color","edge_color","emission"]:
			surface.material.set_shader_parameter(parameter,profile.get(parameter))
		for parameter in ["outer_radius","jet_radius","outer_length","jet_length"]:
			surface.material.set_shader_parameter(parameter,float(profile.get(parameter))*fit)
		surface.node.custom_aabb = AABB(Vector3(0,-radius,-radius),Vector3(length,radius*2.0,radius*2.0))

func add_mesh(id: String, mesh_id: String, shader: Shader, role: String) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = id
	node.mesh = EffectMeshes.mesh(mesh_id)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var material := ShaderMaterial.new()
	material.shader = shader
	node.material_override = material
	add_child(node)
	surfaces.append({"node":node,"material":material,"role":role})
	return node

func build_combustion_impact() -> void:
	duration = 1.45 if kind == "rocket" else 0.9 if kind == "grenade" else 0.8
	if kind == "rocket":
		build_rocket_3d()
		add_sparks()
		add_fragments()
		return
	if kind == "grenade":
		build_grenade_3d()
		add_sparks()
		add_fragments()
		return
	build_fireball_hit_3d()

func build_fireball_hit_3d() -> void:
	duration = 0.48
	var fuel_shader := preload("res://shaders/original/fireball_contact_3d.gdshader")
	for index in 3:
		var angle := float(index)*TAU/3.0
		var offset := Vector3(cos(angle)*0.1,0.1,sin(angle)*0.1)
		add_gas_lobe("FuelLobe"+str(index),fuel_shader,4,offset,0.65,index*1.71,index,Vector3(1,0.8,1))
	for index in 6:
		var phase := float(index)*1.17
		var direction := Vector3(cos(phase)*0.8,0.75+0.2*sin(phase*1.3),sin(phase)*0.8).normalized()
		var flare := add_mesh("FuelFlare"+str(index),"FlameEnvelope" if index<3 else "VortexSheets",preload("res://shaders/original/fireball_flare_cloud.gdshader"),"fuel_flare")
		flare.material_override.set_shader_parameter("flow_material",preload("res://assets/models/effects/combat_effects/fireball_flame_albedo_density.png"))
		flare.material_override.set_shader_parameter("flow_relief",preload("res://assets/models/effects/combat_effects/fireball_flame_normal_roughness.png"))
		flare.material_override.set_shader_parameter("phase",phase)
		flare.material_override.set_shader_parameter("flow_sheet",index>=3)
		flare.material_override.set_shader_parameter("flare_length",0.48 if index<3 else 0.36)
		flare.material_override.set_shader_parameter("flare_radius",0.16 if index<3 else 0.12)
		flare.quaternion = Quaternion(Vector3.UP,direction)*Quaternion(Vector3.UP,phase)
		flare.custom_aabb = AABB(Vector3.ONE*-0.7,Vector3.ONE*1.4)
		surfaces[-1].merge({"direction":direction,"phase":phase})
	add_gas_lobe("CoolingWisp",fuel_shader,1,Vector3(0,0.14,0.03),0.4,6.1,1,Vector3(1,0.8,1))
	add_gas_lobe("IgnitionCore",fuel_shader,2,Vector3(0,0.07,0),0.28,0,0)

func build_rocket_3d() -> void:
	var cloud_shader := preload("res://shaders/original/combustion_cloud_3d.gdshader")
	add_spherical_cloud("BurningLobe",cloud_shader,0,0.65,0.2,1.6)
	add_spherical_cloud("SootLobe",cloud_shader,1,0.85,0.3,1.4)
	add_gas_lobe("IgnitionCore",cloud_shader,2,Vector3(0,0.25,0),0.8,0,0)
	var wave := add_mesh("PressureWave","ThermalShell",preload("res://shaders/original/rocket_wave_3d.gdshader"),"rocket_wave")
	wave.custom_aabb = AABB(Vector3.ONE*-0.6,Vector3.ONE*1.2)

func build_grenade_3d() -> void:
	var cloud_shader := preload("res://shaders/original/combustion_cloud_3d.gdshader")
	add_spherical_cloud("DustLobe",cloud_shader,3,0.65,0.16,1.8)
	add_gas_lobe("IgnitionCore",cloud_shader,2,Vector3(0,0.05,0),0.55,0,0)

func add_spherical_cloud(prefix: String, shader: Shader, layer: int, radius: float, height: float, size: float, angle_offset := 0.0, opacity := 1.0) -> void:
	# Six overlapping lobes cover a sphere without a preferred long axis.
	# Preserve coverage at low detail; reduce ray-march samples instead of sectors.
	var directions := [Vector3.RIGHT,Vector3.LEFT,Vector3.UP,Vector3.DOWN,Vector3.BACK,Vector3.FORWARD]
	for index in 6:
		var direction: Vector3 = Basis(Vector3.UP,angle_offset)*directions[index]
		add_gas_lobe(prefix+str(index),shader,layer,direction*radius+Vector3.UP*height,size,8.3+index*1.63,index)
		surfaces[-1].material.set_shader_parameter("effect_opacity",opacity)
		surfaces[-1]["spherical"] = true

func add_gas_lobe(id: String, shader: Shader, layer: int, offset: Vector3, size: float, phase: float, rank: int, stretch := Vector3.ONE) -> void:
	var node := add_mesh(id,"ThermalShell",shader,"spatial_gas")
	node.material_override.set_shader_parameter("turbulence",NOISE)
	node.material_override.set_shader_parameter("density_volume",preload("res://assets/effects/original/rocket_density.tres"))
	node.material_override.set_shader_parameter("albedo_height",preload("res://assets/models/effects/combat_effects/rocket_cloud_albedo_height.png"))
	node.material_override.set_shader_parameter("normal_roughness",preload("res://assets/models/effects/combat_effects/rocket_cloud_normal_roughness.png"))
	if kind=="fire_hit":
		node.material_override.set_shader_parameter("albedo_height",preload("res://assets/models/effects/combat_effects/fireball_smoke_albedo_density.png") if layer==1 else preload("res://assets/models/effects/combat_effects/fireball_flame_albedo_density.png"))
		node.material_override.set_shader_parameter("normal_roughness",preload("res://assets/models/effects/combat_effects/fireball_smoke_normal_roughness.png") if layer==1 else preload("res://assets/models/effects/combat_effects/fireball_flame_normal_roughness.png"))
	node.material_override.set_shader_parameter("layer",layer)
	node.material_override.set_shader_parameter("phase",phase)
	node.rotation = Vector3(phase*0.17,phase*0.31,phase*0.23)
	node.custom_aabb = AABB(Vector3.ONE*-0.85,Vector3.ONE*1.7)
	surfaces[-1].merge({"offset":offset,"size":size,"layer":layer,"rank":rank,"stretch":stretch})

func build_energy_impact() -> void:
	duration = 0.65
	primary_color = Color("c8cbd0")
	secondary_color = Color("666a70")
	for index in 2:
		var shell := add_mesh("HotShell"+str(index),"BurstShell",SHELL,"hot")
		shell.material_override.set_shader_parameter("turbulence",NOISE)
		shell.material_override.set_shader_parameter("phase",index*0.37)
		shell.rotation = Vector3(index*0.8,index*1.7,0.3)
	var smoke := add_mesh("Smoke","BurstShell",SHELL,"smoke")
	smoke.material_override.set_shader_parameter("turbulence",NOISE)
	smoke.material_override.set_shader_parameter("smoke",true)
	smoke.hide()
	for index in 2:
		var ring := add_mesh("PressureFront"+str(index),"PressureRing",preload("res://shaders/original/pressure_ring.gdshader"),"ring")
		ring.rotation = Vector3(index*1.1,0,index*0.7)

func add_sparks() -> void:
	var emitter := GPUParticles3D.new()
	emitter.name = "Sparks"
	emitter.amount = 40 if kind == "grenade" else 24
	emitter.one_shot = true
	emitter.emitting = false
	emitter.explosiveness = 1.0
	emitter.lifetime = 0.22 if kind == "grenade" else 0.42
	emitter.local_coords = true
	emitter.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Y_TO_VELOCITY
	emitter.visibility_aabb = AABB(Vector3.ONE * -5.0,Vector3.ONE * 10.0)
	emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3.UP
	process.spread = 180.0 if kind == "grenade" else 100.0
	process.initial_velocity_min = 9.0 if kind == "grenade" else 2.0
	process.initial_velocity_max = 22.0 if kind == "grenade" else 8.0
	process.gravity = Vector3(0,-2.0,0)
	process.scale_min = 0.15
	process.scale_max = 0.45
	var gradient := Gradient.new()
	gradient.set_color(0,Color.WHITE)
	gradient.set_color(1,Color(1,1,1,0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = gradient
	process.color_ramp = ramp
	emitter.process_material = process
	emitter.draw_pass_1 = EffectMeshes.mesh("FragmentChip")
	var material := ShaderMaterial.new()
	material.shader = preload("res://shaders/original/casing_fragment.gdshader")
	process.scale_min = 0.035
	process.scale_max = 0.11
	emitter.material_override = material
	add_child(emitter)
	emitters.append(emitter)

func add_fragments() -> void:
	var emitter := GPUParticles3D.new()
	emitter.name = "CasingFragments"
	emitter.amount = 24
	emitter.one_shot = true
	emitter.emitting = false
	emitter.explosiveness = 1.0
	emitter.lifetime = 0.35
	emitter.local_coords = true
	emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	emitter.visibility_aabb = AABB(Vector3.ONE*-6,Vector3.ONE*12)
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3.UP
	process.spread = 180.0
	process.initial_velocity_min = 7.0
	process.initial_velocity_max = 15.0
	process.gravity = Vector3(0,-2,0)
	process.angular_velocity_min = -360.0
	process.angular_velocity_max = 360.0
	process.scale_min = 0.025
	process.scale_max = 0.07
	emitter.process_material = process
	emitter.draw_pass_1 = EffectMeshes.mesh("FragmentChip")
	var material := ShaderMaterial.new()
	material.shader = preload("res://shaders/original/casing_fragment.gdshader")
	emitter.material_override = material
	add_child(emitter)
	emitters.append(emitter)

func apply_palette() -> void:
	for surface in surfaces:
		for key in ["primary_color","secondary_color","tertiary_color","emission"]:
			surface.material.set_shader_parameter(key,get(key))

func play() -> float:
	age = 0.0
	playing = true
	show()
	if kind.begins_with("flash"): flash_sequence += 1
	for surface in surfaces:
		if surface.role == "spatial_gas":
			surface.material.set_shader_parameter("impact_origin",global_position+global_basis.y*0.12)
		elif surface.role == "muzzle_3d":
			surface.node.set_instance_shader_parameter("shot_phase",fmod(flash_sequence*2.39996323,TAU*100.0))
	for emitter in emitters:
		emitter.amount_ratio = budget_ratio
		emitter.restart()
		emitter.emitting = true
	set_process(true)
	_process(0.0)
	return duration / maxf(speed_scale,0.01)

func update_length(length_m: float, nozzle := 0.035, tip := 0.17) -> void:
	var fit := Vector3(length_m,nozzle,tip)
	if fit == _last_fit: return
	_last_fit = fit
	beam_length = maxf(length_m,0.001)
	start_radius = nozzle
	end_radius = tip
	for emitter in emitters:
		emitter.visibility_aabb = AABB(Vector3(-0.5,-1.0,-0.5),Vector3(1.0,beam_length+2.0,1.0))
	if surfaces.is_empty(): return
	var radius := maxf(nozzle,tip)
	for index in surfaces.size():
		var node: MeshInstance3D = surfaces[index].node
		var material: ShaderMaterial = surfaces[index].material
		var width := 0.55 if index == 0 else 1.0
		var radius_from := nozzle * width
		var radius_to := tip * width
		if kind == "beam":
			radius_from = 0.035 if index == 0 else 0.05
			radius_to = 0.12 if index == 0 else tip
		var layer_length: float = beam_length * ([0.45,0.6,0.9][index] if kind == "exhaust" else [0.32,1.0,1.0,0.5,0.5,0.5,0.5,1.0,1.0,1.0,1.0][index])
		material.set_shader_parameter("beam_length",layer_length)
		material.set_shader_parameter("start_radius",radius_from)
		material.set_shader_parameter("end_radius",radius_to)
		if kind == "beam": material.set_shader_parameter("segment_length",beam_length)
		var bounds_radius := radius*3.0 if kind=="beam" and index>=3 else radius
		node.custom_aabb = AABB(Vector3(-bounds_radius,0,-bounds_radius),Vector3(bounds_radius * 2.0,beam_length,bounds_radius * 2.0))

func set_budget(reduced: bool, distance: float) -> void:
	budget_ratio = 0.25 if reduced or distance >= 60.0 else 0.5 if distance >= 25.0 else 1.0
	apply_emitter_budget()

func set_detail(quality: int) -> void:
	var index := clampi(quality,0,3)
	budget_ratio = [0.25,0.5,0.75,1.0][index]
	apply_emitter_budget()

func apply_emitter_budget() -> void:
	for emitter in emitters:
		emitter.amount_ratio = budget_ratio
	for surface in surfaces:
		if surface.role == "spatial_gas":
			surface.node.visible = int(surface.rank)<(2 if budget_ratio<=0.25 else 3 if budget_ratio<=0.5 else 5)
			if surface.get("spherical",false): surface.node.visible = true
			surface.material.set_shader_parameter("march_steps",16 if budget_ratio<=0.5 else 24 if budget_ratio<1.0 else 32)

func _process(dt: float) -> void:
	if duration <= 0.0: return
	age += dt * speed_scale
	var progress := clampf(age / duration,0.0,1.0)
	var compact := 0.42 if kind == "emp" else 1.0
	for surface in surfaces:
		var node: MeshInstance3D = surface.node
		node.set_instance_shader_parameter("progress",progress)
		match surface.role:
			"spatial_gas":
				var expansion := 0.08+0.92*(1.0-exp(-age*(11.0 if int(surface.layer)==1 else 19.0)))
				node.scale = surface.stretch*float(surface.size)*expansion
				node.position = surface.offset*expansion+Vector3.UP*((0.025+progress*0.045) if kind=="fire_hit" else (0.12+progress*0.22) if kind=="grenade" else (0.18+progress*0.28))
			"fuel_flare":
				var unfold := 0.12+0.88*(1.0-exp(-age*38.0))
				node.scale = Vector3.ONE*unfold
				node.position = Vector3.UP*0.045+surface.direction*(0.015+progress*0.1)
			"rocket_wave":
				node.scale = Vector3.ONE*(0.15+minf(age,0.4)*16.0)
			"hot":
				var growth := (0.6+3.4*(1.0-exp(-age*23.0))) * compact
				node.scale = Vector3.ONE * growth * (0.92 if node.name.ends_with("1") else 1.0)
			"smoke":
				node.scale = Vector3.ONE * (1.0+progress*3.0) * compact
				node.position.y = progress * 0.8
				node.visible = false
			"ring":
				node.scale = Vector3.ONE * (0.2+2.4*(1.0-exp(-age*12.0))) * compact
				node.set_instance_shader_parameter("progress",minf(1.0,progress*2.5))
	if progress >= 1.0:
		playing = false
		hide()
		set_process(false)
