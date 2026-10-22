class_name PulseContact
extends WeaponContactBurst
## Compact ion bloom with closed shells, latitude bands and solid beads.
const ION_SHELL = preload("res://shaders/combat/pulse_contact_3d.gdshader")

func _init() -> void:
	size_m = 0.46
	duration = 0.52
	primary_color = Color("22e6ff")
	secondary_color = Color("087cae")
	core_color = Color("b6ffff")
	tertiary_color = Color("023a5c")
	emission_energy = 3.0

func _build_layers() -> void:
	add_volume("Core","ThermalShell",0,Vector3.ONE*0.24,0.0,0.52)
	add_volume("ScallopedShell","BurstShell",1,Vector3(0.92,0.92,0.62),0.0,0.94)
	add_volume("LatitudeBands","ThermalShell",2,Vector3(1.0,1.0,0.68),0.06,1.0)
	for index in 8:
		var angle := float(index)*TAU/8.0
		var direction := Vector3(cos(angle),sin(angle),0.6).normalized()
		add_volume("IonBead"+str(index),"PacketShell",3,Vector3(0.07,0.07,0.14),0.1,0.88,direction)

func add_volume(id: String, mesh_id: String, mode: int, extent: Vector3, start: float, end: float, direction := Vector3.ZERO) -> void:
	var body := MeshInstance3D.new()
	body.name = id
	body.mesh = EffectMeshes.mesh(mesh_id)
	body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var material := ShaderMaterial.new()
	material.shader = ION_SHELL
	material.set_shader_parameter("layer",mode)
	body.material_override = material
	body.custom_aabb = AABB(Vector3.ONE*-0.8,Vector3.ONE*1.6)
	add_child(body)
	_materials.append(material)
	_layers.append({"node":body,"material":material,"start":start,"end":end,"extent":extent,"direction":direction,"mode":mode})

func _render_progress(progress: float) -> void:
	super._render_progress(progress)
	for entry in _layers:
		var t := clampf((progress-entry.start)/maxf(entry.end-entry.start,0.001),0,1)
		var expansion := lerpf(0.12,1.0,smoothstep(0,0.4,t))
		entry.node.scale = entry.extent*expansion
		entry.node.position = Vector3(0,0,0.12)
		if entry.mode==0: entry.node.scale *= 1.0-t*0.65
		if entry.mode==3:
			entry.node.position += entry.direction*lerpf(0.06,0.56,t)
			entry.node.scale *= 1.0-t*0.7
