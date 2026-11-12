"""
XE TU HANH NE VAT CAN
ESP32 + 2 driver L298N (4 dong co rieng) + HC-SR04 gan tren servo.

DRIVER 1 (banh SAU):   A = m1 sau trai    | B = m2 sau phai
DRIVER 2 (banh TRUOC): A = m3 truoc trai  | B = m4 truoc phai

Cach chay:
  - Phia truoc thoang: chay, toc do tang dan theo khoang cach.
  - Gan vat can: giam toc do, dung han khi cach <= STOP_DIST.
  - Dung lai: lui nhe, quet servo trai/phai, quay ve phia thoang hon.
  - Hai ben deu kin: quay dau ~180 do.
Bam Ctrl+C (Thonny: nut Stop) de dung xe.
"""
from machine import Pin, PWM, time_pulse_us
import time

# =====================================================================
# CAU HINH (chinh o day)
# =====================================================================
# --- Toc do (0..1023) ---
MIN_SPEED = 450        # thap hon muc nay dong co TT de khong quay
MAX_SPEED = 700        # toc do toi da khi duong thoang
TURN_SPEED = 600       # toc do khi quay / lui
ACCEL_STEP = 30        # tang toc toi da moi vong lap (giam toc ap dung ngay)

# --- Khoang cach (cm) ---
STOP_DIST = 20         # gan hon -> dung va ne
FAR_DIST = 80          # xa hon -> chay het MAX_SPEED
CLEAR_DIST = 35        # sau khi quay, phia truoc phai thoang hon muc nay moi di tiep

# --- Quay ---
TURN_TIME = 0.60       # thoi gian quay ~90 do (chinh theo xe)
BACK_TIME = 0.35       # thoi gian lui khi gap vat can

# --- Servo: goc quet. Neu quay NGUOC phia thi doi LEFT_ANGLE va RIGHT_ANGLE cho nhau ---
CENTER_ANGLE = 90
LEFT_ANGLE = 150
RIGHT_ANGLE = 30

# --- Dong co: [m1 sau trai, m2 sau phai, m3 truoc trai, m4 truoc phai] ---
INVERT = [True, False, False, True]    # True neu banh quay nguoc chieu
SCALE = [1.0, 1.0, 1.0, 1.0]           # he so bu toc do tung banh

# =====================================================================
# CHAN NOI
# =====================================================================
D1_ENA, D1_IN1, D1_IN2 = 25, 26, 27
D1_IN3, D1_IN4, D1_ENB = 14, 13, 33
D2_ENA, D2_IN1, D2_IN2 = 32, 16, 17
D2_IN3, D2_IN4, D2_ENB = 5, 22, 21
SERVO_PIN = 23
TRIG_PIN, ECHO_PIN = 18, 19

# =====================================================================
# KHOI TAO PHAN CUNG
# =====================================================================
def make_motor(en, a, b):
    return (PWM(Pin(en), freq=1000, duty=0), Pin(a, Pin.OUT), Pin(b, Pin.OUT))

motors = [
    make_motor(D1_ENA, D1_IN1, D1_IN2),   # m1 sau trai
    make_motor(D1_ENB, D1_IN3, D1_IN4),   # m2 sau phai
    make_motor(D2_ENA, D2_IN1, D2_IN2),   # m3 truoc trai
    make_motor(D2_ENB, D2_IN3, D2_IN4),   # m4 truoc phai
]

servo = PWM(Pin(SERVO_PIN), freq=50)
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

# =====================================================================
# DONG CO
# =====================================================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def set_motor(i, v):
    if INVERT[i]:
        v = -v
    v = clamp(int(v * SCALE[i]), -1023, 1023)
    en, a, b = motors[i]
    a.value(1 if v > 0 else 0)
    b.value(1 if v < 0 else 0)
    en.duty(abs(v))

def drive(left, right):
    """left, right: -1023..1023 (duong = tien). Ap cho ca banh truoc va sau."""
    set_motor(0, left);  set_motor(2, left)
    set_motor(1, right); set_motor(3, right)

def stop():
    drive(0, 0)

def backward(t):
    drive(-TURN_SPEED, -TURN_SPEED)
    time.sleep(t)
    stop()

def turn_left(t):
    drive(-TURN_SPEED, TURN_SPEED)
    time.sleep(t)
    stop()

def turn_right(t):
    drive(TURN_SPEED, -TURN_SPEED)
    time.sleep(t)
    stop()

# =====================================================================
# SERVO (quay muot tung buoc nho de do giat)
# =====================================================================
servo_angle = CENTER_ANGLE

def set_angle(target, step=3, delay=0.02):
    global servo_angle
    target = clamp(int(target), 0, 180)
    while servo_angle != target:
        if abs(target - servo_angle) <= step:
            servo_angle = target
        else:
            servo_angle += step if target > servo_angle else -step
        servo.duty(int(26 + servo_angle * 102 / 180))
        time.sleep(delay)
    time.sleep(0.2)

# =====================================================================
# SIEU AM
# =====================================================================
def distance_once():
    trig.value(0); time.sleep_us(2)
    trig.value(1); time.sleep_us(10)
    trig.value(0)
    t = time_pulse_us(echo, 1, 30000)
    if t < 0:
        return 400          # khong nhan duoc xung -> coi nhu khong co vat can
    return t * 0.0343 / 2

def distance(samples=3):
    vals = []
    for _ in range(samples):
        vals.append(distance_once())
        time.sleep_ms(30)
    vals.sort()
    return vals[len(vals) // 2]

# =====================================================================
# TOC DO THEO KHOANG CACH
# =====================================================================
def speed_for(d):
    if d <= STOP_DIST:
        return 0
    if d >= FAR_DIST:
        return MAX_SPEED
    ratio = (d - STOP_DIST) / (FAR_DIST - STOP_DIST)     # 0 -> 1
    return int(MIN_SPEED + (MAX_SPEED - MIN_SPEED) * ratio)

def ramp(current, target):
    if target < current:
        return target                       # giam toc ngay (an toan)
    return min(target, current + ACCEL_STEP)   # tang toc tu tu

# =====================================================================
# NE VAT CAN
# =====================================================================
def avoid():
    stop()
    backward(BACK_TIME)

    set_angle(LEFT_ANGLE);  d_left = distance()
    set_angle(RIGHT_ANGLE); d_right = distance()
    set_angle(CENTER_ANGLE)
    print("Trai: %.0f cm | Phai: %.0f cm" % (d_left, d_right))

    if d_left < CLEAR_DIST and d_right < CLEAR_DIST:
        print("Ket hai ben -> quay dau")
        turn_left(TURN_TIME * 2)
    elif d_left >= d_right:
        print("Quay trai")
        turn_left(TURN_TIME)
    else:
        print("Quay phai")
        turn_right(TURN_TIME)

# =====================================================================
# CHAY CHUONG TRINH
# =====================================================================
try:
    stop()
    set_angle(CENTER_ANGLE)
    print("Bat dau sau 3 giay... (Ctrl+C de huy)")
    time.sleep(3)

    current = 0
    while True:
        d = distance()
        target = speed_for(d)
        current = ramp(current, target)

        if target == 0:
            print("Vat can o %.0f cm" % d)
            current = 0
            avoid()
        else:
            drive(current, current)
            print("d = %.0f cm | v = %d" % (d, current))

        time.sleep_ms(30)

except KeyboardInterrupt:
    print("Da dung theo yeu cau")
finally:
    stop()
    set_angle(CENTER_ANGLE)
    print("Xe da dung")