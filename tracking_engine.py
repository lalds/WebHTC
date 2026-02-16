"""
WebHTC Pro - High-Performance Tracking Engine (V17.2)
Supports Hybrid Tracking (Pose + Hands)
"""
import cv2
import mediapipe as mp
import numpy as np
import time
from PySide6.QtCore import QThread, Signal
from pythonosc import udp_client

class TrackingEngine(QThread):
    frame_ready = Signal(np.ndarray)
    status_changed = Signal(str, str)
    fps_updated = Signal(int)
    
    def __init__(self, config_manager):
        super().__init__()
        self.cfg = config_manager
        self.running = True
        self.paused = False
        
        # Calibration (Real-time mutable)
        self.scale = self.cfg.get('calibration', 'scale')
        self.offset_x = self.cfg.get('calibration', 'offset_x')
        self.offset_y = self.cfg.get('calibration', 'offset_y')
        self.offset_z = self.cfg.get('calibration', 'offset_z')
        
        # OSC Client
        self.vmt = udp_client.SimpleUDPClient(
            self.cfg.get('network', 'vmt_ip'),
            self.cfg.get('network', 'vmt_port')
        )
        
        # Smoothers list (up to 30 markers for fingers if needed)
        alpha = self.cfg.get('tracking', 'smooth_factor')
        self.filters = {i: {"pos": None, "alpha": alpha} for i in range(50)}
        
    def apply_filter(self, idx, pos):
        f = self.filters[idx]
        if f["pos"] is None:
            f["pos"] = np.array(pos, dtype=np.float64)
        else:
            f["pos"] += (np.array(pos) - f["pos"]) * f["alpha"]
        return f["pos"].tolist()

    def send_vmt(self, idx, pos, quat=[0,0,0,1]):
        try:
            msg = [int(idx), 1, 0.0] + [float(x) for x in pos] + [float(x) for x in quat]
            self.vmt.send_message("/VMT/Room/Unity", msg)
        except: pass

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        # Init Models based on Mode
        mode = self.cfg.get('tracking', 'mode')
        use_fingers = self.cfg.get('tracking', 'use_fingers')
        
        mp_pose = mp.solutions.pose
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils
        
        # Always init Pose for body-active modes
        pose = None
        if "Body" in mode:
            pose = mp_pose.Pose(
                model_complexity=self.cfg.get('tracking', 'model_complexity'),
                min_detection_confidence=self.cfg.get('tracking', 'min_detection_confidence'),
                min_tracking_confidence=self.cfg.get('tracking', 'min_tracking_confidence')
            )
            
        hands = None
        if mode == "Hands Only" or use_fingers:
            hands = mp_hands.Hands(
                model_complexity=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )

        cap = cv2.VideoCapture(self.cfg.get('camera', 'device_id'))
        if not cap.isOpened(): cap = cv2.VideoCapture(0)
        
        # Performance settings
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.get('camera', 'width'))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.get('camera', 'height'))
        
        last_time = time.time()
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                self.status_changed.emit("CAM ERROR", "#ff5555")
                time.sleep(1)
                continue
                
            if self.cfg.get('camera', 'flip_horizontal'):
                frame = cv2.flip(frame, 1)
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            
            tracking_active = False
            
            # --- POSE PROCESSING ---
            if pose:
                results_pose = pose.process(rgb)
                if results_pose.pose_landmarks:
                    tracking_active = True
                    lms = results_pose.pose_landmarks.landmark
                    
                    def to_vr(x, y, z):
                        return [(x - 0.5) * self.scale + self.offset_x, 
                                (0.5 - y) * self.scale + self.offset_y, 
                                self.offset_z - z * self.scale]

                    # Basic tracking
                    if self.cfg.get('trackers', 'enable_head'):
                        p = self.apply_filter(0, to_vr(lms[0].x, lms[0].y, lms[0].z))
                        self.send_vmt(self.cfg.get('trackers', 'head_index'), p)
                    
                    # Wrists (if fingers disabled)
                    if self.cfg.get('trackers', 'enable_hands') and not use_fingers:
                        p_l = self.apply_filter(1, to_vr(lms[15].x, lms[15].y, lms[15].z))
                        p_r = self.apply_filter(2, to_vr(lms[16].x, lms[16].y, lms[16].z))
                        self.send_vmt(self.cfg.get('trackers', 'left_hand_index'), p_l)
                        self.send_vmt(self.cfg.get('trackers', 'right_hand_index'), p_r)
                    
                    if self.cfg.get('trackers', 'enable_waist'):
                        wx, wy, wz = (lms[23].x + lms[24].x)/2, (lms[23].y + lms[24].y)/2, (lms[23].z + lms[24].z)/2
                        p_w = self.apply_filter(3, to_vr(wx, wy, wz))
                        self.send_vmt(self.cfg.get('trackers', 'waist_index'), p_w)
                        
                    if self.cfg.get('visuals', 'show_skeleton'):
                        mp_draw.draw_landmarks(frame, results_pose.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # --- HANDS PROCESSING ---
            if hands:
                results_hands = hands.process(rgb)
                if results_hands.multi_hand_landmarks:
                    tracking_active = True
                    for i, hand_lms in enumerate(results_hands.multi_hand_landmarks):
                        # Simple wrist tracking for demo in this pass
                        wrist = hand_lms.landmark[0]
                        label = results_hands.multi_handedness[i].classification[0].label
                        idx = 1 if label == 'Left' else 2
                        
                        v_pos = [(wrist.x - 0.5) * self.scale + self.offset_x, 
                                 (0.5 - wrist.y) * self.scale + self.offset_y, 
                                 self.offset_z - wrist.z * self.scale]
                        
                        f_pos = self.apply_filter(idx + 10, v_pos) # High index for hands
                        # Note: VMT expects regular indices, so we map them
                        vmt_idx = self.cfg.get('trackers', 'left_hand_index') if label == 'Left' else self.cfg.get('trackers', 'right_hand_index')
                        self.send_vmt(vmt_idx, f_pos)
                        
                        if self.cfg.get('visuals', 'show_skeleton'):
                            mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

            # --- STATUS & FPS ---
            curr_time = time.time()
            fps = int(1.0 / (curr_time - last_time))
            last_time = curr_time
            self.fps_updated.emit(fps)
            self.status_changed.emit("TRACKING" if tracking_active else "SEARCHING", 
                                   "#a8ffbc" if tracking_active else "#ffaa00")
            
            self.frame_ready.emit(frame)

        cap.release()
