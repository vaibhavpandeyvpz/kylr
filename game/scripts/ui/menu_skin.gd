class_name MenuSkin
extends RefCounted
## Shared menu surfaces and states, including independently hosted overlays.
const CANVAS = Color("0b1119")
const PLATE = Color("17222d")
const RAISED = Color("243341")
const LINE = Color("415464")
const TEXT = Color("f3f6f7")
const MUTED = Color("b9c9d1")
const ACTION = Color("6fe5ea")
const HOVER = Color("a9f5f4")
const SUCCESS = Color("8bdead")
const CAUTION = Color("ffc36a")
const DANGER = Color("ff7275")
const RADIUS = 8
const SPACING = 16

static func surface(selected := false) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = RAISED if selected else PLATE
	box.border_color = ACTION if selected else LINE
	box.set_border_width_all(1)
	box.set_corner_radius_all(RADIUS)
	box.content_margin_left = 20
	box.content_margin_right = 20
	box.content_margin_top = 14
	box.content_margin_bottom = 14
	return box

static func control_style(state: String, primary := false, selected := false) -> StyleBoxFlat:
	var box := surface(selected)
	if state == "focus":
		box.bg_color = Color.TRANSPARENT
		box.border_color = TEXT if primary else ACTION
		box.set_border_width_all(2)
	elif state == "disabled":
		box.bg_color = PLATE
		box.border_color = LINE.darkened(0.35)
	elif primary:
		box.bg_color = HOVER if state == "hover" else ACTION.darkened(0.12) if state == "pressed" else ACTION
		box.border_color = box.bg_color
	elif state in ["hover","pressed"]:
		box.bg_color = RAISED.lightened(0.06) if state == "hover" else RAISED
		box.border_color = ACTION if state == "pressed" or selected else LINE.lightened(0.25)
	return box

static func toggle_style(state: String) -> StyleBoxFlat:
	# A checked switch is a persistent value, not a held action button.
	return control_style("hover" if state in ["hover","hover_pressed"] else "normal" if state == "pressed" else state)

static func apply_button(button: Button, primary := false, selected := false):
	for state in ["normal","hover","pressed","focus","disabled","hover_pressed"]:
		button.add_theme_stylebox_override(state,control_style("pressed" if state == "hover_pressed" else state,primary,selected))
	for state in ["font_color","font_hover_color","font_pressed_color","font_focus_color","font_hover_pressed_color"]:
		button.add_theme_color_override(state,CANVAS if primary else TEXT)
	button.add_theme_color_override("font_disabled_color",MUTED.darkened(0.25))

static func icon(svg: String) -> ImageTexture:
	var image := Image.new()
	image.load_svg_from_string(svg)
	return ImageTexture.create_from_image(image)

static func make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font = load("res://assets/ui/fonts/Inter.ttf")
	theme.default_font_size = 18
	for type in ["Label","Button","LineEdit","OptionButton","CheckButton","SpinBox","PopupMenu"]:
		theme.set_color("font_color",type,TEXT)
		theme.set_color("font_disabled_color",type,MUTED.darkened(0.25))
		for state in ["font_hover_color","font_pressed_color","font_focus_color","font_hover_pressed_color"]:
			theme.set_color(state,type,TEXT)
	for type in ["Button","OptionButton","LineEdit","CheckButton"]:
		for state in ["normal","hover","pressed","focus","disabled","read_only","hover_pressed"]:
			theme.set_stylebox(state,type,toggle_style(state) if type == "CheckButton" else control_style("disabled" if state == "read_only" else "pressed" if state == "hover_pressed" else state))
	for type in ["Panel","PanelContainer","PopupMenu","AcceptDialog"]:
		theme.set_stylebox("panel",type,surface())
	theme.set_stylebox("hover","PopupMenu",surface(true))
	theme.set_color("font_hover_color","PopupMenu",TEXT)
	theme.set_color("selection_color","LineEdit",Color(ACTION,0.25))
	theme.set_color("caret_color","LineEdit",ACTION)
	theme.set_color("font_selected_color","LineEdit",TEXT)
	theme.set_color("font_placeholder_color","LineEdit",MUTED)
	for type in ["HBoxContainer","VBoxContainer"]: theme.set_constant("separation",type,SPACING)
	var track := surface()
	track.bg_color = CANVAS
	track.set_content_margin_all(0)
	theme.set_stylebox("background","ProgressBar",track)
	var fill := track.duplicate() as StyleBoxFlat
	fill.bg_color = ACTION
	fill.set_border_width_all(0)
	theme.set_stylebox("fill","ProgressBar",fill)
	var slider := surface()
	slider.set_content_margin_all(0)
	slider.set_border_width_all(0)
	slider.bg_color = LINE
	slider.content_margin_top = 2
	slider.content_margin_bottom = 2
	theme.set_stylebox("slider","HSlider",slider)
	var slider_active := slider.duplicate() as StyleBoxFlat
	slider_active.bg_color = ACTION
	theme.set_stylebox("grabber_area","HSlider",slider_active)
	theme.set_stylebox("grabber_area_highlight","HSlider",slider_active)
	for state in ["grabber","grabber_highlight","grabber_disabled"]:
		var tint := MUTED if state == "grabber_disabled" else ACTION
		theme.set_icon(state,"HSlider",icon('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="8" fill="#'+tint.to_html(false)+'"/></svg>'))
	for checked in [false,true]:
		for disabled in [false,true]:
			var fill_color := ACTION if checked and not disabled else LINE
			var knob_color := CANVAS if checked and not disabled else MUTED
			var svg := '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="24"><rect x="1" y="3" width="38" height="18" rx="9" fill="#%s"/><circle cx="%d" cy="12" r="6" fill="#%s"/></svg>' % [fill_color.to_html(false),29 if checked else 11,knob_color.to_html(false)]
			theme.set_icon(("checked" if checked else "unchecked")+("_disabled" if disabled else ""),"CheckButton",icon(svg))
	return theme
