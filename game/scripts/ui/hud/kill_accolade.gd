class_name KillAccolade
extends Control
## Local-only feedback from authoritative elimination events.
const HOLD := 2.6
var victim := ""
var accolade := ""
var chain_count := 0
var remaining := 0.0
var reduced_motion := false
var high_contrast := false

func _ready() -> void:
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	accessibility_live=1

func announce(event: Dictionary) -> void:
	victim=String(event.victim)
	accolade=String(event.accolade)
	chain_count=int(event.count)
	remaining=HOLD
	accessibility_name="You killed %s. %s" % [victim,accolade]
	queue_redraw()

func _process(dt: float) -> void:
	remaining=maxf(0.0,remaining-dt)
	queue_redraw()

func _draw() -> void:
	if remaining<=0.0: return
	var age := HOLD-remaining
	var opacity := minf(1.0,remaining/0.4)
	var pop := 1.0 if reduced_motion else 1.0+0.14*pow(maxf(0.0,1.0-age/0.22),2.0)
	var center := Vector2(size.x*0.5,size.y*0.5-126.0)
	draw_set_transform(center,0,Vector2.ONE*pop)
	line("You killed "+victim,0,26,HudSkin.WHITE,opacity)
	if not accolade.is_empty():
		var accent := HudSkin.AMBER if chain_count>=5 else HudSkin.CYAN
		line(accolade.to_upper(),47,46,accent,opacity)
		var span := minf(116.0,size.x*0.13)
		draw_line(Vector2(-span,60),Vector2(span,60),Color(accent,opacity*0.7),2.0,true)
	draw_set_transform(Vector2.ZERO)

func line(text: String, y: float, font_size: int, color: Color, opacity: float) -> void:
	var available := size.x*0.64
	var width := HudSkin.BOLD_FONT.get_string_size(text,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x
	var fitted := maxi(14,int(font_size*minf(1.0,available/maxf(width,1.0))))
	width=HudSkin.BOLD_FONT.get_string_size(text,HORIZONTAL_ALIGNMENT_LEFT,-1,fitted).x
	var point := Vector2(-width*0.5,y)
	draw_string_outline(HudSkin.BOLD_FONT,point,text,HORIZONTAL_ALIGNMENT_LEFT,-1,fitted,5 if high_contrast else 3,Color(0.02,0.03,0.04,opacity*0.94))
	draw_string(HudSkin.BOLD_FONT,point,text,HORIZONTAL_ALIGNMENT_LEFT,-1,fitted,Color(color,opacity))
