extends CanvasLayer
## Health meter, lives, sling stones, treasure, score and on-screen messages.

@onready var health_fill: ColorRect = %HealthFill
@onready var lives_label: Label = %Lives
@onready var stones_label: Label = %Stones
@onready var score_label: Label = %Score
@onready var message_label: Label = %Message
@onready var pause_label: Label = %Paused

var _message_time := 0.0
var _waiting_restart := false


func _ready() -> void:
	add_to_group("hud")
	process_mode = Node.PROCESS_MODE_ALWAYS
	GameState.changed.connect(_refresh)
	GameState.message.connect(_on_message)
	_refresh()


func _refresh() -> void:
	health_fill.size.x = 60.0 * GameState.health / float(GameState.MAX_HEALTH)
	health_fill.color = Color("4ad04a") if GameState.health > 40 else Color("e0b030") if GameState.health > 20 else Color("e04040")
	lives_label.text = "LIVES %d" % GameState.lives
	stones_label.text = "STONES %d   GOLD %d" % [GameState.stones, GameState.treasure]
	score_label.text = "SCORE %06d" % GameState.score


func _on_message(text: String, seconds: float) -> void:
	message_label.text = text
	message_label.modulate.a = 1.0
	_message_time = seconds


func _process(delta: float) -> void:
	if _message_time > 0.0:
		_message_time -= delta
		if _message_time < 0.4:
			message_label.modulate.a = max(_message_time / 0.4, 0.0)
	if _waiting_restart and Input.is_action_just_pressed("jump"):
		_waiting_restart = false
		get_tree().paused = false
		GameState.reset()
		get_tree().reload_current_scene()
	elif not _waiting_restart and Input.is_action_just_pressed("pause"):
		get_tree().paused = not get_tree().paused
		pause_label.visible = get_tree().paused


func show_game_over() -> void:
	_waiting_restart = true


func show_level_complete() -> void:
	GameState.show_message("LEVEL COMPLETE!\nTreasure %d   Score %d\nPress Jump to play again" % [GameState.treasure, GameState.score], 999.0)
	_waiting_restart = true
