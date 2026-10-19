class_name FixtureLighting
extends RefCounted
## Physical luminaires follow the native projection sockets, including moving heads.

static func attach(projection: Node3D, light: Light3D, kind: String, offset: float) -> Light3D:
	if projection.has_node("FixtureIllumination"):
		light.free()
		return projection.get_node("FixtureIllumination") as Light3D
	light.name="FixtureIllumination"
	light.set_meta("fixture_light",true)
	light.set_meta("fixture_kind",kind)
	light.light_color=Color("e6f3ff")
	light.shadow_bias=.03
	light.shadow_normal_bias=1.0 if light is AreaLight3D else .4
	light.position.z=-offset
	configure(light,false,false)
	projection.add_child(light)
	return light

static func area(projection: Node3D, kind: String, range_m: float) -> Light3D:
	var light := AreaLight3D.new()
	light.area_size=Vector2(1.1,.16) if kind=="batten_light" else Vector2(.36,.22)
	light.area_range=range_m
	light.light_energy=1.8 if kind=="batten_light" else 1.2
	light.light_size=.12
	return attach(projection,light,kind,.02 if kind=="batten_light" else .055)

static func spot(projection: Node3D, kind: String, spec: Dictionary) -> Light3D:
	var light := SpotLight3D.new()
	light.spot_angle=float(spec.cone_half_angle_deg)
	light.spot_range=float(spec.range_m)
	light.spot_attenuation=1.0
	light.spot_angle_attenuation=1.0
	light.light_energy=4.0 if kind=="jumbotron" else 2.2
	light.light_size=.12
	return attach(projection,light,kind,.04)

static func configure(light: Light3D, enabled: bool, shadows: bool) -> void:
	light.visible=enabled
	light.light_cull_mask=0xfffff if enabled else 0
	light.shadow_enabled=enabled and shadows
