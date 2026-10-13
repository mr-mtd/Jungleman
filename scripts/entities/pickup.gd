extends Area2D
## Collectibles: gold treasure, sling stones, canteen (health) and extra life.

enum Kind { GOLD, STONES, HEALTH, LIFE }

@export var kind: Kind = Kind.GOLD

var _base_y := 0.0
var _t := 0.0

@onready var sprite: Sprite2D = $Sprite


func _ready() -> void:
	sprite.region_rect = Rect2(int(kind) * 16, 0, 16, 16)
	_base_y = position.y
	_t = position.x * 0.1
	body_entered.connect(_on_body_entered)


func _process(delta: float) -> void:
	_t += delta
	position.y = _base_y + round(sin(_t * 3.0) * 1.5)


func _on_body_entered(body: Node) -> void:
	if not body.is_in_group("player"):
		return
	match kind:
		Kind.GOLD:
			GameState.add_treasure()
		Kind.STONES:
			GameState.add_stones(5)
			GameState.show_message("+5 SLING STONES", 1.0)
		Kind.HEALTH:
			body.heal(50)
			GameState.add_score(25)
		Kind.LIFE:
			GameState.add_life()
	set_deferred("monitoring", false)
	var tw := create_tween().set_parallel()
	tw.tween_property(self, "position:y", position.y - 12.0, 0.25)
	tw.tween_property(self, "modulate:a", 0.0, 0.25)
	tw.chain().tween_callback(queue_free)
