extends Area2D
## Stone idol. Touch it and it turns gold: you'll respawn here.

var active := false

@onready var sprite: Sprite2D = $Sprite


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	# already reached this one before the scene was reloaded?
	if GameState.has_checkpoint and GameState.checkpoint.distance_to(_spawn_point()) < 1.0:
		_activate()


func _spawn_point() -> Vector2:
	return global_position + Vector2(0, -5)


func _on_body_entered(body: Node) -> void:
	if active or not body.is_in_group("player"):
		return
	_activate()
	Audio.play("checkpoint", -2.0, 0.0)
	GameState.set_checkpoint(_spawn_point())
	GameState.add_score(50)
	GameState.show_message("CHECKPOINT", 1.5)


func _activate() -> void:
	active = true
	sprite.region_rect = Rect2(320, 0, 64, 64)
