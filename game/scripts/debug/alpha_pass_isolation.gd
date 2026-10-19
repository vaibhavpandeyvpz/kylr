extends RefCounted
## Diagnostic raster-alpha draw isolation. Simulation and RT resources stay live.
const PHASE_SECONDS := 8.0
const PHASES := [
	{"label":"baseline_before_effects","mask":""},
	{"label":"without_effects","mask":"res://shaders/combat/*;res://shaders/original/*;!res://shaders/combat/armor_hit.gdshader;!res://shaders/original/frosted_glass.gdshader"},
	{"label":"baseline_after_effects","mask":""},
	{"label":"without_glass","mask":"res://shaders/original/frosted_glass.gdshader"},
	{"label":"baseline_after_glass","mask":""},
	{"label":"without_hit_overlay","mask":"res://shaders/combat/armor_hit.gdshader"},
	{"label":"baseline_after_hit_overlay","mask":""},
]
const EFFECT_PHASES := [
	{"label":"baseline_before_layered_effects","mask":""},
	{"label":"without_layered_effects","mask":"res://shaders/original/*;!res://shaders/original/frosted_glass.gdshader"},
	{"label":"baseline_after_layered_effects","mask":""},
	{"label":"without_thermal_layers","mask":"res://shaders/original/thermal_surface.gdshader"},
	{"label":"baseline_after_thermal_layers","mask":""},
	{"label":"without_other_custom_effects","mask":"res://shaders/combat/*;!res://shaders/combat/armor_hit.gdshader"},
	{"label":"baseline_after_other_custom_effects","mask":""},
]
const LAYERED_PHASES := [
	{"label":"baseline_before_gas_shells","mask":""},
	{"label":"without_gas_shells","mask":"res://shaders/original/eruption_shell.gdshader"},
	{"label":"baseline_after_gas_shells","mask":""},
	{"label":"without_thermal_surfaces","mask":"res://shaders/original/thermal_surface.gdshader"},
	{"label":"baseline_after_thermal_surfaces","mask":""},
	{"label":"without_pressure_fronts","mask":"res://shaders/original/pressure_ring.gdshader"},
	{"label":"baseline_after_pressure_fronts","mask":""},
]
var phases: Array
var groups := "overview"
var started_usec := 0
var phase := -1
var rows: Array[Dictionary] = []
var original_mask := ""
var restored := false

func begin(now: int,choice: String) -> void:
	started_usec=now
	groups=choice
	phases=LAYERED_PHASES if choice == "layered" else (EFFECT_PHASES if choice=="effects" else PHASES)
	original_mask=OS.get_environment("GODOT_GPU_PROFILE_ALPHA_MASK")
	for item in phases:
		var row: Dictionary=item.duplicate()
		row["frames"]=0;row["start_seconds"]=-1.0;row["end_seconds"]=-1.0
		rows.append(row)
	tick(now)

func tick(now: int) -> void:
	var elapsed := float(now-started_usec)/1000000.0
	var next_phase := mini(phases.size()-1,int(elapsed/PHASE_SECONDS))
	if next_phase==phase: return
	if phase>=0: rows[phase].end_seconds=elapsed
	phase=next_phase
	rows[phase].start_seconds=elapsed
	OS.set_environment("GODOT_GPU_PROFILE_ALPHA_MASK",phases[phase].mask)
	print("PROFILE_ALPHA_PHASE index=",phase," label=",phases[phase].label," elapsed_s=",elapsed)

func record_frame() -> void:
	if phase>=0: rows[phase].frames+=1

func finish(now: int) -> void:
	if phase>=0: rows[phase].end_seconds=float(now-started_usec)/1000000.0
	OS.set_environment("GODOT_GPU_PROFILE_ALPHA_MASK",original_mask)
	restored=true
	print("PROFILE_ALPHA_END")

func report() -> Dictionary:
	return {"diagnostic_only":true,"performance_acceptance":false,"phase_seconds":PHASE_SECONDS,
		"camera_orbit_seconds":PHASE_SECONDS,"groups":groups,"restored":restored,"phases":rows}
