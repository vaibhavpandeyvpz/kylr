extends GutTest

func test_weapon_deliveries_use_authored_pbr_without_baked_finish_maps():
	for weapon in ContentRegistry.weapons():
		for suffix in ["", "_ammo", "_rocket", "_grenade"]:
			var path := "res://assets/models/weapons/%s/%s%s.glb" % [weapon,weapon,suffix]
			if not ResourceLoader.exists(path): continue
			var model: Node = load(path).instantiate()
			for mesh in model.find_children("*","MeshInstance3D",true,false):
				for surface in mesh.mesh.get_surface_count():
					var material := mesh.mesh.surface_get_material(surface) as StandardMaterial3D
					assert_not_null(material,path)
					if material == null: continue
					for channel in [BaseMaterial3D.TEXTURE_ALBEDO,BaseMaterial3D.TEXTURE_METALLIC,BaseMaterial3D.TEXTURE_ROUGHNESS,BaseMaterial3D.TEXTURE_NORMAL,BaseMaterial3D.TEXTURE_AMBIENT_OCCLUSION]:
						assert_null(material.get_texture(channel),path+": "+material.resource_name)
			model.free()

class ChargeWorld extends Node3D:
	var phase := "Active"
	var first_person
	var local_robot

class ChargeRobot extends ArenaRobot:
	func _ready():
		set_process(false)
		set_physics_process(false)

class ChargeView extends Node3D:
	var weapon_id := "lightning_gun"
	var gun: Node3D

class EffectsServer extends ArenaMatch:
	func _ready():
		set_process(false)
		set_physics_process(false)

class FlightCombat extends ArenaCombat:
	var sweep_origin := Vector3.ZERO
	func projectile_hit(projectile: Node3D, _motion: Vector3, _exclude: Array = []) -> Dictionary:
		sweep_origin = projectile.global_position
		return {}
	func ray(from: Vector3, _to: Vector3, _exclude: Array = [], _mask := 5) -> Dictionary:
		sweep_origin = from
		return {}

func test_fpv_projectiles_launch_from_camera_muzzle_without_moving_world_sweeps():
	var world := EffectsServer.new()
	add_child_autofree(world)
	world.phase = "Active"
	world.camera = Camera3D.new()
	world.add_child(world.camera)
	world.camera.position = Vector3(0, 5, 0)
	world.combat = FlightCombat.new(world)
	world.effects = ArenaEffects.new()
	world.effects.game = world
	world.add_child(world.effects)
	var robot := ChargeRobot.new()
	robot.arena_match = world
	robot.character = ContentRegistry.character(robot.character_id)
	robot.human = true
	robot.protection = 0
	world.add_child(robot)
	world.local_robot = robot
	robot.weapon_vfx = WeaponVfx.new()
	robot.weapon_vfx.robot = robot
	robot.add_child(robot.weapon_vfx)
	robot.weapon_vfx.set_process(false)
	world.first_person = FirstPersonRig.new()
	world.first_person.robot = robot
	world.first_person.camera = world.camera
	world.add_child(world.first_person)
	world.first_person.set_process(false)
	for weapon in ["rocket_launcher", "emp_gun", "lightning_gun", "flamethrower"]:
		robot.equipped = weapon
		if robot.gun: robot.gun.free()
		robot.gun = Assets.model("weapons", weapon)
		robot.add_child(robot.gun)
		robot.gun.position = Vector3(-2, 1, -1)
		world.combat.launch(robot, weapon)
		var projectile: ArenaProjectile = world.get_children().filter(func(node): return node is ArenaProjectile)[0]
		projectile.set_physics_process(false)
		var world_origin := robot.muzzle()
		var view_origin := robot.weapon_vfx.origin()
		assert_gt(view_origin.distance_to(world_origin), 1.0, weapon)
		assert_almost_eq(projectile.global_position, world_origin, Vector3.ONE * 0.001, "Authority retains the robot muzzle")
		assert_almost_eq(projectile.visual.global_position, view_origin, Vector3.ONE * 0.001, weapon + " starts at FPV muzzle")
		var component: Dictionary = ProjectileCollision.shapes(weapon)[0]
		var volume_pose := ProjectileCollision.local_pose(projectile,component)
		projectile.visual.position += Vector3(1,2,3)
		assert_almost_eq(ProjectileCollision.local_pose(projectile,component).origin,volume_pose.origin,Vector3.ONE*0.0001,"Cosmetic view offset cannot enter volume placement")
		projectile.update_presentation()
		projectile._physics_process(0.01)
		assert_almost_eq(world.combat.sweep_origin, world_origin, Vector3.ONE * 0.001, "FPV cannot move collision sweeps")
		world.third_person = true
		projectile.update_presentation()
		assert_almost_eq(projectile.visual.global_position, projectile.global_position, Vector3.ONE * 0.001, "TPV uses world flight")
		world.third_person = false
		projectile.distance = projectile.view_start_distance + projectile.view_convergence_distance
		projectile.update_presentation()
		assert_almost_eq(projectile.visual.global_position, projectile.global_position, Vector3.ONE * 0.001, "View flight converges at target")
		projectile.distance = 0
		world.local_robot = null
		projectile.update_presentation()
		assert_almost_eq(projectile.visual.global_position, projectile.global_position, Vector3.ONE * 0.001, "Other observers use world flight")
		world.local_robot = robot
		projectile.free()

func test_fire_orb_uses_original_compact_thermal_surface():
	var orb := FireOrb.new()
	add_child_autofree(orb)
	assert_eq(orb.composition.kind,"orb")
	assert_almost_eq(orb.composition.scale.x,Arsenal.ORB_DIAMETER,0.0001)
	for mesh in orb.composition.find_children("*","MeshInstance3D",true,false):
		assert_true(mesh.mesh is ArrayMesh)
		var size: Vector3 = mesh.get_aabb().size
		var world_size: Vector3 = mesh.global_basis.x.abs()*size.x + mesh.global_basis.y.abs()*size.y + mesh.global_basis.z.abs()*size.z
		for extent in [world_size.x,world_size.y,world_size.z]:
			assert_lte(extent,Arsenal.ORB_DIAMETER*1.1,"Every transformed layer stays within the compact projectile budget")
	for material in PackVfx.materials(orb.composition):
		assert_true(material.shader.resource_path.begins_with("res://shaders/original/"))
		assert_almost_eq(float(material.get_shader_parameter("emission")),0.8,0.001)

func test_rocket_tail_uses_bounded_original_plume_on_exhaust_axis():
	var projectile := ArenaProjectile.new()
	add_child_autofree(projectile)
	projectile.set_physics_process(false)
	var socket := Assets.socket(projectile.visual,"Exhaust")
	var tail := socket.get_child(0) as NozzleExhaust
	assert_eq(tail.plume.kind,"exhaust")
	assert_almost_eq(tail.flame_diameter_m,0.05,0.0001)
	assert_almost_eq(tail.length_m,0.15,0.0001)
	for travel in [Vector3.LEFT,Vector3.UP,Vector3.FORWARD]:
		projectile.orient_to_flight(travel)
		tail._process(0)
		assert_almost_eq(tail.plume.global_position,socket.global_position,Vector3.ONE * 0.001)
		assert_lt(tail.plume.global_basis.y.normalized().dot(travel),-0.99,"Plume trails behind flight, including vertical shots")
	var mesh := tail.plume.get_node("ThermalPlume0") as MeshInstance3D
	assert_almost_eq(mesh.custom_aabb.size.y,tail.length_m,0.0001)
	assert_lte(mesh.custom_aabb.size.x,tail.flame_diameter_m + 0.00001)
	assert_eq(tail.plume.find_children("*","Light3D",true,false).size(),0,"No bright nozzle halo")

func test_original_fireball_contact_replicates_with_bounded_pool():
	var server := EffectsServer.new()
	add_child_autofree(server)
	server.replicating = true
	server.authority = true
	var effects := ArenaEffects.new()
	server.add_child(effects)
	effects.game = server
	effects.fire_contact(Vector3.ONE, Vector3.LEFT)
	assert_eq(server.presentation_events[0].kind, "fire_orb")
	assert_eq(effects.fire_orb_pool.size(), 0)
	server.authority = false
	for index in 32: effects.fire_contact(Vector3.ONE, Vector3.LEFT)
	assert_eq(effects.fire_orb_pool.size(), ArenaEffects.MAX_SPARK_BURSTS)
	assert_true(effects.fire_orb_pool[0].scene.resource_path.ends_with("original/fire_hit.tscn"))
	for emitter in effects.fire_orb_pool[0].effect.find_children("*", "GPUParticles3D", true, false):
		assert_true(emitter.local_coords, "Contact particles inherit the compact impact scale")
	assert_eq(effects.lightning_pool.size(), 0)
	effects.explosion(Vector3.ZERO, Vector3.UP)
	assert_true(effects.rocket_pool[0].scene.resource_path.ends_with("original/rocket.tscn"), "Rocket and fire contacts use independent original compositions")

func test_pilot_fire_tracks_gas_jet_and_muzzle_reuses_flame_and_retires():
	var world := ChargeWorld.new()
	add_child_autofree(world)
	var robot := ChargeRobot.new()
	world.add_child(robot)
	robot.arena_match = world
	robot.equipped = "flamethrower"
	robot.gun = Assets.model("weapons", "flamethrower")
	world.add_child(robot.gun)
	var vfx := WeaponVfx.new()
	vfx.robot = robot
	robot.add_child(vfx)
	vfx.set_process(false)
	vfx.set_physics_process(false)
	vfx.update_pilot()
	var pilot := vfx.pilot
	assert_not_null(pilot)
	assert_same(pilot.get_parent(), Assets.socket(robot.gun, "PilotFlame"))
	assert_eq(pilot.plume.plume.kind,"exhaust")
	assert_eq(pilot.plume.plume.find_children("*","Light3D",true,false).size(),0)
	assert_eq(pilot.plume.plume.find_children("*","GPUParticles3D",true,false).size(),0,"No flying ember tail on the gas pilot")
	for firing in [false, true]:
		robot.streaming = firing
		robot.reload_time = 0.5
		robot.gun.position += Vector3.ONE
		vfx.update_pilot()
		assert_same(vfx.pilot, pilot)
		var direction := (Assets.socket(robot.gun, "Muzzle").global_position - pilot.global_position).normalized()
		assert_almost_eq(-pilot.plume.global_basis.z.dot(direction), 1.0, 0.001)
		assert_lt(pilot.plume.length_m, pilot.global_position.distance_to(Assets.socket(robot.gun, "Muzzle").global_position), "Pilot ends before the muzzle")
	robot.equipped = "pistol"
	vfx.update_pilot()
	assert_null(vfx.pilot)
	assert_false(pilot.visible)
	assert_true(pilot.is_queued_for_deletion())

func test_receptor_sparks_follow_visible_gizmos_while_loaded_idle_firing_and_reloading():
	var world := ChargeWorld.new()
	add_child_autofree(world)
	var robot := ChargeRobot.new()
	world.add_child(robot)
	robot.arena_match = world
	robot.equipped = "lightning_gun"
	robot.loaded = 1
	robot.gun = Assets.model("weapons", "lightning_gun")
	world.add_child(robot.gun)
	var vfx := WeaponVfx.new()
	vfx.robot = robot
	robot.add_child(vfx)
	vfx.set_process(false)
	vfx.set_physics_process(false)
	vfx.update_receptor_sparks()
	assert_eq(vfx.receptor_sparks.size(), 3, "Idle weapon glows at all three receptor gizmos")
	var first := vfx.receptor_sparks[0]
	for firing in [false, true]:
		robot.streaming = firing
		robot.reload_time = 0.5
		robot.gun.position += Vector3.ONE
		vfx.update_receptor_sparks()
		assert_same(vfx.receptor_sparks[0], first, "Firing and reload reuse the continuous effect")
		for index in 3:
			var tip := Assets.socket(robot.gun, "ArcTip" + str(index + 1))
			assert_eq(vfx.receptor_sparks[index].global_position, tip.global_position)
			for emitter in vfx.receptor_sparks[index].emitters:
				assert_true(emitter.emitting)
				assert_true(emitter.local_coords)
	var view := ChargeView.new()
	world.add_child(view)
	view.gun = Assets.model("weapons", "lightning_gun")
	view.add_child(view.gun)
	world.first_person = view
	world.local_robot = robot
	vfx.update_receptor_sparks()
	assert_true(first.is_queued_for_deletion(), "Camera switch retires the former gun effects")
	assert_false(first.visible)
	assert_same(vfx.receptor_sparks[0].get_parent(), Assets.socket(view.gun, "ArcTip1"))
	robot.loaded = 0
	vfx.update_receptor_sparks()
	assert_eq(vfx.receptor_sparks.size(), 0, "Empty weapon stops sparks even during fire")
	robot.loaded = 1
	vfx.update_receptor_sparks()
	assert_eq(vfx.receptor_sparks.size(), 3, "Loaded ammo restores sparks")
	robot.alive = false
	vfx.update_receptor_sparks()
	assert_eq(vfx.receptor_sparks.size(), 0, "Death retires sparks")
	robot.alive = true
	robot.equipped = "pistol"
	vfx.update_receptor_sparks()
	assert_eq(vfx.receptor_sparks.size(), 0, "Unequipped lightning gun emits nothing")

func test_lightning_contacts_reuse_bounded_pool_and_face_out_of_surface():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	for i in 80: effects.electric_contact(Vector3.ZERO, Vector3.LEFT)
	assert_eq(effects.lightning_pool.size(), ArenaEffects.MAX_SPARK_BURSTS)
	assert_eq(effects.spark_pool.size(), 0, "Lightning contacts use curved dissolving meshes")
	var burst := effects.lightning_pool[0]
	assert_almost_eq(burst.global_basis.y.dot(Vector3.LEFT), 1.0, 0.001)
	for emitter in burst.emitters:
		assert_true(emitter.one_shot)
		assert_same(emitter.material_override, LightningOrb.lightning_material)
		assert_eq(emitter.amount, 6)
	await wait_seconds(0.6)
	assert_false(burst.visible)
	effects.electric_contact(Vector3.ONE, Vector3.ZERO)
	assert_same(effects.lightning_pool[0], burst)
	assert_eq(effects.lightning_pool.size(), ArenaEffects.MAX_SPARK_BURSTS)
	assert_eq(burst.global_position, Vector3.ONE + Vector3.UP * 0.015)

func test_orb_contact_replicates_without_server_particles_or_duplicate_stream_events():
	var server := EffectsServer.new()
	add_child_autofree(server)
	server.replicating = true
	server.authority = true
	var effects := ArenaEffects.new()
	server.add_child(effects)
	effects.game = server
	effects.electric_contact(Vector3.ONE, Vector3.UP, true)
	assert_eq(server.presentation_events.size(), 1)
	assert_eq(server.presentation_events[0].kind, "electric")
	effects.electric_contact(Vector3.ZERO, Vector3.UP)
	assert_eq(server.presentation_events.size(), 1, "Stream contacts remain snapshot presentation")
	assert_eq(effects.lightning_pool.size(), 0, "Dedicated server allocates no lightning emitters")
	server.authority = false
	server.effects = effects
	var transport := OnlineTransport.new()
	transport.game = server
	transport.apply_presentation(server.presentation_events[0])
	assert_eq(effects.lightning_pool.size(), 1, "Client presents the accepted orb contact event")
	transport.free()

func test_lightning_mesh_particles_follow_snapshot_motion_and_retire_with_projectile():
	var projectile := ArenaProjectile.new()
	projectile.weapon = "lightning_gun"
	add_child(projectile)
	projectile.set_physics_process(false)
	var lightning: Array[GPUParticles3D] = []
	var total := 0
	for child in projectile.visual.get_children():
		if child is GPUParticles3D and child.name.begins_with("Lightning"):
			lightning.append(child)
			total += child.amount
	assert_eq(total, 10, "Lightning remains bounded per orb")
	for direction in [Vector3.UP, Vector3.LEFT, Vector3.FORWARD]:
		projectile.position += direction * 5.0
		projectile.orient_to_flight(direction)
		for emitter in lightning:
			assert_true(emitter.local_coords, "Particles move with the replicated orb instead of trailing stale positions")
			assert_lt(emitter.global_position.distance_to(projectile.global_position), 0.0001)
	var references: Array[WeakRef] = []
	for emitter in lightning: references.append(weakref(emitter))
	projectile.free()
	for reference in references: assert_null(reference.get_ref(), "Orb removal retires its emitters")

func test_emp_charge_tracks_flight_including_vertical_shots():
	for direction in [Vector3.LEFT, Vector3.RIGHT, Vector3.FORWARD, Vector3.UP, Vector3.DOWN, Vector3(1, 2, -3).normalized()]:
		var pulse := ArenaProjectile.new()
		pulse.weapon = "emp_gun"
		pulse.direction = direction
		add_child(pulse)
		pulse.set_physics_process(false)
		assert_true(pulse.visual is EmpCharge)
		var charge := pulse.visual as EmpCharge
		assert_gt(absf(charge.shell.global_basis.y.normalized().dot(direction)), 0.9999, "Long shell axis follows flight")
		pulse.distance = 10
		pulse.update_emp_visual()
		pulse.orient_to_flight(-direction)
		assert_gt(absf(charge.shell.global_basis.y.normalized().dot(direction)), 0.9999, "Expansion preserves replicated orientation")
		pulse.free()

func test_emp_charged_contacts_reuse_bounded_pool_and_finish_without_smoke():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	for i in 80: effects.emp_contact(Vector3.ZERO, Vector3.LEFT)
	assert_eq(effects.emp_pool.size(), ArenaEffects.MAX_SPARK_BURSTS)
	var burst := effects.emp_pool[0]
	assert_false(burst.effect.get_node("Smoke").visible)
	assert_not_null(burst.refraction, "EMP has a refracting and blurring volume")
	assert_almost_eq(burst.global_basis.y.normalized().dot(Vector3.LEFT), 1.0, 0.001)
	for material in PackVfx.materials(burst.effect):
		var color = material.get_shader_parameter("primary_color")
		if color is Color:
			assert_almost_eq(color.r, color.b, 0.001, "EMP stays neutral grey")
			assert_almost_eq(color.r, color.g, 0.001)
	for entry in effects.emp_pool: entry._process(10.0)
	assert_false(burst.visible)
	effects.emp_contact(Vector3.ONE, Vector3.ZERO)
	assert_same(effects.emp_pool[0], burst)
	assert_eq(burst.global_position, Vector3.ONE + Vector3.UP * 0.015)
	assert_eq(effects.emp_pool.size(), ArenaEffects.MAX_SPARK_BURSTS)
func test_emp_charged_contact_replicates_without_server_renderers():
	var server := EffectsServer.new()
	add_child_autofree(server)
	server.replicating = true
	server.authority = true
	var effects := ArenaEffects.new()
	server.add_child(effects)
	effects.game = server
	effects.emp_contact(Vector3.ONE, Vector3.UP)
	assert_eq(server.presentation_events.size(), 1)
	assert_eq(server.presentation_events[0].kind, "emp")
	assert_eq(effects.emp_pool.size(), 0)
	server.authority = false
	server.effects = effects
	var transport := OnlineTransport.new()
	transport.game = server
	transport.apply_presentation(server.presentation_events[0])
	assert_eq(effects.emp_pool.size(), 1)
	transport.free()

func test_emp_charge_keeps_half_size_fades_after_twenty_metres_and_retires_both_layers():
	var pulse := ArenaProjectile.new()
	pulse.weapon = "emp_gun"
	add_child_autofree(pulse)
	pulse.set_physics_process(false)
	var charge := pulse.visual as EmpCharge
	assert_eq(charge.get_child_count(), 2, "Emissive core plus distorted charge shell")
	assert_same(charge.shell_material.shader, EmpCharge.SHELL)
	assert_eq(charge.shell_material.get_shader_parameter("primary_color"), EmpCharge.PRIMARY)
	assert_eq(charge.shell_material.get_shader_parameter("emission_energy"), EmpCharge.EMISSION)
	var shell := charge.shell
	var core_reference: WeakRef = weakref(charge.core)
	var shell_reference: WeakRef = weakref(shell)
	assert_true(shell.mesh is ArrayMesh, "Charge uses the authored smooth envelope")
	assert_same(shell.get_node("InductionFilaments").material_override, charge.shell_material)
	for travelled in [0.0, 5.0, 10.0, 20.0, 22.5, 25.0]:
		pulse.distance = travelled
		pulse.update_emp_visual()
		assert_same(charge.shell, shell, "Travel updates reuse meshes")
		var envelope: AABB = shell.transform * shell.mesh.get_aabb()
		assert_almost_eq(envelope.size.x * charge.scale.x, 0.06, 0.0001)
		assert_almost_eq(envelope.size.z * charge.scale.z, 0.15, 0.0001)
		var opacity := clampf((25.0 - travelled) / 5.0, 0, 1)
		assert_almost_eq(charge.core_material.albedo_color.a, opacity, 0.0001)
		assert_almost_eq(float(charge.shell_material.get_shader_parameter("opacity")), opacity, 0.0001)
		assert_eq(charge.visible, travelled < 25)
	pulse.free()
	assert_null(core_reference.get_ref(), "Removal retires the charge core")
	assert_null(shell_reference.get_ref(), "Removal retires the charge shell")

func test_rocket_impact_orients_volumes_to_incoming_path_and_reuses_pool():
	for incoming in [Vector3.DOWN, Vector3.LEFT, Vector3(1, -1, -1).normalized(), Vector3.UP]:
		var effects := ArenaEffects.new()
		add_child(effects)
		var normal: Vector3 = Vector3.UP if incoming.y < 0 else -incoming
		effects.explosion(Vector3.ZERO, normal, 1.3, incoming)
		assert_eq(effects.rocket_pool.size(), 1)
		var burst := effects.rocket_pool[0]
		assert_gt(burst.global_basis.y.normalized().dot(-incoming), 0.999)
		for decal in burst.effect.find_children("*", "Decal", true, false):
			assert_false(decal.visible, "Explosion cannot stain robot surfaces")
		assert_eq(burst.effect.scene_file_path, "res://assets/effects/original/rocket.tscn")
		burst._process(10.0)
		assert_false(burst.visible)
		effects.explosion(Vector3.ZERO, normal, 1.3, incoming)
		assert_same(effects.rocket_pool[0], burst)
		effects.free()
func test_weapon_effect_sockets_exist_and_face_out_of_barrels():
	var fixtures := {
		"pistol": ["Muzzle", "ShellEject", "CompVent", "HookVent"],
		"rifle": ["Muzzle", "ShellEject", "ScopeEye", "Flashlight"],
		"minigun": ["Muzzle1", "Muzzle2", "Muzzle3", "Muzzle4", "Muzzle5", "Muzzle6", "ShellEject"],
		"rocket_launcher": ["Muzzle1", "Muzzle2", "Muzzle3", "Backblast"],
		"lightning_gun": ["Muzzle", "ArcTip1", "ArcTip2", "ArcTip3", "VentLeft", "VentRight"],
		"flamethrower": ["Muzzle", "PilotFlame", "FumeVent"],
		"emp_gun": ["Muzzle", "AirIntake", "VentLeft", "VentRight"]}
	for weapon in fixtures:
		var model := Assets.model("weapons", weapon)
		add_child_autofree(model)
		for id in fixtures[weapon] + ["RightHandSocket", "LeftHandSocket", "AmmoHandSocket", "AmmoMount"]:
			var socket := Assets.socket(model, id)
			assert_not_null(socket, weapon + "/" + id)
			if socket and id.begins_with("Muzzle"):
				assert_gt((-socket.global_basis.z.normalized()).dot(Vector3.BACK), 0.95, weapon + " muzzle must point along imported geometry +Z")
	var rocket := Assets.model("weapons", "rocket_launcher", "_rocket")
	add_child_autofree(rocket)
	assert_not_null(Assets.socket(rocket, "Exhaust"))
	assert_not_null(Assets.socket(rocket, "Warhead"))

func test_effect_budget_and_socket_cleanup():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var socket := Node3D.new()
	add_child(socket)
	effects.muzzle(socket, "pistol")
	assert_eq(effects.muzzle_pool.size(), 1)
	socket.free()
	await wait_process_frames(2)
	assert_false(effects.muzzle_pool[0].visible, "Destroyed sockets retire attached flashes")
	for i in 200: effects.burst(Vector3.ZERO, Color.WHITE, 0.1)
	assert_eq(effects.count, ArenaEffects.MAX_EFFECTS)
	await wait_seconds(0.4)
	assert_eq(effects.count, 0, "Expired effects return the complete budget")

func test_authored_muzzle_cards_and_glow_point_forward_for_rotated_sockets():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var socket := Node3D.new()
	add_child_autofree(socket)
	for angles in [Vector3.ZERO, Vector3(PI / 2, 0, 0), Vector3(0.4, 1.7, -0.5)]:
		socket.rotation = angles
		for weapon in ["pistol", "rifle", "minigun", "rocket_launcher"]:
			effects.muzzle(socket, weapon)
			var burst: PackBurst
			for candidate in effects.muzzle_pool:
				if candidate.remaining > 0: burst = candidate
			var forward := -socket.global_basis.z.normalized()
			var gas := burst.effect.get_node("Gas0") as MeshInstance3D
			assert_gt(gas.global_basis.y.normalized().dot(forward),0.999)
			assert_gt((gas.global_position-socket.global_position).dot(forward),0.0,"Flash extends beyond the barrel")
			assert_almost_eq(gas.custom_aabb.size.y * gas.global_basis.y.length(),effects.MUZZLE_LENGTHS[weapon],0.001)
			burst._process(10.0)

func test_bullet_atlas_marks_follow_moving_surfaces_and_expire():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var surface := Node3D.new()
	add_child_autofree(surface)
	effects.impact(Vector3.ZERO, Vector3.UP, false, surface)
	assert_eq(effects.decals.size(), 1)
	var mark := effects.decals[0]
	var cell: int = mark.get_instance_shader_parameter("atlas_cell")
	assert_between(cell, 0, 63)
	assert_almost_eq(mark.global_basis.z.normalized().dot(Vector3.UP), 1.0, 0.001)
	surface.position = Vector3(2, 3, 4)
	mark._process(0)
	assert_lt(mark.global_position.distance_to(surface.position + Vector3.UP * 0.003), 0.001)
	mark._process(10.01)
	assert_true(mark.is_queued_for_deletion())

func test_impact_sparks_reuse_a_bounded_gpu_pool_under_automatic_fire():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	for i in 80: effects.sparks(Vector3.ZERO,Vector3.UP)
	assert_eq(effects.spark_pool.size(),ArenaEffects.MAX_SPARK_BURSTS)
	assert_eq(effects.count,0,"Spark density does not consume the muzzle/impact mesh budget")
	await wait_seconds(0.5)
	effects.sparks(Vector3.ONE,Vector3.UP,true)
	assert_eq(effects.spark_pool.size(),ArenaEffects.MAX_SPARK_BURSTS,"Finished GPU emitters are reused")
	assert_eq(effects.spark_pool[0].global_position,Vector3.ONE)

func test_stream_reuses_layers_reaches_endpoint_and_releases_budget():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var beam := effects.stream("lightning")
	var target := Vector3(5, 2, -7)
	beam.update_endpoints(Vector3.ZERO, target)
	var core: MeshInstance3D = beam.layers[0].node
	assert_lt(core.to_global(Vector3.UP * 0.5).distance_to(target), 0.001)
	assert_gt(float(beam.layers[0].material.get_shader_parameter("core_continuity")), 0.0)
	var meshes := beam.layers.size()
	beam.update_endpoints(Vector3.ONE, Vector3(0, 5, 0))
	assert_eq(beam.layers.size(), meshes, "Endpoint updates reuse the same meshes")
	beam.release()
	for entry in beam.layers: assert_false(entry.node.visible)
	await wait_seconds(1.15)
	assert_eq(effects.stream_count, 0)

func test_original_flame_tracks_segment_reuses_geometry_and_stops():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var flame := effects.stream("flame")
	var source := flame.pack_beam as OriginalEffect
	assert_not_null(source)
	assert_null(flame.pack_fire)
	var core := source.get_node("ThermalPlume0") as MeshInstance3D
	var mesh := core.mesh
	for point in [Vector3(10,0,0),Vector3(0,15,0),Vector3(2,-1,-3)]:
		flame.update_endpoints(Vector3.ZERO,point)
		assert_almost_eq(float(core.material_override.get_shader_parameter("start_radius")),0.035,0.0001)
		assert_almost_eq(float(core.material_override.get_shader_parameter("end_radius")),0.12,0.0001)
		assert_lt(source.to_global(Vector3.ZERO).length(),0.001,"Narrow end stays at nozzle")
		var length_m := float(core.material_override.get_shader_parameter("beam_length"))
		assert_gt(length_m, 0.0)
		assert_lte(length_m, point.length(), "Continuous ignition remains inside the hit segment")
		for emitter in source.emitters:
			assert_true(emitter.visibility_aabb.has_point(Vector3.UP*point.length()), "Projected gas bounds include the contact")
		assert_same(core.mesh,mesh,"Changing endpoints reuses the geometry resource")
		assert_same(flame.pack_beam,source)
		for material in flame.beam_materials:
			assert_true(material.get_shader_parameter("clip_enabled"))
			assert_eq(material.get_shader_parameter("clip_origin"),Vector3.ZERO)
			assert_almost_eq(float(material.get_shader_parameter("clip_length")),point.length(),0.0001)
	flame.release()
	assert_false(source.visible)
	var exhaust := effects.stream("exhaust")
	assert_true(exhaust.pack_fire is OriginalEffect)
	assert_null(exhaust.pack_beam)
	exhaust.release()

func test_beam_sparkles_track_outer_strands_reuse_emitters_and_stop_on_release():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var beam := effects.stream("lightning")
	assert_eq(beam.strand_sparks.size(), 2)
	for end in [Vector3(0, 0, -25), Vector3(0, 5, 0), Vector3(2, -1, 3)]:
		beam.update_endpoints(Vector3.ZERO, end)
		for emitter in beam.strand_sparks:
			assert_almost_eq(float(emitter.process_material.get_shader_parameter("beam_length")), end.length(), 0.0001)
			assert_eq(emitter.process_material.get_shader_parameter("strand_seed_1"), beam.layers[1].material.get_shader_parameter("arc_seed"))
			assert_eq(emitter.process_material.get_shader_parameter("strand_seed_2"), beam.layers[2].material.get_shader_parameter("arc_seed"))
	assert_eq(beam.strand_sparks.size(), 2, "Changing aim and reach reuses the emitters")
	beam.release()
	for emitter in beam.strand_sparks:
		assert_false(emitter.emitting)
		assert_false(emitter.visible, "No surrounding lightning survives trigger release")
