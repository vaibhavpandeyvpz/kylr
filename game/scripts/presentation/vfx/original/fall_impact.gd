extends OriginalEffect
## Independently tunable grounded robot impact; immutable kit geometry is shared.
@export_range(0.0,1.0) var dust_opacity := 0.45
@export_range(0.1,2.0) var dust_size := 0.7
@export_range(0.1,2.0) var impact_duration := 0.65

func build_combustion_impact() -> void:
	duration = impact_duration
	build_grenade_3d()

func build_grenade_3d() -> void:
	var shader := preload("res://shaders/original/combustion_cloud_3d.gdshader")
	add_spherical_cloud("ImpactDust",shader,3,0.45,0.12,dust_size*1.8,0.0,dust_opacity)
	add_gas_lobe("IgnitionCore",shader,2,Vector3(0,0.05,0),0.55,0,0)
