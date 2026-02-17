import cv2
import mediapipe as mp
import numpy as np
import time
import math
from PySide6.QtCore import QThread, Signal
from pythonosc import udp_client

class OneEuroFilter:
    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def __call__(self, t, x):
        x = np.array(x, dtype=np.float64)
        if self.x_prev is None:
            self.x_prev = x
            self.dx_prev = np.zeros_like(x)
            self.t_prev = t
            return x
        dt = t - self.t_prev
        if dt <= 0: return self.x_prev
        a_d = self._alpha(dt, self.d_cutoff)
        dx = (x - self.x_prev) / dt
        edx = self.dx_prev + a_d * (dx - self.dx_prev)
        self.dx_prev = edx
        cutoff = self.min_cutoff + self.beta * np.abs(edx)
        a = self._alpha(dt, cutoff)
        ex = self.x_prev + a * (x - self.x_prev)
        self.x_prev = ex
        self.t_prev = t
        return ex

    def _alpha(self, dt, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

class TrackingEngine(QThread):
    frame_ready = Signal(np.ndarray)
    status_changed = Signal(str, str)
    fps_updated = Signal(int)
    calib_status = Signal(str, int)
    calib_done = Signal(float, float, float)
    log_msg = Signal(str, str)
    
    def __init__(self, config_manager):
        super().__init__()
        self.cfg = config_manager
        self.running = True
        self.calibrating = False
        self.calib_start_time = 0
        self.calib_samples = []
        
        self.scale = self.cfg.get('calibration', 'scale')
        self.offset_x = self.cfg.get('calibration', 'offset_x')
        self.offset_y = self.cfg.get('calibration', 'offset_y')
        self.offset_z = self.cfg.get('calibration', 'offset_z')
        
        self.vmt = udp_client.SimpleUDPClient(self.cfg.get('network', 'vmt_ip'), self.cfg.get('network', 'vmt_port'))
        
        alpha_ui = self.cfg.get('tracking', 'smooth_factor')
        min_cutoff = max(0.01, 1.5 * (1.1 - alpha_ui)) 
        self.filters = {i: OneEuroFilter(min_cutoff=min_cutoff, beta=0.01) for i in range(100)}

    def to_vr(self, x, y, z):
        return [(x - 0.5) * self.scale + self.offset_x, 
                (0.5 - y) * self.scale + self.offset_y, 
                self.offset_z - z * self.scale]

    def apply_filter(self, idx, pos):
        return self.filters[idx](time.time(), pos).tolist()

    def send_vmt(self, idx, pos):
        try:
            # Устанавливаем статус 'Авто' (1) и шлем координаты
            msg = [int(idx), 1, 0.0] + [float(x) for x in pos] + [0.0, 0.0, 0.0, 1.0]
            self.vmt.send_message("/VMT/Room/Unity", msg)
        except: pass

    def start_calibration(self):
        self.calibrating = True
        self.calib_start_time = time.time()
        self.calib_samples = []

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        mp_pose = mp.solutions.pose
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils
        
        pose = mp_pose.Pose(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        
        hands = None
        use_fingers = self.cfg.get('tracking', 'use_fingers')
        mode = self.cfg.get('tracking', 'mode')
        
        if use_fingers or mode == "Hands Only":
            hands = mp_hands.Hands(model_complexity=0, min_detection_confidence=0.3, min_tracking_confidence=0.3)

        cap = cv2.VideoCapture(self.cfg.get('camera', 'device_id'))
        if not cap.isOpened(): cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        last_time = time.time()

        while self.running:
            ret, frame = cap.read()
            if not ret: continue
            if self.cfg.get('camera', 'flip_horizontal'): frame = cv2.flip(frame, 1)
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            tracking_active = False

            # --- POSE ---
            res_p = pose.process(rgb)
            if res_p.pose_landmarks:
                tracking_active = True
                lms = res_p.pose_landmarks.landmark
                
                # Head, Waist, Feet
                if self.cfg.get('trackers', 'enable_head'):
                    self.send_vmt(0, self.apply_filter(0, self.to_vr(lms[0].x, lms[0].y, lms[0].z)))
                if self.cfg.get('trackers', 'enable_waist'):
                    wx, wy, wz = (lms[23].x+lms[24].x)/2, (lms[23].y+lms[24].y)/2, (lms[23].z+lms[24].z)/2
                    self.send_vmt(3, self.apply_filter(3, self.to_vr(wx, wy, wz)))
                if self.cfg.get('trackers', 'enable_feet'):
                    self.send_vmt(4, self.apply_filter(4, self.to_vr(lms[27].x, lms[27].y, lms[27].z)))
                    self.send_vmt(5, self.apply_filter(5, to_vr(lms[28].x, lms[28].y, lms[28].z)))

                # FAST HANDS (If full finger tracking is OFF)
                if not hands and self.cfg.get('trackers', 'enable_hands'):
                    # Шлем как ТРЕКЕРЫ (индексы выше 10), чтобы SteamVR не спрашивал раскладку кнопок
                    p_l = self.apply_filter(11, self.to_vr(lms[15].x, lms[15].y, lms[15].z))
                    p_r = self.apply_filter(12, self.to_vr(lms[16].x, lms[16].y, lms[16].z))
                    self.send_vmt(11, p_l)
                    self.send_vmt(12, p_r)
                    if self.cfg.get('visuals', 'show_skeleton'):
                        cv2.circle(frame, (int(lms[15].x*640), int(lms[15].y*480)), 6, (0, 255, 0), -1)
                        cv2.circle(frame, (int(lms[16].x*640), int(lms[16].y*480)), 6, (0, 255, 0), -1)

                if self.calibrating and (time.time()-self.calib_start_time) >= 3.0:
                    fy = (lms[27].y + lms[28].y)/2
                    self.calib_samples.append([[lms[0].x, lms[0].y, lms[0].z], [0, fy, 0]])

                if self.cfg.get('visuals', 'show_skeleton'):
                    mp_draw.draw_landmarks(frame, res_p.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # --- DETAILED HANDS ---
            if hands and self.cfg.get('trackers', 'enable_hands'):
                res_h = hands.process(rgb)
                if res_h.multi_hand_landmarks:
                    for i, h_lms in enumerate(res_h.multi_hand_landmarks):
                        wrist = h_lms.landmark[0]
                        label = res_h.multi_handedness[i].classification[0].label
                        # Тоже используем индексы 11/12 для избежания меню раскладки
                        vmt_idx = 11 if label == 'Left' else 12
                        self.send_vmt(vmt_idx, self.apply_filter(vmt_idx+5, self.to_vr(wrist.x, wrist.y, wrist.z)))
                        if self.cfg.get('visuals', 'show_skeleton'):
                            mp_draw.draw_landmarks(frame, h_lms, mp_hands.HAND_CONNECTIONS)

            # --- CALIB FINISH ---
            if self.calibrating and (time.time() - self.calib_start_time) >= 5.0:
                if self.calib_samples:
                    avg = np.mean(np.array(self.calib_samples), axis=0)
                    h_norm = avg[1][1] - avg[0][1]
                    if h_norm > 0.1:
                        self.scale = 1.7 / h_norm
                        self.offset_y = -(avg[0][1] * self.scale - 1.55)
                        self.calib_done.emit(self.scale, self.offset_y, self.offset_z)
                self.calibrating = False
                self.calib_status.emit("calib_success", 0)

            curr = time.time()
            self.fps_updated.emit(int(1.0 / (curr - last_time)) if curr > last_time else 0)
            last_time = curr
            if not self.calibrating:
                self.status_changed.emit("TRACKING" if tracking_active else "SEARCHING", "#a8ffbc")
            self.frame_ready.emit(frame)
        cap.release()
