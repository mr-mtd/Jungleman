extends Node2D
## Rolls a log toward the player every few seconds while they are nearby.

const LogScene := preload("res://scenes/entities/rolling_log.tscn")

@export var interval := 3.4
@export var trigger_distance := 420.0

var _timer := 1.0


func _physics_process(delta: float) -> void:
	var player := get_tree().get_first_node_in_group("player") as Node2D
	if player == null:
		return
	var dx := global_position.x - player.global_position.x
	if dx < 0.0 or dx > trigger_distance:
		return
	_timer -= delta
	if _timer <= 0.0:
		_timer = interval
		var rolling := LogScene.instantiate()
		rolling.position = position
		get_parent().add_child(rolling)
