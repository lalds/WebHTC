import cv2
import mediapipe as mp
import time
import threading
import math
from pythonosc import udp_client

# --- КОНФИГУРАЦИЯ VMT ---
VMT_IP = "127.0.0.1"
VMT_PORT = 39570
UNITY_PORT = 39571

# Чувствительность и смещение
SCALE_XY = 5.0    # Множитель для движений (сделал больше)
OFFSET_Y = 1.0    # Высота (базовая)
OFFSET_Z = 2.0    # Базовая дистанция (теперь это "точка отсчета" для Z)

# Настройки для эмуляции
INDEX_HMD = 0
INDEX_LEFT = 1
INDEX_RIGHT = 2

class SmoothPose:
    """Класс для сглаживания движений и удержания позиции при потере трекинга"""
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.pos = [0, 0, 0]
        self.last_seen = 0

    def update(self, x, y, z):
        # Экспоненциальное сглаживание: new = old * (1-a) + current * a
        self.pos[0] = self.pos[0] * (1 - self.alpha) + x * self.alpha
        self.pos[1] = self.pos[1] * (1 - self.alpha) + y * self.alpha
        self.pos[2] = self.pos[2] * (1 - self.alpha) + z * self.alpha
        self.last_seen = time.time()
        return self.pos

class VMTClient:
    def __init__(self, ip, vmt_port, unity_port):
        self.vmt_client = udp_client.SimpleUDPClient(ip, vmt_port)
        self.unity_client = udp_client.SimpleUDPClient(ip, unity_port)
        print(f"OSC Clients: VMT:{vmt_port}, Unity:{unity_port}")

    def send_pose(self, index, x, y, z, qx=0, qy=0, qz=0, qw=1, is_active=1):
        msg = [
            int(index), int(is_active), float(0),
            float(x), float(y), float(z),
            float(qx), float(qy), float(qz), float(qw)
        ]
        try:
            self.vmt_client.send_message("/VMT/Room/Unity", msg)
            self.unity_client.send_message("/VMT/Room/Unity", msg)
        except: pass

class CameraStream:
    def __init__(self, src=0, width=160, height=120): # УМЕНЬШИЛ В 2 РАЗА
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.stream.set(cv2.CAP_PROP_FPS, 30)
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = False

    def start(self):
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while not self.stopped: (self.grabbed, self.frame) = self.stream.read()

    def read(self): return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

def calculate_depth(hand_landmarks):
    # Расстояние между запястьем (0) и основанием среднего пальца (9)
    p0 = hand_landmarks.landmark[0]
    p9 = hand_landmarks.landmark[9]
    dist = math.sqrt((p0.x - p9.x)**2 + (p0.y - p9.y)**2)
    if dist < 0.01: dist = 0.01
    return 0.15 / dist # Глубина Z

def main():
    global OFFSET_Y, OFFSET_Z, SCALE_XY
    mp_hands = mp.solutions.hands
    vmt = VMTClient(VMT_IP, VMT_PORT, UNITY_PORT)
    
    # Сглаживатели для обеих рук
    smoothers = { INDEX_LEFT: SmoothPose(0.4), INDEX_RIGHT: SmoothPose(0.4) }
    
    print("\n=== ULTRA FIX TRACKER 2.0 (Optimized) ===")
    print("[КЛАВИШИ В ОКНЕ ВИДЕО]")
    print("W/S - Вверх/Вниз | A/D - Дальше/Ближе | +/- - Чувствительность")
    
    user_input = input("Индекс камеры [1]: ")
    camera_idx = int(user_input) if user_input.strip().isdigit() else 1
    cam = CameraStream(src=camera_idx).start()

    start_time = time.time()
    
    # model_complexity=1 - лучше трекинг, confidence=0.7 - меньше ложных срабатываний
    with mp_hands.Hands(
        model_complexity=1, 
        min_detection_confidence=0.7, 
        min_tracking_confidence=0.7
    ) as hands:
        while True:
            t = time.time() - start_time
            # Минимальное шевеление HMD
            vmt.send_pose(INDEX_HMD, math.sin(t)*0.02, 1.7 + math.cos(t)*0.01, 0.0) 

            frame = cam.read()
            if frame is None: continue
            
            frame = cv2.flip(frame, 1)
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            active_indices = []

            if results.multi_hand_landmarks:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    label = results.multi_handedness[i].classification[0].label
                    idx = INDEX_LEFT if label == 'Right' else INDEX_RIGHT
                    
                    wrist = hand_landmarks.landmark[0]
                    depth = calculate_depth(hand_landmarks)
                    
                    # МАППИНГ С ИСПРАВЛЕННОЙ ИНВЕРСИЕЙ Z
                    vx = (wrist.x - 0.5) * SCALE_XY
                    vy = (0.5 - wrist.y) * SCALE_XY + OFFSET_Y
                    vz = OFFSET_Z - depth # ИНВЕРСИЯ: Чем меньше depth (ближе к камере), тем больше vz
                    
                    # Сглаживаем
                    sx, sy, sz = smoothers[idx].update(vx, vy, vz)
                    vmt.send_pose(idx, sx, sy, sz)
                    active_indices.append(idx)
                    
                    # Рисуем (на маленьком кадре)
                    h, w, _ = frame.shape
                    cv2.circle(frame, (int(wrist.x*w), int(wrist.y*h)), 5, (0, 255, 0), -1)

            # Если рука пропала, держим её на месте еще 0.5 сек, но слать не перестаем (чтобы не прыгала)
            for idx in [INDEX_LEFT, INDEX_RIGHT]:
                if idx not in active_indices:
                    # Если прошло меньше 0.5 сек с момента потери, продолжаем слать последнюю позицию
                    if time.time() - smoothers[idx].last_seen < 0.5:
                        vmt.send_pose(idx, *smoothers[idx].pos)

            # Показываем результат (увеличим окно для удобства, хотя кадр маленький)
            cv2.imshow('VR Tracker Lite', cv2.resize(frame, (320, 240)))
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            elif key == ord('w'): OFFSET_Y += 0.1
            elif key == ord('s'): OFFSET_Y -= 0.1
            elif key == ord('d'): OFFSET_Z += 0.1
            elif key == ord('a'): OFFSET_Z -= 0.1
            elif key == ord('='): SCALE_XY += 0.5
            elif key == ord('-'): SCALE_XY -= 0.5
    
    cam.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
