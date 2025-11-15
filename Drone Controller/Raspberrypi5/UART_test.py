#uart_test.py
# UART 통신 테스트 코드


import serial
import time

# === UART 포트 설정 ===
# PLM100이 연결된 포트 (라즈베리파이 5에서 AMA3 핀: GPIO21=RX, GPIO24=TX)
PORT = "/dev/ttyAMA3"
BAUD = 115200   # 실제 사용하는 모듈 속도에 맞게 수정 (예: 9600, 57600 등)

print("조종기 수신 시작...")

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
except Exception as e:
    print(f"포트 열기 실패: {e}")
    exit(1)

# === 수신 루프 ===
while True:
    if ser.in_waiting > 0:  # 버퍼에 데이터가 있으면
        data = ser.readline().decode(errors="ignore").strip()
        if data:
            print(f"[수신] {data}")
    else:
        # 디버깅용 (너무 자주 찍히면 주석 처리 가능)
        # print("대기 중...")
        pass
    time.sleep(0.1)
