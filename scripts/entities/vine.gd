class_name Vine
extends Node2D
## A pendulum vine. Swings on its own until grabbed; the player can pump it
## (push in the swing direction), climb up/down, and jump off with momentum.

const GRAVITY := 900.0
const PUMP_STRENGTH := 2.2
const MAX_ANGLE := 1.15
const VineTexture := preload("res://assets/tiles/vine.png")

@export var length := 96.0
@export var rest_amplitude := 0.6  ## radians the vine swings when nobody hangs on it
@export var phase := 0.0

var angle := 0.0
var ang_vel := 0.0
var occupied := false
var grab := 0.0


func _ready() -> void:
	add_to_group("vines")
	var w := sqrt(GRAVITY / (length * 0.85))
	angle = rest_amplitude * sin(phase)
	ang_vel = rest_amplitude * w * cos(phase)
	rotation = angle


func _physics_process(delta: float) -> void:
	var l := grab if occupied else length * 0.85
	ang_vel += -(GRAVITY / l) * sin(angle) * delta
	if not occupied:
		# gently steer back toward the resting swing amplitude
		var energy := 0.5 * ang_vel * ang_vel + (GRAVITY / l) * (1.0 - cos(angle))
		var target := (GRAVITY / l) * (1.0 - cos(rest_amplitude))
		ang_vel *= 1.0 + clamp((target - energy) / target, -1.0, 1.0) * 0.6 * delta
		if absf(ang_vel) < 0.01 and absf(angle) < 0.01:
			ang_vel = 0.5
	else:
		ang_vel *= 1.0 - 0.05 * delta
	angle += ang_vel * delta
	if absf(angle) > MAX_ANGLE:
		angle = sign(angle) * MAX_ANGLE
		ang_vel *= -0.3
	rotation = angle


func _draw() -> void:
	# a knotted branch stub the vine hangs from
	draw_circle(Vector2(0, -1), 3.2, Color("4a2e16"))
	draw_circle(Vector2(-0.8, -1.8), 1.4, Color("7a5230"))
	var tex_h := VineTexture.get_height()
	var y := 0.0
	while y < length:
		var h := minf(16.0, length - y)
		draw_texture_rect_region(VineTexture, Rect2(-8, y, 16, h), Rect2(0, 0, VineTexture.get_width(), tex_h * h / 16.0))
		y += 16.0
	# leafy tuft at the tip
	draw_circle(Vector2(-1.5, length - 1.0), 2.4, Color("4f9a32"))
	draw_circle(Vector2(1.6, length), 2.0, Color("6cc040"))
	draw_circle(Vector2(0.0, length + 1.6), 1.6, Color("3a7a26"))


## Unit vector pointing from the anchor down the vine.
func down_vector() -> Vector2:
	return Vector2(-sin(angle), cos(angle))


func point_at(dist: float) -> Vector2:
	return global_position + down_vector() * dist


func velocity_at(dist: float) -> Vector2:
	return Vector2(-cos(angle), -sin(angle)) * dist * ang_vel


## Distance along the vine where a hand at `point` can grab it, or -1.
func grab_distance(point: Vector2) -> float:
	var local := (point - global_position).rotated(-angle)
	if absf(local.x) <= 7.0 and local.y >= 10.0 and local.y <= length:
		return local.y
	return -1.0


func attach(dist: float, vel: Vector2) -> void:
	occupied = true
	grab = dist
	var tangent := Vector2(-cos(angle), -sin(angle))
	ang_vel = clamp(ang_vel * 0.4 + vel.dot(tangent) / dist * 0.8, -3.5, 3.5)


func set_grab(dist: float) -> void:
	grab = dist


func detach() -> void:
	occupied = false


## Push in direction `dir` (-1 left, 1 right). Only adds energy when pushing
## along the current swing, like pumping a playground swing.
func pump(dir: float, delta: float) -> void:
	if dir == 0.0:
		return
	var moving_right := ang_vel < 0.0
	if (dir > 0.0) == moving_right and absf(angle) < MAX_ANGLE * 0.9:
		ang_vel -= dir * PUMP_STRENGTH * delta
