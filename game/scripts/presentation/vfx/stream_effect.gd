class_name CombatStream
extends Node3D

const ARC = preload("res://shaders/combat/lightning_arc.gdshader")
const STRAND_PARTICLES = preload("res://shaders/combat/lightning_strand_particles.gdshader")
const FLAME_SOURCE_RADIUS := 0.035
const FLAME_END_RADIUS := 0.12
const FLAME_OUTER_SOURCE_RADIUS := 0.05
const FLAME_OUTER_END_RADIUS := 0.17
const ROBOT_FLAME_OVERLAP := 0.15
static var noise_texture: NoiseTexture2D
var kind := "lightning"
var layers: Array[Dictionary] = []
var particles: Array[GPUParticles3D] = []
var idle_time := 0.0
var released := false
var reach := 1.0
var rng := RandomNumberGenerator.new()
var exhaust_radius := 0.065
var exhaust_tint := Color("ff7529")
var pack_fire: Node3D
var pack_beam: Node3D
var beam_materials: Array[ShaderMaterial] = []
var strand_sparks: Array[GPUParticles3D] = []

static func arc_noise() -> NoiseTexture2D:
	if noise_texture == null:
		var noise := FastNoiseLite.new()
		noise.noise_type = FastNoiseLite.TYPE_CELLULAR
		noise.frequency = 0.12
		noise_texture = NoiseTexture2D.new()
		noise_texture.width = 128
		noise_texture.height = 128
		noise_texture.noise = noise
	return noise_texture

static func tube(radius: float, tip: float, rings := 32) -> CylinderMesh:
	var mesh := CylinderMesh.new()
	mesh.bottom_radius = radius
	mesh.top_radius = tip
	mesh.height = 1.0
	mesh.radial_segments = 8
	mesh.rings = rings
	mesh.cap_top = false
	mesh.cap_bottom = false
	return mesh

func _ready():
	rng.randomize()
	if kind == "lightning":
		for i in 3:
			layer(tube(0.02, 0.02), ARC, 1.0, {"noise_texture": arc_noise(), "arc_seed": rng.randf() * 100, "arc_color": Color("bdefff") if i == 0 else Color("74bfff"), "arc_amplitude": [0.1, 0.2, 0.28][i], "arc_opacity": [1.0, 0.22, 0.16][i], "core_continuity": 0.35 if i == 0 else 0.0})
		add_strand_sparks()
	else:
		var thermal := OriginalEffect.new()
		thermal.kind = "beam" if kind == "flame" else "exhaust"
		thermal.emission = 1.5 if kind == "flame" else 0.65
		thermal.secondary_color = exhaust_tint
		add_child(thermal)
		if kind == "flame": pack_beam = thermal
		else: pack_fire = thermal
		beam_materials = PackVfx.materials(thermal)

func layer(mesh: Mesh, shader: Shader, ratio: float, parameters: Dictionary) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.mesh = mesh
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.extra_cull_margin = 0.6
	var material := ShaderMaterial.new()
	material.shader = shader
	for key in parameters: material.set_shader_parameter(key, parameters[key])
	node.material_override = material
	add_child(node)
	layers.append({"node": node, "material": material, "ratio": ratio})
	return node

func update_endpoints(from: Vector3, to: Vector3, robot_contact := false):
	if released: return
	idle_time = 0
	reach = from.distance_to(to)
	visible = reach > 0.015
	if not visible: return
	global_transform = Transform3D(Basis(Quaternion(Vector3.UP, (to - from).normalized())), from)
	var thermal := (pack_beam if pack_beam else pack_fire) as OriginalEffect
	if thermal:
		var overlap := ROBOT_FLAME_OVERLAP if kind=="flame" and robot_contact else 0.0
		thermal.update_length(reach+overlap,FLAME_SOURCE_RADIUS if kind == "flame" else exhaust_radius * 0.55,FLAME_OUTER_END_RADIUS if kind == "flame" else exhaust_radius)
		for material in beam_materials:
			material.set_shader_parameter("clip_enabled",true)
			material.set_shader_parameter("clip_origin",from)
			material.set_shader_parameter("clip_direction",(to-from).normalized())
			material.set_shader_parameter("clip_length",reach+overlap)
			if kind=="flame": material.set_shader_parameter("robot_contact",robot_contact)
		return
	for entry in layers:
		if entry.ratio == 0: continue
		entry.node.position.y = reach * entry.ratio * 0.5
		entry.node.scale.y = reach * entry.ratio
	for emitter in particles:
		emitter.visibility_aabb = AABB(Vector3(-2, -2, -2), Vector3(4, reach + 4, 4))
	for emitter in strand_sparks:
		emitter.process_material.set_shader_parameter("beam_length", reach)
		emitter.amount_ratio = clampf(reach / 12.0, 0.5, 1.0)

func release():
	if released: return
	released = true
	idle_time = 0
	for emitter in particles: emitter.emitting = false
	for emitter in strand_sparks: emitter.hide()
	# Stop the damaging-looking stream immediately; only detached particles retire.
	for entry in layers: entry.node.hide()
	if pack_fire: pack_fire.hide()
	if pack_beam: pack_beam.hide()

func _process(dt: float):
	idle_time += dt
	if not released and idle_time > 0.15: release()
	if released and idle_time > 1.0:
		queue_free()
		return

func add_strand_sparks():
	LightningOrb.prepare_lightning()
	for index in LightningOrb.LIGHTNING_MESHES.size():
		var emitter := GPUParticles3D.new()
		emitter.name = "StrandSparks" + str(index + 1)
		emitter.amount = 12
		emitter.lifetime = 0.55
		emitter.preprocess = 0.3
		emitter.local_coords = true
		emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		emitter.draw_pass_1 = LightningOrb.LIGHTNING_MESHES[index]
		emitter.material_override = LightningOrb.lightning_material
		var material := ShaderMaterial.new()
		material.shader = STRAND_PARTICLES
		material.set_shader_parameter("strand_seed_1", layers[1].material.get_shader_parameter("arc_seed"))
		material.set_shader_parameter("strand_seed_2", layers[2].material.get_shader_parameter("arc_seed"))
		material.set_shader_parameter("core_seed", layers[0].material.get_shader_parameter("arc_seed"))
		material.set_shader_parameter("particle_seed", rng.randf() * 100.0)
		emitter.process_material = material
		add_child(emitter)
		particles.append(emitter)
		strand_sparks.append(emitter)
