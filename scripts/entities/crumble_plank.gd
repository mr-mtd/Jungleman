extends StaticBody2D
## A rickety bridge plank that gives way shortly after you step on it.

@export var delay := 0.35
@export var respawn_time := 3.5

var _state := "solid"
var _home := Vector2.ZERO

@onready var shape: CollisionShape2D = $Shape
@onready var sprite: Sprite2D = $Sprite
@onready var sensor: Area2D = $Sensor


func _ready() -> void:
	_home = position
	sensor.body_entered.connect(_on_step)


func _on_step(body: Node) -> void:
	if _state != "solid" or not body.is_in_group("player"):
		return
	_state = "shaking"
	var tw := create_tween()
	for i in 4:
		tw.tween_property(sprite, "position:x", 1.0, delay / 8.0)
		tw.tween_property(sprite, "position:x", -1.0, delay / 8.0)
	tw.tween_callback(_fall)


func _fall() -> void:
	_state = "fallen"
	sprite.position.x = 0
	shape.set_deferred("disabled", true)
	var tw := create_tween().set_parallel()
	tw.tween_property(self, "position:y", _home.y + 120.0, 0.7).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_property(sprite, "modulate:a", 0.0, 0.7)
	tw.chain().tween_interval(respawn_time)
	tw.chain().tween_callback(_reset)


func _reset() -> void:
	position = _home
	sprite.modulate.a = 1.0
	shape.set_deferred("disabled", false)
	_state = "solid"
