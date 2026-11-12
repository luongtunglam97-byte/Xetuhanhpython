"""
XE TU HANH NE VAT CAN + DIEU KHIEN DONG WEB SERVER (GIU NUT DE CHAY)
ESP32 + 2 driver L298N (4 dong co) + HC-SR04 + Servo
"""
from machine import Pin, PWM, time_pulse_us
import time
import network
import socket
import _thread

# =====================================================================
# CAU HINH PHAN CUNG & TOC DO
# =====================================================================
MIN_SPEED = 450
MAX_SPEED = 700
TURN_SPEED = 600
ACCEL_STEP = 30

STOP_DIST = 20
FAR_DIST = 80
CLEAR_DIST = 35

TURN_TIME = 0.60
BACK_TIME = 0.35

CENTER_ANGLE = 90
LEFT_ANGLE = 150
RIGHT_ANGLE = 30

INVERT = [True, False, False, True]
SCALE = [1.0, 1.0, 1.0, 1.0]

D1_ENA, D1_IN1, D1_IN2 = 25, 26, 27
D1_IN3, D1_IN4, D1_ENB = 14, 13, 33
D2_ENA, D2_IN1, D2_IN2 = 32, 16, 17
D2_IN3, D2_IN4, D2_ENB = 5, 22, 21
SERVO_PIN = 23
TRIG_PIN, ECHO_PIN = 18, 19

mode = "MANUAL"
manual_cmd = "stop"

# =====================================================================
# KHOI TAO PHAN CUNG
# =====================================================================
def make_motor(en, a, b):
    return (PWM(Pin(en), freq=1000, duty=0), Pin(a, Pin.OUT), Pin(b, Pin.OUT))

motors = [
    make_motor(D1_ENA, D1_IN1, D1_IN2),
    make_motor(D1_ENB, D1_IN3, D1_IN4),
    make_motor(D2_ENA, D2_IN1, D2_IN2),
    make_motor(D2_ENB, D2_IN3, D2_IN4),
]

servo = PWM(Pin(SERVO_PIN), freq=50)
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
servo_angle = CENTER_ANGLE

# =====================================================================
# DONG CO & SERVO
# =====================================================================
def clamp(v, lo, hi): return max(lo, min(hi, v))

def set_motor(i, v):
    if INVERT[i]: v = -v
    v = clamp(int(v * SCALE[i]), -1023, 1023)
    en, a, b = motors[i]
    a.value(1 if v > 0 else 0)
    b.value(1 if v < 0 else 0)
    en.duty(abs(v))

def drive(left, right):
    set_motor(0, left);  set_motor(2, left)
    set_motor(1, right); set_motor(3, right)

def stop(): drive(0, 0)

def backward(t): drive(-TURN_SPEED, -TURN_SPEED); time.sleep(t); stop()
def turn_left(t): drive(-TURN_SPEED, TURN_SPEED); time.sleep(t); stop()
def turn_right(t): drive(TURN_SPEED, -TURN_SPEED); time.sleep(t); stop()

def set_angle(target, step=3, delay=0.02):
    global servo_angle
    target = clamp(int(target), 0, 180)
    while servo_angle != target:
        if abs(target - servo_angle) <= step: servo_angle = target
        else: servo_angle += step if target > servo_angle else -step
        servo.duty(int(26 + servo_angle * 102 / 180))
        time.sleep(delay)
    time.sleep(0.1)

# =====================================================================
# SIEU AM
# =====================================================================
def distance_once():
    trig.value(0); time.sleep_us(2)
    trig.value(1); time.sleep_us(10)
    trig.value(0)
    t = time_pulse_us(echo, 1, 30000)
    if t < 0: return 400
    return t * 0.0343 / 2

def distance(samples=3):
    vals = []
    for _ in range(samples):
        vals.append(distance_once())
        time.sleep_ms(20)
    vals.sort()
    return vals[len(vals) // 2]

def speed_for(d):
    if d <= STOP_DIST: return 0
    if d >= FAR_DIST: return MAX_SPEED
    return int(MIN_SPEED + (MAX_SPEED - MIN_SPEED) * ((d - STOP_DIST) / (FAR_DIST - STOP_DIST)))

def ramp(current, target):
    if target < current: return target
    return min(target, current + ACCEL_STEP)

def avoid():
    stop()
    backward(BACK_TIME)
    set_angle(LEFT_ANGLE);  d_left = distance()
    set_angle(RIGHT_ANGLE); d_right = distance()
    set_angle(CENTER_ANGLE)

    if d_left < CLEAR_DIST and d_right < CLEAR_DIST: turn_left(TURN_TIME * 2)
    elif d_left >= d_right: turn_left(TURN_TIME)
    else: turn_right(TURN_TIME)

# =====================================================================
# GIAO DIEN WEB HTML
# =====================================================================
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta charset="utf-8">
    <title>Dieu Khien Xe ESP32</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background-color: #1e1e2f; color: #fff; margin: 0; padding: 20px; touch-action: manipulation; }
        h1 { color: #00d2ff; }
        .btn { display: inline-block; width: 80px; height: 80px; line-height: 80px; font-size: 24px; font-weight: bold; margin: 10px; color: white; background-color: #3a3b5c; border: none; border-radius: 15px; box-shadow: 0 4px #1a1a2e; cursor: pointer; user-select: none; -webkit-user-select: none; }
        .btn:active { background-color: #00d2ff; transform: translateY(4px); box-shadow: none; }
        .btn-mode { width: 140px; height: 50px; line-height: 50px; font-size: 16px; background-color: #e94560; }
        .grid { display: grid; grid-template-columns: repeat(3, 90px); justify-content: center; margin-top: 40px; }
    </style>
</head>
<body>
    <h1>CHẾ ĐỘ ĐIỀU KHIỂN</h1>
    <div>
        <button class="btn btn-mode" onclick="setMode('AUTO')">TỰ ĐỘNG</button>
        <button class="btn btn-mode" onclick="setMode('MANUAL')">THỦ CÔNG</button>
    </div>
    
    <h3 id="mode-text" style="color:#e94560; margin-top:20px;">Đang ở chế độ: THỦ CÔNG</h3>
    <p style="font-size: 14px; color: #aaa;">Nhấn giữ nút để chạy, nhả tay ra để dừng.</p>

    <div class="grid">
        <div></div>
        <button class="btn" id="btn-fwd">▲</button>
        <div></div>
        <button class="btn" id="btn-left">◄</button>
        <div></div>
        <button class="btn" id="btn-right">►</button>
        <div></div>
        <button class="btn" id="btn-bwd">▼</button>
        <div></div>
    </div>

    <script>
        function sendCmd(cmd) { fetch('/cmd?val=' + cmd).catch(err => console.log(err)); }
        function setMode(mode) { 
            sendCmd('mode_' + mode.toLowerCase()); 
            document.getElementById('mode-text').innerText = 'Đang ở chế độ: ' + mode;
        }

        function setupButton(id, cmd) {
            let btn = document.getElementById(id);
            // Dành cho điện thoại (cảm ứng)
            btn.addEventListener('touchstart', function(e) { e.preventDefault(); sendCmd(cmd); });
            btn.addEventListener('touchend', function(e) { e.preventDefault(); sendCmd('stop'); });
            // Dành cho máy tính (chuột)
            btn.addEventListener('mousedown', function(e) { sendCmd(cmd); });
            btn.addEventListener('mouseup', function(e) { sendCmd('stop'); });
            btn.addEventListener('mouseleave', function(e) { sendCmd('stop'); });
        }

        setupButton('btn-fwd', 'forward');
        setupButton('btn-bwd', 'backward');
        setupButton('btn-left', 'left');
        setupButton('btn-right', 'right');
    </script>
</body>
</html>
"""

# =====================================================================
# LUONG WEB SERVER
# =====================================================================
def web_server_thread():
    global mode, manual_cmd
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid='XeTuHanh_AP', password='password123', authmode=3)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)
    print("Web Server OK! IP: 192.168.4.1")

    while True:
        try:
            conn, addr = s.accept()
            request = conn.recv(1024).decode('utf-8')
            if 'GET /cmd?val=' in request:
                cmd = request.split('GET /cmd?val=')[1].split(' ')[0]
                if cmd == 'mode_auto': mode = "AUTO"
                elif cmd == 'mode_manual': mode, manual_cmd = "MANUAL", "stop"
                elif mode == "MANUAL": manual_cmd = cmd
                conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\nOK')
            else:
                conn.send('HTTP/1.1 200 OK\nContent-Type: text/html\n\n' + HTML_PAGE)
            conn.close()
        except: pass

# =====================================================================
# LUONG CHINH
# =====================================================================
try:
    stop()
    set_angle(CENTER_ANGLE)
    _thread.start_new_thread(web_server_thread, ())
    current = 0
    print("He thong da san sang!")

    while True:
        if mode == "AUTO":
            d = distance()
            target = speed_for(d)
            current = ramp(current, target)
            if target == 0:
                current = 0
                avoid()
            else:
                drive(current, current)
            time.sleep_ms(30)
            
        elif mode == "MANUAL":
            if manual_cmd == "forward": drive(TURN_SPEED, TURN_SPEED)
            elif manual_cmd == "backward": drive(-TURN_SPEED, -TURN_SPEED)
            elif manual_cmd == "left": drive(-TURN_SPEED, TURN_SPEED)
            elif manual_cmd == "right": drive(TURN_SPEED, -TURN_SPEED)
            else: stop()
            time.sleep_ms(30)

except KeyboardInterrupt: print("Da dung xe")
finally: stop(); set_angle(CENTER_ANGLE)
