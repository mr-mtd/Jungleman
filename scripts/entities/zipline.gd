class_name Zipline
extends Node2D
## A rope slide. Jump up and grab it, then ride it downhill to the far end.

@export var end_offset := Vector2(320, 80)


func _ready() -> void:
	add_to_group("ziplines")
	queue_redraw()


func _draw() -> void:
	draw_line(Vector2.ZERO, end_offset, Color("c8b080"), 1.5)
	draw_rect(Rect2(-3, -4, 6, 6), Color("5a3a1c"))
	draw_rect(Rect2(end_offset.x - 3, end_offset.y - 4, 6, 6), Color("5a3a1c"))


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
