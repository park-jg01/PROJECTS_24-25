#drone_stop.py
from dronekit import connect, VehicleMode
import time

vehicle = connect('/dev/ttyAMA0', baud=57600, wait_ready=True)

print("착륙 모드로 변경 중...")
vehicle.mode = VehicleMode("LAND")
time.sleep(2)  # 모드 변경 대기

print("Disarm 시도 중...")
vehicle.armed = False

while vehicle.armed:
    print("Disarm 대기 중...")
    time.sleep(1)

print("✅ 드론 시동 꺼짐 (모터 정지 완료)")
vehicle.close()
