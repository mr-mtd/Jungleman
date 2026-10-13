extends CharacterBody2D
## A log rolling along the ground. Jump over it!

@export var speed := 75.0
@export var damage := 25

var direction := -1.0
var _life := 14.0

@onready var hurtbox: Area2D = $Hurtbox
@onready var sprite: AnimatedSprite2D = $Sprite


func _ready() -> void:
	sprite.play("roll")
	sprite.flip_h = direction > 0


func _physics_process(delta: float) -> void:
	_life -= delta
	velocity.x = direction * speed
	velocity.y = min(velocity.y + 900.0 * delta, 400.0)
	move_and_slide()
	if is_on_wall() or _life <= 0.0 or global_position.y > 1000.0:
		queue_free()
		return
	for body in hurtbox.get_overlapping_bodies():
		if body.has_method("hurt"):
			body.hurt(damage, global_position)
