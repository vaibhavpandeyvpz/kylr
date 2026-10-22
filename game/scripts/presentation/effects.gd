class_name ArenaEffects
extends Node3D
var game

func replicate(event: Dictionary) -> bool:
	if game is ArenaMatch and game.replicating and game.authority:
		game.present(event)
		return true
	return false
var gravity := ArenaTuning.GRAVITY

const MAX_EFFECTS := 160
const MAX_SPARK_BURSTS := 16
const MAX_MUZZLE_FLASHES := 32
const SPARK_GRAVITY_RATIO := 8.0 / ArenaTuning.GRAVITY
const IMPACT = preload("res://shaders/combat/impact.gdshader")
const MUZZLE = preload("res://shaders/combat/muzzle_flash.gdshader")
const MUZZLE_PROFILES := {
	"pistol":preload("res://assets/effects/muzzle/pistol.tres"),
	"rifle":preload("res://assets/effects/muzzle/rifle.tres"),
	"minigun":preload("res://assets/effects/muzzle/minigun.tres"),
	"rocket_launcher":preload("res://assets/effects/muzzle/rocket_launcher.tres"),
	"lightning_gun":preload("res://assets/effects/muzzle/lightning_gun.tres")}
const FLASH_SHORT = preload("res://assets/effects/original/flash_short.tscn")
const FLASH_LONG = preload("res://assets/effects/original/flash_long.tscn")
const FLASH_WIDE = preload("res://assets/effects/original/flash_wide.tscn")
const FLASH_BIG = preload("res://assets/effects/original/flash_big.tscn")
var spark_pool: Array[ImpactSparks] = []
var lightning_pool: Array[LightningSparks] = []
var emp_pool: Array[PackBurst] = []
var rocket_pool: Array[PackBurst] = []
var grenade_pool: Array[PackBurst] = []
var pulse_pool: Array[PackBurst] = []
var bio_pool: Array[BioContact] = []
var flak_pool: Array[FlakContact] = []
var fire_orb_pool: Array[PackBurst] = []
var muzzle_pool: Array[PackBurst] = []
var idle_emp_charges: Array[EmpCharge] = []

func acquire_emp_charge(parent: Node3D) -> EmpCharge:
	var charge: EmpCharge
	if idle_emp_charges.is_empty():
		charge = EmpCharge.new()
		parent.add_child(charge)
	else:
		charge = idle_emp_charges.pop_back()
		charge.reparent(parent, false)
		charge.transform = Transform3D.IDENTITY
		charge.update_travel(0.0)
	return charge

func recycle_emp_charge(charge: EmpCharge) -> void:
	if idle_emp_charges.size() >= MAX_SPARK_BURSTS:
		charge.queue_free()
		return
	charge.hide()
	charge.reparent(self, false)
	idle_emp_charges.append(charge)

var count := 0
var rng := RandomNumberGenerator.new()
var card := QuadMesh.new()
var surface_material := ShaderMaterial.new()
var sprite_material := ShaderMaterial.new()
var muzzle_material := ShaderMaterial.new()
var line_mesh := CylinderMesh.new()
var warm_material: StandardMaterial3D
var electric_material: StandardMaterial3D
var brass_material: StandardMaterial3D
var stream_count := 0
var decal_material := ShaderMaterial.new()
var decals: Array[CombatTransient] = []
var explosion_materials: Array[ShaderMaterial] = []
var volume := SphereMesh.new()

func _init():
	rng.randomize()
	surface_material.shader = IMPACT
	sprite_material.shader = IMPACT
	sprite_material.set_shader_parameter("billboard", true)
	muzzle_material.shader = MUZZLE
	line_mesh.top_radius = 1.0
	line_mesh.bottom_radius = 0.15
	line_mesh.height = 1.0
	line_mesh.radial_segments = 5
	warm_material = Assets.material(Color("ffd295"), 3.0)
	electric_material = Assets.material(Color("88caff"), 3.0)
	brass_material = Assets.material(Color("b79152"))
	brass_material.metallic = 0.7
	CombatStream.arc_noise()
	decal_material.shader = preload("res://shaders/combat/bullet_decal.gdshader")
	volume.radius = 0.5
	volume.height = 1.0
	volume.radial_segments = 24
	volume.rings = 16
	for shader in [preload("res://shaders/combat/hit_effect_fire_volume.gdshader"), preload("res://shaders/combat/hit_effect_smoke_volume.gdshader"), preload("res://shaders/combat/hit_effect_blast_surface.gdshader")]:
		var material := ShaderMaterial.new()
		material.shader = shader
		explosion_materials.append(material)
	explosion_materials[1].set_shader_parameter("stepped_shading", false)

func stream(kind: String) -> CombatStream:
	if game is ArenaMatch and game.replicating and game.authority: return null
	if stream_count >= 16: return null
	var node := CombatStream.new()
	node.kind = kind
	add_child(node)
	stream_count += 1
	node.tree_exiting.connect(func(): stream_count -= 1)
	return node

func make(point: Vector3, duration: float, material: Material, geometry: Mesh = null) -> CombatTransient:
	if game is ArenaMatch and game.replicating and game.authority: return null
	if count >= MAX_EFFECTS: return null
	var effect := CombatTransient.new()
	effect.mesh = geometry if geometry else card
	effect.material_override = material
	effect.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	effect.lifetime = duration
	add_child(effect)
	effect.global_position = point
	count += 1
	effect.tree_exiting.connect(func(): count -= 1)
	return effect

func sprite(point: Vector3, color: Color, size: float, duration: float, style: float, billboard := true) -> CombatTransient:
	var effect := make(point, duration, sprite_material if billboard else surface_material)
	if not effect: return null
	effect.scale = Vector3.ONE * size
	effect.set_instance_shader_parameter("tint", color)
	effect.set_instance_shader_parameter("seed", rng.randf() * 100.0)
	effect.set_instance_shader_parameter("style", style)
	return effect

func muzzle(socket: Node3D, weapon: String, size_override := 0.0):
	if not is_instance_valid(socket): return
	if game is ArenaMatch and game.replicating and game.authority: return
	var scene: PackedScene = FLASH_SHORT if weapon == "pistol" or size_override > 0 else FLASH_BIG if weapon == "rocket_launcher" else FLASH_WIDE if weapon == "minigun" else FLASH_LONG
	var burst := packed_burst(muzzle_pool, scene, false, MAX_MUZZLE_FLASHES)
	if not burst: return
	var profile: MuzzleFlashProfile = MUZZLE_PROFILES.get(weapon,MUZZLE_PROFILES.pistol)
	burst.effect.configure_muzzle(profile,size_override)
	# Gas jets extend along +X in their local composition; sockets emit -Z.
	burst.anchor = weakref(socket)
	burst.anchor_offset = Transform3D(Basis(Vector3.UP, PI / 2), Vector3.ZERO)
	burst.fire(socket.global_position, Vector3.UP)
	burst.global_transform = socket.global_transform * burst.anchor_offset

func packed_burst(pool: Array[PackBurst], scene: PackedScene, emp := false, limit := MAX_SPARK_BURSTS) -> PackBurst:
	for candidate in pool:
		if candidate.remaining <= 0 and candidate.scene == scene: return candidate
	if pool.size() >= limit:
		for candidate in pool:
			if candidate.remaining <= 0:
				pool.erase(candidate)
				candidate.queue_free()
				break
	if pool.size() >= limit: return null
	var node := PackBurst.new()
	node.scene = scene
	node.emp = emp
	add_child(node)
	pool.append(node)
	return node
func beam(from: Vector3, to: Vector3, _color: Color, width: float):
	if from.distance_to(to) < 0.01: return
	var effect := make(from, maxf(0.035, from.distance_to(to) / 360.0 + 0.012), warm_material, line_mesh)
	if not effect: return
	effect.quaternion = Quaternion(Vector3.UP, (to - from).normalized())
	effect.scale = Vector3(width, 0.001, width)
	effect.tracer = true
	effect.tracer_from = from
	effect.tracer_to = to

func arc(from: Vector3, to: Vector3, width := 0.014):
	if from.distance_to(to) < 0.01: return
	for i in (1 if width < 0.01 else 3):
		var material := ShaderMaterial.new()
		material.shader = CombatStream.ARC
		material.set_shader_parameter("noise_texture", CombatStream.arc_noise())
		material.set_shader_parameter("arc_seed", rng.randf() * 100)
		material.set_shader_parameter("arc_amplitude", minf(from.distance_to(to) * 0.15, 0.1 + i * 0.09))
		material.set_shader_parameter("arc_opacity", 1.0 if i == 0 else 0.2)
		material.set_shader_parameter("core_continuity", 0.35 if i == 0 else 0.0)
		var segment := make((from + to) * 0.5, 0.055, material, CombatStream.tube(width, width))
		if not segment: return
		segment.quaternion = Quaternion(Vector3.UP, (to - from).normalized())
		segment.scale.y = from.distance_to(to)
		segment.extra_cull_margin = 0.4

func electric_contact(point: Vector3, normal: Vector3, broadcast := false):
	# Sustained contacts are presented from stream snapshots; orb hits are discrete.
	if broadcast and replicate({"kind":"electric","point":point,"normal":normal}): return
	if game is ArenaMatch and game.replicating and game.authority: return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst: LightningSparks
	for candidate in lightning_pool:
		if candidate.remaining <= 0:
			burst = candidate
			break
	if burst == null:
		if lightning_pool.size() >= MAX_SPARK_BURSTS: return
		burst = LightningSparks.new()
		add_child(burst)
		lightning_pool.append(burst)
	burst.fire(point + n * 0.015, n)
	sprite(point + n * 0.015, Color("bdefff"), 0.18, 0.1, 4.0)

func fire_contact(point: Vector3, normal: Vector3):
	if replicate({"kind":"fire_orb","point":point,"normal":normal}): return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst := packed_burst(fire_orb_pool, preload("res://assets/effects/original/fire_hit.tscn"))
	if burst:
		# World-space particles omit parent scale; local particles inherit hit size.
		for emitter in burst.effect.find_children("*", "GPUParticles3D", true, false):
			emitter.local_coords = true
		burst.fire(point + n * 0.015, n, 1.0)

func emp_contact(point: Vector3, normal: Vector3):
	if replicate({"kind":"emp","point":point,"normal":normal}): return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst := packed_burst(emp_pool, preload("res://assets/effects/original/emp.tscn"), true)
	if burst: burst.fire(point + n * 0.015, n, 0.6)
func sparks(point: Vector3, normal: Vector3, energy := false):
	var burst: ImpactSparks
	for candidate in spark_pool:
		if candidate.remaining <= 0:
			burst = candidate
			break
	if burst == null:
		if spark_pool.size() >= MAX_SPARK_BURSTS: return
		burst = ImpactSparks.new()
		add_child(burst)
		spark_pool.append(burst)
	burst.fire(point, normal, energy, gravity * SPARK_GRAVITY_RATIO)

func impact(point: Vector3, normal: Vector3, energy := false, surface: Node3D = null, robot_hit := false):
	if replicate({"kind":"impact","point":point,"normal":normal,"energy":energy,"robot":robot_hit}): return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var origin := point + n * 0.015
	var color := Color("79c8ff") if energy else Color("ffdf32")
	if energy: sprite(origin, color, 0.65, 0.19, 2.0)
	var core := sprite(origin, color, 0.45 if robot_hit else 0.28, 0.12, 4.0)
	if core: core.growth = 0.6
	sparks(origin, n, energy)
	var smoke := sprite(origin, Color(0.32, 0.34, 0.38, 0.65), 0.3, 0.65, 1.0)
	if smoke:
		smoke.velocity = n * 0.25 + Vector3.UP * 0.3
		smoke.growth = 0.7
	if surface and not energy and count < MAX_EFFECTS - 40:
		while not decals.is_empty() and not is_instance_valid(decals[0]): decals.pop_front()
		if decals.size() >= 64:
			var oldest = decals.pop_front()
			if is_instance_valid(oldest): oldest.queue_free()
		var mark := make(point + n * 0.003, 10.0, decal_material)
		if mark:
			mark.scale = Vector3.ONE * rng.randf_range(0.09, 0.16)
			mark.set_instance_shader_parameter("atlas_cell", rng.randi_range(0, 63))
			mark.quaternion = Quaternion(Vector3.BACK, n)
			mark.rotate_object_local(Vector3.BACK, rng.randf() * TAU)
			mark.anchor = weakref(surface)
			mark.anchor_offset = surface.global_transform.affine_inverse() * mark.global_transform
			decals.append(mark)

func explosion(point: Vector3, normal: Vector3, size := 1.3, incoming := Vector3.ZERO):
	if replicate({"kind":"explosion","point":point,"normal":normal,"size":size,"incoming":incoming}): return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var outward := -incoming.normalized() if incoming.length_squared() > 0.0001 else n
	var burst := packed_burst(rocket_pool, preload("res://assets/effects/original/rocket.tscn"))
	if burst: burst.fire(point + n * 0.06, outward, size * 0.6)
func grenade_explosion(point: Vector3, normal: Vector3):
	if replicate({"kind":"grenade_explosion","point":point,"normal":normal}): return
	if DisplayServer.get_name() == "headless": return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst := packed_burst(grenade_pool, preload("res://assets/effects/original/grenade.tscn"))
	if burst: burst.fire(point + n * 0.015, n)

func pulse_contact(point: Vector3, normal: Vector3):
	if replicate({"kind":"pulse_contact","point":point,"normal":normal}): return
	if DisplayServer.get_name() == "headless": return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst := packed_burst(pulse_pool, preload("res://assets/effects/original/pulse.tscn"))
	if burst: burst.fire(point + n * 0.015, n)

func bio_contact(point: Vector3, normal: Vector3):
	if replicate({"kind":"bio_contact","point":point,"normal":normal}): return
	if DisplayServer.get_name() == "headless": return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst: BioContact
	for candidate in bio_pool:
		if candidate.remaining <= 0.0:
			burst = candidate
			break
	if burst == null:
		if bio_pool.size() >= MAX_SPARK_BURSTS: return
		burst = BioContact.new()
		add_child(burst)
		bio_pool.append(burst)
	burst.fire(point+n*0.015,n)

func flak_contact(point: Vector3, normal: Vector3):
	if replicate({"kind":"flak_contact","point":point,"normal":normal}): return
	if DisplayServer.get_name() == "headless": return
	var n := normal.normalized() if normal.length_squared() > 0.01 else Vector3.UP
	var burst: FlakContact
	for candidate in flak_pool:
		if candidate.remaining <= 0.0:
			burst = candidate
			break
	if burst == null:
		if flak_pool.size() >= MAX_SPARK_BURSTS: return
		burst = FlakContact.new()
		add_child(burst)
		flak_pool.append(burst)
	burst.fire(point+n*0.015,n)

func burst(point: Vector3, color: Color, size: float):
	var flash := sprite(point, color, size * 2.0, 0.22, 4.0)
	if flash: flash.growth = size * 3.0
	if size > 0.5:
		sprite(point, color, size * 4.0, 0.4, 2.0)
		for i in 7:
			var smoke := sprite(point, Color(0.18, 0.2, 0.24, 0.8), size, 1.2, 1.0)
			if not smoke: break
			smoke.velocity = Vector3(rng.randf_range(-2, 2), rng.randf_range(0.4, 2.5), rng.randf_range(-2, 2))
			smoke.growth = 1.8

func flame(point: Vector3, direction: Vector3, reach := 12.0):
	var jet := stream("flame")
	if jet: jet.update_endpoints(point, point + direction * reach)

func vent(socket: Node3D, intake := false):
	if not is_instance_valid(socket): return
	var direction := -socket.global_basis.z.normalized()
	var point := socket.global_position + (direction * 0.22 if intake else Vector3.ZERO)
	var puff := sprite(point, Color(0.5, 0.55, 0.6, 0.5), 0.08, 0.3, 1.0)
	if puff:
		puff.velocity = direction * (-0.7 if intake else 0.7)
		puff.growth = 0.15 if intake else 0.4

func shot_smoke(socket: Node3D, shell_port := false):
	if not is_instance_valid(socket): return
	var direction := -socket.global_basis.z.normalized()
	var puff := sprite(socket.global_position + direction * 0.008, Color(0.55, 0.57, 0.6, 0.3), 0.035 if shell_port else 0.05, 0.18 if shell_port else 0.24, 1.0)
	if puff:
		puff.velocity = direction * (0.2 if shell_port else 0.35) + Vector3.UP * 0.08
		puff.growth = 0.08

func casing(socket: Node3D):
	if not is_instance_valid(socket): return
	shot_smoke(socket, true)
	var shell := make(socket.global_position, 0.6, brass_material, line_mesh)
	if not shell: return
	shell.scale = Vector3(0.007, 0.028, 0.007)
	shell.velocity = -socket.global_basis.z.normalized() * 1.6
	shell.acceleration = Vector3.DOWN * gravity
	shell.spin = Vector3(8, 12, 4)
