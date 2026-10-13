extends Area2D
## A sling stone. Arcs through the air and knocks out the first enemy it hits.

var velocity := Vector2.ZERO
var _life := 2.0


func _ready() -> void:
	area_entered.connect(_on_area_entered)
	body_entered.connect(func(_b): queue_free())


func _physics_process(delta: float) -> void:
	velocity.y += 500.0 * delta
	position += velocity * delta
	rotation += delta * 12.0
	_life -= delta
	if _life <= 0.0:
		queue_free()


func _on_area_entered(area: Area2D) -> void:
	if area.has_method("hit"):
		area.hit(1)
		queue_free()
