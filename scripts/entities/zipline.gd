class_name Zipline
extends Node2D
## A rope slide. Jump up and grab it, then ride it downhill to the far end.

@export var end_offset := Vector2(320, 80)


func _ready() -> void:
	add_to_group("ziplines")
	queue_redraw()


func _draw() -> void:
	var sag := PackedVector2Array()
	for i in 21:
		var t := i / 20.0
		sag.append(end_offset * t + Vector2(0, sin(t * PI) * 2.0))
	draw_polyline(sag, Color(0.2, 0.13, 0.06, 0.5), 2.2, true)
	draw_polyline(sag, Color("d8c08a"), 1.1, true)
	for p in [Vector2.ZERO, end_offset]:
		draw_circle(p, 3.0, Color("4a2e16"))
		draw_circle(p, 1.8, Color("a07040"))
		draw_circle(p + Vector2(-0.6, -0.6), 0.7, Color(1, 1, 1, 0.4))


func length() -> float:
	return end_offset.length()


func direction() -> Vector2:
	return end_offset.normalized()


func point_at(t: float) -> Vector2:
	return global_position + end_offset * t


## Position (0..1) along the rope that a hand at `point` can grab, or -1.
func grab_t(point: Vector2) -> float:
	var local := point - global_position
	var t := clampf(local.dot(end_offset) / end_offset.length_squared(), 0.0, 1.0)
	if t > 0.9:
		return -1.0
	if local.distance_to(end_offset * t) <= 8.0:
		return t
	return -1.0
