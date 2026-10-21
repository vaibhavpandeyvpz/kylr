class_name OriginalEffect
extends Node3D

# Independent composition built from the library's generated effect kit.
const SPRITE = preload("res://shaders/original/burst_sprite.gdshader")
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

func _ready() -> void:
	if kind.begins_with("flash"):
		duration = 0.075
		var width := 0.30 if kind == "flash_wide" else 0.18
		if kind == "flash_big": width = 0.32
		for index in 2:
			var gas := add_mesh("Gas" + str(index),"AxialCard",SPRITE,"flash")
			gas.material_override.set_shader_parameter("billboard",false)
			gas.material_override.set_shader_parameter("use_atlas",true)
			gas.material_override.set_shader_parameter("flash_profile",["flash_short","flash_long","flash_wide","flash_big"].find(kind))
			gas.material_override.set_shader_parameter("gas_atlas",preload("res://assets/models/effects/combat_effects/gas_atlas.png"))
			gas.basis = Basis(Vector3.RIGHT,index * PI / 2.0) * Basis(Vector3.FORWARD,PI / 2.0)
			gas.scale = Vector3(width,1.5,1)
			gas.position.x = 0.75
			gas.custom_aabb = AABB(Vector3(-0.5,-0.5,-0.01),Vector3(1,1,0.02))
	elif kind in ["beam","exhaust"]:
		duration = 0.0
		for index in 3:
			var mesh_id := "Nozzle" if kind == "beam" and index == 0 else "FlameEnvelope" if index < 2 else "VortexSheets"
			var plume := add_mesh("ThermalPlume" + str(index),mesh_id,THERMAL,"plume")
			plume.material_override.set_shader_parameter("axial",true)
			plume.material_override.set_shader_parameter("plume_shape",0 if kind == "beam" and index == 0 else 1 if index < 2 else 2)
			plume.material_override.set_shader_parameter("continuous_beam",kind == "beam")
			plume.material_override.set_shader_parameter("phase",index * 1.731)
			plume.material_override.set_shader_parameter("turbulence_texture",NOISE)
			plume.material_override.set_shader_parameter("effect_opacity",([0.09,0.08,0.06] if kind == "beam" else [0.8,0.32,0.24])[index])
		update_length(1.0)
		if kind == "beam": add_projected_gas()
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
	var atlas: Texture2D = preload("res://assets/models/effects/combat_effects/rocket_explosion_atlas.png")
	if kind == "grenade": atlas = preload("res://assets/models/effects/combat_effects/grenade_combustion_atlas.png")
	if kind == "fire_hit": atlas = preload("res://assets/models/effects/combat_effects/fire_contact_atlas.png")
	var volume := add_mesh("CoolingGas","AxialCard",preload("res://shaders/original/gas_volume.gdshader"),"gas_volume")
	volume.material_override.set_shader_parameter("volume_atlas",atlas)
	volume.material_override.set_shader_parameter("event_profile",3 if kind == "grenade" else 2 if kind == "fire_hit" else 0)
	volume.material_override.set_shader_parameter("surface_aligned",kind == "fire_hit")
	volume.material_override.set_shader_parameter("anchor_offset_y",0.3 if kind == "fire_hit" else 0.12 if kind == "grenade" else 0.0)
	# Covers camera-facing rotation and the fuel flare's shifted surface anchor.
	volume.custom_aabb = AABB(Vector3.ONE*-1.0,Vector3.ONE*2.0)
	if kind == "rocket":
		var jet := add_mesh("BlastJet","FlameEnvelope",THERMAL,"blast_jet")
		jet.material_override.set_shader_parameter("turbulence_texture",NOISE)
		jet.material_override.set_shader_parameter("axial",true)
		jet.material_override.set_shader_parameter("plume_shape",1)
		jet.material_override.set_shader_parameter("beam_length",1.4)
		jet.material_override.set_shader_parameter("end_radius",0.45)
		jet.material_override.set_shader_parameter("effect_emission",0.45)
		jet.custom_aabb = AABB(Vector3(-0.5,0,-0.5),Vector3(1,1.5,1))
		add_mesh("BurstStreaks","BurstRays",preload("res://shaders/original/pressure_ring.gdshader"),"rays")
	elif kind == "fire_hit":
		for index in 2:
			var lick := add_mesh("FuelTongue"+str(index),"FlameEnvelope" if index == 0 else "VortexSheets",THERMAL,"fuel_lick")
			lick.material_override.set_shader_parameter("turbulence_texture",NOISE)
			lick.material_override.set_shader_parameter("axial",true)
			lick.material_override.set_shader_parameter("plume_shape",1 if index == 0 else 2)
			lick.material_override.set_shader_parameter("beam_length",0.65)
			lick.material_override.set_shader_parameter("end_radius",0.18)
			lick.material_override.set_shader_parameter("phase",index*1.73)
			lick.material_override.set_shader_parameter("effect_emission",0.35)
			lick.position.x = -0.1 if index == 0 else 0.1
			lick.rotation.z = -0.25 if index == 0 else 0.3
			lick.custom_aabb = AABB(Vector3(-0.25,0,-0.25),Vector3(0.5,0.7,0.5))
	add_sparks()
	if kind == "grenade": add_fragments()

func build_energy_impact() -> void:
	duration = 0.65 if kind == "emp" else 0.45
	primary_color = Color("c8cbd0") if kind == "emp" else Color("d7fbff")
	secondary_color = Color("666a70") if kind == "emp" else Color("21bce8")
	if kind == "pulse":
		add_mesh("IonFlash","AxialCard",SPRITE,"ion_flash")
		for index in 3:
			var arc := add_mesh("IonFilament"+str(index),"ElectricalRibbon0" if index%2 == 0 else "ElectricalRibbon1",preload("res://shaders/original/electrical_ribbon.gdshader"),"ion_arc")
			arc.material_override.set_shader_parameter("Tint",secondary_color)
			arc.material_override.set_shader_parameter("Intensity",1.4)
			arc.rotation = Vector3(index*0.9,index*1.3,0.6+index*0.7)
			arc.custom_aabb = AABB(Vector3.ONE*-0.5,Vector3.ONE)
		add_mesh("IonWavefront","PressureRing",preload("res://shaders/original/ion_wave.gdshader"),"ion_wave")
		add_sparks()
		return
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
	add_sparks()

func add_sparks() -> void:
	var emitter := GPUParticles3D.new()
	emitter.name = "Sparks"
	emitter.amount = 12 if kind in ["fire_hit","pulse"] else 40 if kind == "grenade" else 24
	emitter.one_shot = true
	emitter.emitting = false
	emitter.explosiveness = 1.0
	emitter.lifetime = 0.12 if kind == "pulse" else 0.65 if kind == "fire_hit" else 0.22 if kind == "grenade" else 0.42
	emitter.local_coords = true
	emitter.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Y_TO_VELOCITY
	emitter.visibility_aabb = AABB(Vector3.ONE * -5.0,Vector3.ONE * 10.0)
	emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3.UP
	process.spread = 180.0 if kind == "grenade" else 100.0
	process.initial_velocity_min = 9.0 if kind == "grenade" else 0.4 if kind == "fire_hit" else 0.8 if kind == "pulse" else 2.0
	process.initial_velocity_max = 22.0 if kind == "grenade" else 2.0 if kind == "fire_hit" else 3.0 if kind == "pulse" else 8.0
	process.gravity = Vector3(0,-2.0,0)
	process.scale_min = 0.05 if kind == "pulse" else 0.15
	process.scale_max = 0.12 if kind == "pulse" else 0.45
	var gradient := Gradient.new()
	gradient.set_color(0,Color.WHITE)
	gradient.set_color(1,Color(1,1,1,0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = gradient
	process.color_ramp = ramp
	emitter.process_material = process
	emitter.draw_pass_1 = EffectMeshes.mesh("AxialCard")
	var material := ShaderMaterial.new()
	material.shader = SPRITE
	material.set_shader_parameter("billboard",false)
	material.set_shader_parameter("card_width",0.08)
	material.set_shader_parameter("primary_color",primary_color)
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

func add_projected_gas() -> void:
	# Two fixed, reusable GPU emitters transport overlapping lobes. The same
	# authored flame envelope is used for thrusters; no per-tick mesh creation.
	for index in 2:
		var emitter := GPUParticles3D.new()
		emitter.name = "ProjectedFumes" if index == 1 else "ProjectedFlame"
		emitter.amount = 32 if index == 0 else 16
		emitter.lifetime = 0.85
		emitter.fixed_fps = 60
		emitter.interpolate = true
		emitter.local_coords = true
		emitter.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Y_TO_VELOCITY
		emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var process := ParticleProcessMaterial.new()
		process.direction = Vector3.UP
		process.spread = 0.6
		process.anim_offset_max = 1.0
		# A narrow velocity band keeps neighbouring lobes overlapping rather
		# than overtaking each other and flickering into separate sheets.
		process.initial_velocity_min = 16.0
		process.initial_velocity_max = 17.0
		process.gravity = Vector3.ZERO
		emitter.process_material = process
		emitter.draw_pass_1 = EffectMeshes.mesh("AxialCard")
		var material := ShaderMaterial.new()
		if index == 0:
			material.shader = preload("res://shaders/original/gas_volume.gdshader")
			material.set_shader_parameter("volume_atlas",preload("res://assets/models/effects/combat_effects/fireball_atlas.png"))
			material.set_shader_parameter("particle_volume",true)
			material.set_shader_parameter("projected_jet",true)
			material.set_shader_parameter("event_profile",2)
			material.set_shader_parameter("effect_opacity",0.65)
			material.set_shader_parameter("emission",1.2)
		else:
			material.shader = preload("res://shaders/original/gas_volume.gdshader")
			material.set_shader_parameter("volume_atlas",preload("res://assets/models/effects/combat_effects/fireball_atlas.png"))
			material.set_shader_parameter("particle_volume",true)
			material.set_shader_parameter("projected_jet",true)
			material.set_shader_parameter("effect_opacity",0.18)
			material.set_shader_parameter("emission",0.25)
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
		var layer_length: float = beam_length * ([0.45,0.6,0.9][index] if kind == "exhaust" else [0.25,0.85,1.0][index])
		material.set_shader_parameter("beam_length",layer_length)
		material.set_shader_parameter("start_radius",radius_from)
		material.set_shader_parameter("end_radius",radius_to)
		node.custom_aabb = AABB(Vector3(-radius,0,-radius),Vector3(radius * 2.0,beam_length,radius * 2.0))

func set_budget(reduced: bool, distance: float) -> void:
	budget_ratio = 0.25 if reduced or distance >= 60.0 else 0.5 if distance >= 25.0 else 1.0
	apply_emitter_budget()

func set_detail(quality: int) -> void:
	var index := clampi(quality,0,3)
	budget_ratio = [0.25,0.5,0.75,1.0][index]
	apply_emitter_budget()

func apply_emitter_budget() -> void:
	for emitter in emitters:
		# Keep the damaging jet continuous; scale only its decorative cooling gas.
		emitter.amount_ratio = maxf(0.75,budget_ratio) if emitter.name == "ProjectedFlame" else budget_ratio

func _process(dt: float) -> void:
	if duration <= 0.0: return
	age += dt * speed_scale
	var progress := clampf(age / duration,0.0,1.0)
	var compact := 0.42 if kind in ["emp","pulse","fire_hit"] else 1.0
	for surface in surfaces:
		var node: MeshInstance3D = surface.node
		node.set_instance_shader_parameter("progress",progress)
		match surface.role:
			"hot":
				var growth := (0.6+3.4*(1.0-exp(-age*23.0))) * compact
				node.scale = Vector3.ONE * growth * (0.92 if node.name.ends_with("1") else 1.0)
			"smoke":
				node.scale = Vector3.ONE * (1.0+progress*3.0) * compact
				node.position.y = progress * 0.8
				node.visible = false
			"gas_volume":
				node.scale = Vector3.ONE * (4.8 if kind == "rocket" else 5.2 if kind == "grenade" else 3.6)
				node.position.y = 0.45+progress*0.4 if kind == "rocket" else 0.25+progress*0.2 if kind == "grenade" else 0.03
			"blast_jet":
				surface.material.set_shader_parameter("effect_opacity",0.4*(1.0-smoothstep(0.0,0.18,progress)))
			"fuel_lick":
				surface.material.set_shader_parameter("effect_opacity",0.3*(1.0-smoothstep(0.3,1.0,progress)))
			"ion_flash":
				node.scale = Vector3.ONE*(0.2+progress*0.65)
				node.set_instance_shader_parameter("progress",minf(1.0,progress*2.0))
			"ion_arc":
				node.scale = Vector3.ONE*(0.35+progress*0.25)
				node.visible = progress<0.7
				node.set_instance_shader_parameter("progress",minf(1.0,progress*1.5))
			"ion_wave":
				node.scale = Vector3.ONE*(0.1+progress*0.8)
				node.set_instance_shader_parameter("progress",minf(1.0,progress*2.0))
			"ring":
				node.scale = Vector3.ONE * (0.2+2.4*(1.0-exp(-age*12.0))) * compact
				node.set_instance_shader_parameter("progress",minf(1.0,progress*2.5))
			"rays":
				node.scale = Vector3.ONE * (0.7+age*10.0) * compact
				node.set_instance_shader_parameter("progress",minf(1.0,progress*4.0))
	if progress >= 1.0:
		playing = false
		hide()
		set_process(false)
