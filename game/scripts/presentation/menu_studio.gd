class_name MenuStudio
extends RefCounted
## Menu portraits share lighting; their 3D resolution follows the display setting.
static func create(tree: SceneTree, dimensions: Vector2i, transparent := true) -> SubViewport:
	var viewport := SubViewport.new()
	viewport.name = "MenuPortraitStudio"
	viewport.size = dimensions
	viewport.world_3d = World3D.new()
	viewport.transparent_bg = transparent
	viewport.msaa_3d = Viewport.MSAA_4X
	viewport.scaling_3d_scale = float(tree.root.get_meta("render_resolution_scale",1.0))
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	tree.root.add_child(viewport)
	ArenaLighting.install(viewport,true)
	return viewport

static func fitted_dimensions(area: Vector2, density: Vector2, aspect := Vector2(560,640)) -> Vector2i:
	var scale:=minf(area.x/aspect.x,area.y/aspect.y)
	return Vector2i((aspect*scale*density).round()).max(Vector2i.ONE)

static func fit_to_control(viewport: SubViewport, control: Control) -> void:
	if not is_instance_valid(viewport) or not control.is_inside_tree(): return
	var window:=control.get_window()
	var density:=window.get_stretch_transform().get_scale()*control.get_global_transform_with_canvas().get_scale().abs()
	viewport.size=fitted_dimensions(control.size,density)
	viewport.scaling_3d_scale=float(window.get_meta("render_resolution_scale",1.0))
