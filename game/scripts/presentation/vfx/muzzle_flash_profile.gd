class_name MuzzleFlashProfile
extends Resource
## Immutable weapon recipe; individual flashes retain their own phase and fade.
@export var outer_color := Color("ffb532")
@export var jet_color := Color("fff6d4")
@export var edge_color := Color("ff5108")
@export_range(0.01,2.0,0.005) var outer_length := 0.105
@export_range(0.005,0.5,0.005) var outer_radius := 0.075
@export_range(0.01,2.0,0.005) var jet_length := 0.42
@export_range(0.002,0.5,0.002) var jet_radius := 0.024
@export_range(0.01,0.5,0.005) var lifetime := 0.10
@export_range(0.0,20.0,0.1) var emission := 5.5
