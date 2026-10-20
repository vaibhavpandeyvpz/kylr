extends CanvasLayer
signal raster_requested
## Lightweight enough to draw before the application's resource graph is loaded.
var canvas: ColorRect
var spinner: Spinner
var caption: Label
var elapsed := 0.0
var reduced_motion := false
var last_tick_usec := 0
var max_frame_gap_ms := 0.0

class Spinner extends Control:
	var phase := 0.0
	func _draw() -> void:
		var center := size*0.5
		draw_arc(center,18,0,TAU,64,MenuSkin.RAISED,3,true)
		draw_arc(center,18,phase,phase+PI*1.4,48,MenuSkin.ACTION,3,true)

func _ready() -> void:
	layer=1000
	process_mode=Node.PROCESS_MODE_ALWAYS
	canvas=ColorRect.new()
	canvas.theme=MenuSkin.make_theme()
	canvas.color=MenuSkin.CANVAS
	canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	canvas.mouse_filter=Control.MOUSE_FILTER_STOP
	add_child(canvas)
	spinner=Spinner.new()
	spinner.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	spinner.position=Vector2(-32,-32)
	spinner.size=Vector2(64,64)
	canvas.add_child(spinner)
	caption=Label.new()
	caption.text="Loading…"
	caption.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	caption.add_theme_color_override("font_color",MenuSkin.MUTED)
	caption.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	caption.position=Vector2(-160,42)
	caption.size=Vector2(320,32)
	canvas.add_child(caption)

func begin(text := "Loading…") -> void:
	last_tick_usec=Time.get_ticks_usec()
	max_frame_gap_ms=0.0
	caption.text=text
	canvas.show()
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE

func finish() -> void:
	canvas.hide()
	for button in canvas.find_children("*","Button",false,false): button.queue_free()
	spinner.show()

func offer_raster() -> void:
	spinner.hide()
	caption.text="Ray tracing could not finish preparing."
	var button := Button.new()
	button.text="CONTINUE WITH RASTER LIGHTING"
	button.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	button.position=Vector2(-180,88)
	button.size=Vector2(360,44)
	MenuSkin.apply_button(button)
	canvas.add_child(button)
	button.pressed.connect(func(): raster_requested.emit())
	button.grab_focus()

func _process(dt: float) -> void:
	if not canvas or not canvas.visible: return
	var now := Time.get_ticks_usec()
	if last_tick_usec>0: max_frame_gap_ms=maxf(max_frame_gap_ms,(now-last_tick_usec)/1000.0)
	last_tick_usec=now
	elapsed+=dt
	spinner.phase=0.0 if reduced_motion else elapsed*4.0
	spinner.queue_redraw()

func paint() -> void:
	if DisplayServer.get_name()=="headless":
		await get_tree().process_frame
	else:
		await RenderingServer.frame_post_draw

func _input(_event: InputEvent) -> void:
	if canvas and canvas.visible and spinner.visible: get_viewport().set_input_as_handled()
