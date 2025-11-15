from dronekit import connect, VehicleMode
import serial
import time
import sys
import os
import csv


# === 로그 저장 경로 설정 ===
log_dir = "/home/isa/logger"
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, time.strftime("flight_log_%Y%m%d_%H%M%S.csv"))
log_file = open(log_path, "w", newline="")
csv_writer = csv.writer(log_file)
csv_writer.writerow([
    "Time", "Mode",
    "ROLL_PWM", "PITCH_PWM", "THROTTLE_PWM", "YAW_PWM",
    "X_ADC", "Y_ADC", "YAW_ADC", "BAT_ADC",
    "D1", "D2", "D3"
])

# === 포트 설정 ===
PLM_PORT = "/dev/ttyAMA3"
PIXHAWK_PORT = "/dev/serial0"

# === PWM 기본값 ===
min_pwm = 1000
max_pwm = 2000
neutral_pwm = 1500
roll_pwm = 1500
pitch_pwm = 1500
throttle_pwm = 1500
yaw_pwm = 1500

# === 버튼 및 모드 상태 ===
last_d3 = 0
current_mode = "ALT_HOLD"
d1_hold_start = None
d2_hold_start = None

# === 시리얼 및 Pixhawk 연결 ===
def connect_devices():
    print("PLM100 시리얼 연결 중...")
    try:
        ser = serial.Serial(PLM_PORT, baudrate=115200, timeout=1)
        ser.reset_input_buffer()
        time.sleep(1)
        print("PLM100 시리얼 연결 성공!")
    except Exception as e:
        print("시리얼 포트 열기 실패:", e)
        sys.exit(1)

    print("Pixhawk 연결 중...")
    vehicle = connect(PIXHAWK_PORT, wait_ready=True, baud=57600)
    print("Pixhawk 연결 완료!")
    vehicle.mode = VehicleMode("ALT_HOLD")
    time.sleep(2)
    print(f"현재 모드: {vehicle.mode.name}")

    print("드론 ARM 시도 중...")
    vehicle.armed = True
    while not vehicle.armed:
        print("ARM 대기 중...")
        time.sleep(1)
    print("드론 시동 완료!")
    print("조종기 수신 시작...")

    return ser, vehicle


# === 안전 정수 변환 ===
def safe_int(val):
    try:
        return int(val)
    except:
        return None


# === PWM 변환 함수 ===
def adc_to_pwm(adc_val, invert=False):
    if adc_val is None:
        return 1500
    val = (4095 - adc_val) if invert else adc_val
    pwm = int(min_pwm + (val / 4095.0) * (max_pwm - min_pwm))
    pwm = max(min_pwm, min(pwm, max_pwm))
    if 1470 <= pwm <= 1530:
        pwm = 1500
    return pwm


# === 쓰로틀 제어 ===
def handle_throttle(d1, d2):
    global throttle_pwm, d1_hold_start, d2_hold_start
    now = time.time()

    if d1 == 1:  # 상승
        if d1_hold_start is None:
            d1_hold_start = now
        hold_time = now - d1_hold_start
        if hold_time < 0.5:
            step = 10
        elif hold_time < 1.0:
            step = 20
        elif hold_time < 1.5:
            step = 30
        elif hold_time < 2.0:
            step = 40
        else:
            step = 50
        throttle_pwm = min(throttle_pwm + step, max_pwm)

    elif d2 == 1:  # 하강
        if d2_hold_start is None:
            d2_hold_start = now
        hold_time = now - d2_hold_start
        if hold_time < 0.5:
            step = 10
        elif hold_time < 1.0:
            step = 20
        elif hold_time < 1.5:
            step = 30
        elif hold_time < 2.0:
            step = 40
        else:
            step = 50
        throttle_pwm = max(throttle_pwm - step, min_pwm)
    else:
        d1_hold_start = None
        d2_hold_start = None
        throttle_pwm = 1500


# === 착륙 및 재이륙 제어 ===
def handle_d3_toggle(d3, vehicle):
    global last_d3, current_mode, throttle_pwm
    if d3 is not None and last_d3 == 0 and d3 == 1:
        # --- 비행 중일 때: 착륙 ---
        if current_mode == "ALT_HOLD" and vehicle.armed:
            print("[D3] 착륙 명령 실행 중...")
            vehicle.mode = VehicleMode("LAND")
            current_mode = "LAND"

            # 쓰로틀 천천히 낮추고 안전하게 Disarm
            for t in range(throttle_pwm, 1000, -50):
                vehicle.channels.overrides['3'] = t
                time.sleep(0.1)
            print("Disarm 시도 중...")
            vehicle.armed = False
            while vehicle.armed:
                print("Disarm 대기 중...")
                time.sleep(1)
            print("모터 정지 완료")

        # --- 착륙 완료 후 D3 눌림: 재이륙 ---
        elif not vehicle.armed and current_mode == "LAND":
            print("[D3] 재이륙 시도 중...")
            vehicle.mode = VehicleMode("LOITER")
            time.sleep(2)
            vehicle.armed = True
            while not vehicle.armed:
                print("ARM 대기 중...")
                time.sleep(1)
            print("드론 시동 완료! LOITER 모드 진입")
            current_mode = "LOITER"

        last_d3 = d3
    elif d3 is not None:
        last_d3 = d3


# === 로그 기록 ===
def log_data(x_val, y_val, yaw_val, bat_val, d1, d2, d3, vehicle):
    csv_writer.writerow([
        time.strftime("%H:%M:%S"),
        current_mode,
        roll_pwm, pitch_pwm, throttle_pwm, yaw_pwm,
        x_val or 0, y_val or 0, yaw_val or 0,
        bat_val or 0, d1 or 0, d2 or 0, d3 or 0
    ])
    log_file.flush()


# === 메인 루프 ===
def main():
    global roll_pwm, pitch_pwm, yaw_pwm, throttle_pwm
    ser, vehicle = connect_devices()

    while True:
        try:
            if ser.in_waiting > 0:
                raw = ser.readline()
                text = raw.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue

                # --- 입력 파싱 ---
                parts = text.split(",")
                x_val = y_val = yaw_val = bat_val = d1 = d2 = d3 = None

                for part in parts:
                    if "X=" in part: x_val = safe_int(part.split("=")[1])
                    elif "Y=" in part: y_val = safe_int(part.split("=")[1])
                    elif "YAW=" in part: yaw_val = safe_int(part.split("=")[1])
                    elif "BAT=" in part: bat_val = safe_int(part.split("=")[1].replace("%", ""))
                    elif "D1=" in part: d1 = safe_int(part.split("=")[1])
                    elif "D2=" in part: d2 = safe_int(part.split("=")[1])
                    elif "D3=" in part: d3 = safe_int(part.split("=")[1])

                # === 착륙/이륙 제어 ===
                handle_d3_toggle(d3, vehicle)

                # === 착륙 상태일 때 입력 무시 ===
                if not vehicle.armed:
                    roll_pwm = 1500
                    pitch_pwm = 1500
                    yaw_pwm = 1500
                    throttle_pwm = 1000
                else:
                    roll_pwm = adc_to_pwm(x_val)
                    pitch_pwm = adc_to_pwm(y_val, invert=True)
                    yaw_pwm = adc_to_pwm(yaw_val)
                    handle_throttle(d1, d2)

                # === PWM 적용 ===
                vehicle.channels.overrides = {
                    '1': roll_pwm,
                    '2': pitch_pwm,
                    '3': throttle_pwm,
                    '4': yaw_pwm
                }

                if vehicle.mode.name in ("ALT_HOLD", "LOITER"):
                    print(f"[OVERRIDE] R:{roll_pwm}, P:{pitch_pwm}, T:{throttle_pwm}, Y:{yaw_pwm}")

                # === 로그 기록 ===
                log_data(x_val, y_val, yaw_val, bat_val, d1, d2, d3, vehicle)

        except Exception as e:
            print("예외 발생:", e)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
