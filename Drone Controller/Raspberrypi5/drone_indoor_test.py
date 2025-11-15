from dronekit import connect, VehicleMode
import serial
import time
import sys
import os
import csv

# === 포트 설정 ===
PLM_PORT = "/dev/ttyAMA3"
PIXHAWK_PORT = "/dev/serial0"

# === PWM 기본값 ===
ROLL_MIN, ROLL_MAX = 1450, 1550
PITCH_MIN, PITCH_MAX = 1450, 1550
YAW_MIN, YAW_MAX = 1450, 1550
THROTTLE_MIN, THROTTLE_MAX = 1000, 2000

neutral_pwm = 1500
roll_pwm = 1500
pitch_pwm = 1500
throttle_pwm = 1500
yaw_pwm = 1500

# === 상태 변수 ===
last_d3 = 0
current_mode = "ALT_HOLD"
ser = None


# === 시리얼 및 Pixhawk 연결 ===
def connect_devices():
    global ser
    print("PLM100 시리얼 연결 중...")
    try:
        ser = serial.Serial(PLM_PORT, baudrate=115200, timeout=10)
        ser.reset_input_buffer()
        time.sleep(1)
        print("PLM100 시리얼 연결 성공!")
    except Exception as e:
        print("시리얼 포트 열기 실패:", e)
        sys.exit(1)

    print("Pixhawk 연결 중...")
    vehicle = connect(PIXHAWK_PORT, wait_ready=True, baud=57600)
    print("Pixhawk 연결 완료!")

    # === 초기 모드 ALT_HOLD ===
    print("ALT_HOLD 모드로 전환 중...")
    vehicle.mode = VehicleMode("ALT_HOLD")
    time.sleep(2)

    # === ARM 시도 ===
    print("드론 ARM 시도 중...")
    vehicle.armed = True
    while not vehicle.armed:
        time.sleep(1)

    print("드론 시동 완료! ALT_HOLD 모드에서 대기 중.")
    print("조종기 수신 시작...")

    return ser, vehicle


# === 안전 정수 변환 ===
def safe_int(val):
    try:
        return int(val)
    except:
        return None


# === PWM 변환 ===
def adc_to_pwm(adc_val, invert=False, min_pwm=1000, max_pwm=2000):
    if adc_val is None:
        return 1500
    val = (65535 - adc_val) if invert else adc_val
    pwm = int(min_pwm + (val / 65535.0) * (max_pwm - min_pwm))
    pwm = max(min_pwm, min(pwm, max_pwm))
    if 1470 <= pwm <= 1530:
        pwm = 1500
    return pwm


# === 조이스틱 처리 ===
def handle_roll_pitch_yaw(x_val, y_val, yaw_val):
    roll = adc_to_pwm(x_val, invert=False, min_pwm=ROLL_MIN, max_pwm=ROLL_MAX)
    pitch = adc_to_pwm(y_val, invert=False, min_pwm=PITCH_MIN, max_pwm=PITCH_MAX)
    yaw = adc_to_pwm(yaw_val, invert=False, min_pwm=YAW_MIN, max_pwm=YAW_MAX)
    return roll, pitch, yaw


# === 쓰로틀 처리 ===
def handle_throttle(d1, d2):
    global throttle_pwm
    step = 50
    if d1 == 1:
        throttle_pwm = min(throttle_pwm + step, THROTTLE_MAX)
    elif d2 == 1:
        throttle_pwm = max(throttle_pwm - step, THROTTLE_MIN)
    else:
        throttle_pwm = 1500


# === D3 버튼: 착륙 / 재이륙 ===
def handle_d3_toggle(d3, vehicle):
    global last_d3, current_mode, throttle_pwm

    # === 실시간 상태 로그 (디버그용) ===
    print(f"[DEBUG] D3 입력 감지: {d3}, current_mode={current_mode}, armed={vehicle.armed}, mode={vehicle.mode.name}")

    if d3 == 1 and last_d3 == 0:
        print(f"[DEBUG] D3 눌림 감지 / 현재 상태: {current_mode} / Armed: {vehicle.armed}")

        # === 착륙 ===
        if vehicle.armed and current_mode == "ALT_HOLD":
            print("[D3] 착륙 명령 실행 중...")
            vehicle.mode = VehicleMode("LAND")
            time.sleep(1)
            while vehicle.mode.name != "LAND":
                time.sleep(0.5)

            for t in range(throttle_pwm, 1000, -50):
                vehicle.channels.overrides['3'] = t
                time.sleep(0.1)

            vehicle.armed = False
            while vehicle.armed:
                time.sleep(1)

            current_mode = "DISARMED"
            print("[DEBUG] 상태: DISARMED 으로 변경 완료")

        # === 재이륙 ===
        elif (not vehicle.armed) and current_mode in ["LAND", "DISARMED"]:
            print("[D3] 재이륙 시도 중...")
            print(f"[DEBUG] 모드 전환 시도 전: {vehicle.mode.name}")

            vehicle.mode = VehicleMode("ALT_HOLD")
            time.sleep(1)
            print(f"[DEBUG] 모드 전환 후: {vehicle.mode.name}")

            # === disarm 상태에서 강제 ARM 시도 (2회 반복) ===
            for i in range(2):
                print(f"[DEBUG] ARM 시도 {i+1}회차...")
                vehicle.armed = True
                time.sleep(2)
                print(f"[DEBUG] 현재 ARM 상태: {vehicle.armed}")
                if vehicle.armed:
                    print(f"[DEBUG] ARM 성공 (시도 {i+1}회차)")
                    break
                else:
                    print(f"[WARN] ARM 실패 (시도 {i+1}회차) 재시도 중...")

            if not vehicle.armed:
                print("[ERROR] 재이륙 실패: Pixhawk이 disarm 상태에서 명령을 무시함")
            else:
                throttle_pwm = 1500
                current_mode = "ALT_HOLD"
                print("[DEBUG] 재이륙 성공! ALT_HOLD 모드로 변경 완료.")

        last_d3 = 1

    elif d3 == 0:
        last_d3 = 0


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

                # --- 데이터 파싱 ---
                parts = text.split(",")
                x_val = y_val = yaw_val = bat_val = d1 = d2 = d3 = None
                for part in parts:
                    if "X=" in part:
                        x_val = safe_int(part.split("=")[1])
                    elif "Y=" in part:
                        y_val = safe_int(part.split("=")[1])
                    elif "YAW=" in part:
                        yaw_val = safe_int(part.split("=")[1])
                    elif "BAT=" in part:
                        bat_val = safe_int(part.split("=")[1].replace("%", ""))
                    elif "D1=" in part:
                        d1 = safe_int(part.split("=")[1])
                    elif "D2=" in part:
                        d2 = safe_int(part.split("=")[1])
                    elif "D3=" in part:
                        d3 = safe_int(part.split("=")[1])

                # === 버튼 / 조이스틱 처리 ===
                handle_d3_toggle(d3, vehicle)

                if not vehicle.armed:
                    roll_pwm = pitch_pwm = yaw_pwm = throttle_pwm = 1500
                else:
                    roll_pwm, pitch_pwm, yaw_pwm = handle_roll_pitch_yaw(x_val, y_val, yaw_val)
                    handle_throttle(d1, d2)

                # === PWM 적용 ===
                vehicle.channels.overrides = {
                    '1': roll_pwm,
                    '2': pitch_pwm,
                    '3': throttle_pwm,
                    '4': yaw_pwm
                }

                if vehicle.mode.name == "ALT_HOLD":
                    print(f"[OVERRIDE] R:{roll_pwm}  P:{pitch_pwm}  T:{throttle_pwm}  Y:{yaw_pwm}")

        except Exception as e:
            print("예외 발생:", e)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
