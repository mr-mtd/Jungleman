class_name Enemy
extends Area2D
## Shared enemy behaviour: hurts the player on contact, dies to the whip or
## sling stones.

@export var max_health := 1
@export var damage := 20
@export var points := 50

var health := 1
var dying := false

@onready var sprite: AnimatedSprite2D = $Sprite


func _ready() -> void:
	health = max_health
	collision_layer = 4
	collision_mask = 2


func _physics_process(_delta: float) -> void:
	if dying:
		return
	for body in get_overlapping_bodies():
		if body.has_method("hurt"):
			body.hurt(damage, global_position)


func hit(amount: int) -> void:
	if dying:
		return
	health -= amount
	Audio.play_at("hit", global_position)
	var tw := create_tween()
	tw.tween_property(sprite, "modulate", Color(3, 3, 3), 0.05)
	tw.tween_property(sprite, "modulate", Color.WHITE, 0.1)
	if health <= 0:
		_die()


func _die() -> void:
	dying = true
	GameState.add_score(points)
	Audio.play_at("enemy_die", global_position)
	set_deferred("monitoring", false)
	set_deferred("monitorable", false)
	sprite.pause()
	sprite.flip_v = true
	var tw := create_tween().set_parallel()
	tw.tween_property(self, "position:y", position.y + 40.0, 0.5).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_property(sprite, "modulate:a", 0.0, 0.5)
	tw.chain().tween_callback(queue_free)


func player() -> Node2D:
	return get_tree().get_first_node_in_group("player") as Node2D
