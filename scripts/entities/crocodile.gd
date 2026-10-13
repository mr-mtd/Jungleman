class_name Crocodile
extends StaticBody2D
## A crocodile lurking at the water surface. Its back is a safe platform, but
## it snaps its jaws open on a timer, so time your hops.

@export var facing_left := true
@export var closed_time := 1.8
@export var open_time := 1.1
@export var bite_damage := 40
@export var start_offset := 0.0

var is_open := false
var _timer := 0.0

@onready var sprite: AnimatedSprite2D = $Sprite
@onready var mouth: Area2D = $Mouth


func _ready() -> void:
	_timer = closed_time - fmod(position.x * 0.013 + start_offset, closed_time)
	if not facing_left:
		sprite.flip_h = true
		mouth.position.x *= -1
		$Shape.position.x *= -1
	sprite.play("closed")


func _physics_process(delta: float) -> void:
	_timer -= delta
	if _timer <= 0.0:
		is_open = not is_open
		_timer = open_time if is_open else closed_time
		sprite.play("open" if is_open else "closed")
		if not is_open:
			Audio.play_at("snap", global_position, -6.0)
	# small bob so it feels alive
	sprite.position.y = -6.0 + (1.0 if fmod(Time.get_ticks_msec() / 600.0 + position.x, 2.0) > 1.0 else 0.0)
	if is_open:
		for body in mouth.get_overlapping_bodies():
			if body.has_method("hurt"):
				body.hurt(bite_damage, mouth.global_position)
