class_name ArenaLighting
extends RefCounted

static func environment(preview := false) -> Environment:
	var settings := Environment.new()
	settings.background_mode = Environment.BG_COLOR if preview else Environment.BG_SKY
	settings.background_color = Color("0b1119")
	settings.sky = Sky.new()
	var sky_material := ShaderMaterial.new()
	sky_material.shader = preload("res://shaders/original/lunar_sky.gdshader")
	settings.sky.sky_material = sky_material
	sky_material.set_shader_parameter("wisps",preload("res://assets/models/effects/combat_effects/turbulence_rgba.png"))
	# Share the reflection recipe, with independent mutable environment settings.
	settings.sky.process_mode = Sky.PROCESS_MODE_REALTIME
	settings.sky.sky_material = settings.sky.sky_material.duplicate()
	(settings.sky.sky_material as ShaderMaterial).set_shader_parameter("reflection_fill_energy",0.45)
	(settings.sky.sky_material as ShaderMaterial).set_shader_parameter("reflection_detail_strength",1.0)
	(settings.sky.sky_material as ShaderMaterial).set_shader_parameter("reflection_panorama",load("res://assets/textures/reflections/industrial_chrome.png"))
	settings.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = Color("a4b4cc")
	settings.ambient_light_energy = 0.26
	settings.ambient_light_sky_contribution = 0.0
	settings.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	settings.glow_enabled = true
	settings.glow_intensity = 0.12
	settings.ssao_enabled = true
	settings.ssao_radius = 0.75
	settings.ssao_intensity = 1.1
	settings.fog_enabled = not preview
	settings.fog_light_color = Color("343c4b")
	settings.fog_density = 0.0005
	settings.fog_sky_affect = 0.0
	settings.volumetric_fog_enabled = false
	settings.volumetric_fog_density = 0.0
	return settings

static func install(parent: Node, preview := false) -> WorldEnvironment:
	var world := WorldEnvironment.new()
	world.environment = environment(preview)
	parent.add_child(world)
	var moon := DirectionalLight3D.new()
	moon.name = "LGT_Key_Moon"
	moon.rotation_degrees = Vector3(-48,-32,0)
	moon.light_color = Color("c6d5ed")
	moon.light_energy = 0.28
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 110
	parent.add_child(moon)
	if preview:
		# The menu has no arena fixtures. Use real studio lights so disabling
		# raster ambient/reflection fill for RT does not leave the robot unlit.
		for spec in [
			["Key",Vector3(2.5,3.0,2.5),Color("edf3ff"),4.0,Vector2(1.6,1.6)],
			["Fill",Vector3(-2.0,1.8,1.2),Color("b8cfe8"),1.4,Vector2(1.8,1.8)],
			["Rim",Vector3(-1.2,2.5,-2.0),Color("d9e7ff"),3.0,Vector2(1.0,1.6)]]:
			var light := AreaLight3D.new()
			light.name = "LGT_Preview_" + spec[0]
			light.position = spec[1]
			light.light_color = spec[2]
			light.light_energy = spec[3]
			light.area_size = spec[4]
			light.area_range = 8.0
			light.shadow_enabled = true
			parent.add_child(light)
			var target := Vector3(0,0.9,0)
			if parent is Node3D: target = (parent as Node3D).to_global(target)
			light.look_at(target)
	return world
