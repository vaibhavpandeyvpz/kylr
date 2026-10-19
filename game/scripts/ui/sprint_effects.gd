class_name SprintEffects
extends Control
var strength := 0.0
var phase := 0.0
var lines_enabled := true
var blur: ColorRect
var effect: ShaderMaterial

func _ready():
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	blur = ColorRect.new()
	blur.mouse_filter = Control.MOUSE_FILTER_IGNORE
	blur.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	effect = ShaderMaterial.new()
	effect.shader = preload("res://shaders/sprint_blur.gdshader")
	blur.material = effect
	add_child(blur)

func update_sprint(robot: ArenaRobot, options: Dictionary, enabled: bool, dt: float):
	var target := 0.0
	if enabled and is_instance_valid(robot) and robot.can_act() and robot.wants_sprint and robot.ep > ArenaTuning.HALF_EP and not options.reduced_motion:
		target = clampf((Vector2(robot.velocity.x,robot.velocity.z).length()-8.0)/4.0,0,1)
	strength = move_toward(strength,target,dt*5.0)
	if options.reduced_motion or not enabled: strength = 0.0
	phase = fmod(phase+dt*1.8,1.0)
	lines_enabled = options.speed_lines
	effect.set_shader_parameter("intensity",strength*float(options.sprint_blur))
	blur.visible = strength > 0.001 and float(options.sprint_blur)>0.0
	queue_redraw()

func _draw():
	if not lines_enabled or strength <= 0.001: return
	var center := size*0.5
	for i in 28:
		var angle := TAU*float(i)/28.0
		var direction := Vector2(cos(angle),sin(angle))
		var radius := 0.82+fmod(float(i)*0.37+phase,1.0)*0.28
		var edge := minf(size.x*0.5/maxf(absf(direction.x),0.001),size.y*0.5/maxf(absf(direction.y),0.001))
		var outer := center + direction*edge*radius
		var inner := center + direction*edge*(radius-0.08)
		draw_line(inner,outer,Color(0.75,0.88,0.92,0.18*strength),1.5,true)
