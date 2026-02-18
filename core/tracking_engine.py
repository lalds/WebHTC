"""
WebHTC Tracking Engine v2.0
Enhanced with logging, camera watchdog, knee/hip tracking, and VMC support
"""
import cv2
import mediapipe as mp
import numpy as np
import time
import math
import logging
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from pythonosc import udp_client

# Настройка логирования
LOG_FILE = "webhtc.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TrackingEngine")


class OneEuroFilter:
    """Адаптивный фильтр для сглаживания трекинга"""
    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None
        self._initialized = False

    def reset(self):
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None
        self._initialized = False

    def __call__(self, t, x):
        x = np.array(x, dtype=np.float64)
        if not self._initialized:
            self.x_prev = x.copy()
            self.dx_prev = np.zeros_like(x)
            self.t_prev = t
            self._initialized = True
            return x
        dt = t - self.t_prev
        if dt <= 0:
            return self.x_prev
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


class CameraWatchdog:
    """Мониторинг состояния камеры с авто-переподключением"""
    def __init__(self, device_id, max_retries=3, retry_delay=2.0):
        self.device_id = device_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retries = 0
        self.last_frame_time = 0
        self.frame_timeout = 5.0
        logger.info(f"CameraWatchdog initialized for device {device_id}")

    def check_frame_timeout(self):
        if self.last_frame_time > 0:
            elapsed = time.time() - self.last_frame_time
            return elapsed > self.frame_timeout
        return False

    def record_frame(self):
        self.last_frame_time = time.time()

    def should_retry(self):
        return self.retries < self.max_retries

    def increment_retry(self):
        self.retries += 1
        logger.warning(f"Camera retry {self.retries}/{self.max_retries}")

    def reset(self):
        self.retries = 0
        self.last_frame_time = 0


class TrackingQualityMonitor:
    """Мониторинг качества трекинга для графиков"""
    def __init__(self, window_size=60):
        self.window_size = window_size
        self.fps_history = []
        self.confidence_history = []
        self.latency_history = []

    def record(self, fps, confidence=1.0, latency=0.0):
        self.fps_history.append(fps)
        self.confidence_history.append(confidence)
        self.latency_history.append(latency)
        if len(self.fps_history) > self.window_size:
            self.fps_history.pop(0)
            self.confidence_history.pop(0)
            self.latency_history.pop(0)

    def get_stats(self):
        return {
            'fps_avg': np.mean(self.fps_history) if self.fps_history else 0,
            'fps_min': np.min(self.fps_history) if self.fps_history else 0,
            'confidence_avg': np.mean(self.confidence_history) if self.confidence_history else 0,
            'latency_avg': np.mean(self.latency_history) if self.latency_history else 0
        }


class TrackingEngine(QThread):
    frame_ready = Signal(np.ndarray)
    status_changed = Signal(str, str)
    fps_updated = Signal(int)
    calib_status = Signal(str, int)
    calib_done = Signal(float, float, float)
    log_msg = Signal(str, str)
    quality_data = Signal(dict)
    camera_lost = Signal()
    camera_restored = Signal()

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

        # VMT Client
        self.vmt_ip = self.cfg.get('network', 'vmt_ip')
        self.vmt_port = self.cfg.get('network', 'vmt_port')
        self.vmt = None
        self._init_vmt()

        # VMC Client (optional)
        self.use_vmc = self.cfg.get('network', 'use_vmc', default=False)
        self.vmc_ip = self.cfg.get('network', 'vmc_ip', default='127.0.0.1')
        self.vmc_port = self.cfg.get('network', 'vmc_port', default=39580)
        self.vmc = None
        if self.use_vmc:
            self._init_vmc()

        # Filters
        alpha_ui = self.cfg.get('tracking', 'smooth_factor')
        min_cutoff = max(0.01, 1.5 * (1.1 - alpha_ui))
        self.filters = {i: OneEuroFilter(min_cutoff=min_cutoff, beta=0.01) for i in range(100)}

        # Camera Watchdog
        self.watchdog = CameraWatchdog(self.cfg.get('camera', 'device_id'))
        self.camera_connected = False

        # Quality Monitor
        self.quality_monitor = TrackingQualityMonitor()

        # Tracker indices
        self.tracker_indices = {
            'head': self.cfg.get('trackers', 'head_index', default=0),
            'left_hand': self.cfg.get('trackers', 'left_hand_index', default=11),
            'right_hand': self.cfg.get('trackers', 'right_hand_index', default=12),
            'waist': self.cfg.get('trackers', 'waist_index', default=3),
            'left_knee': 4,
            'right_knee': 5,
            'left_hip': 6,
            'right_hip': 7,
            'left_foot': 8,
            'right_foot': 9
        }

        logger.info("TrackingEngine initialized")
        self.log_msg.emit("SYS", "Tracking engine initialized")

    def _init_vmt(self):
        try:
            self.vmt = udp_client.SimpleUDPClient(self.vmt_ip, self.vmt_port)
            logger.info(f"VMT client connected to {self.vmt_ip}:{self.vmt_port}")
        except Exception as e:
            logger.error(f"VMT initialization failed: {e}")
            self.log_msg.emit("ERR", f"VMT connection failed: {e}")

    def _init_vmc(self):
        try:
            self.vmc = udp_client.SimpleUDPClient(self.vmc_ip, self.vmc_port)
            logger.info(f"VMC client connected to {self.vmc_ip}:{self.vmc_port}")
        except Exception as e:
            logger.error(f"VMC initialization failed: {e}")
            self.log_msg.emit("ERR", f"VMC connection failed: {e}")

    def to_vr(self, x, y, z):
        return [(x - 0.5) * self.scale + self.offset_x,
                (0.5 - y) * self.scale + self.offset_y,
                self.offset_z - z * self.scale]

    def apply_filter(self, idx, pos):
        return self.filters[idx](time.time(), pos).tolist()

    def send_vmt(self, idx, pos, rotation=None):
        if self.vmt is None:
            return
        try:
            rot = rotation if rotation else [0.0, 0.0, 0.0, 1.0]
            msg = [int(idx), 1, 0.0] + [float(x) for x in pos] + [float(r) for r in rot]
            self.vmt.send_message("/VMT/Room/Unity", msg)
        except Exception as e:
            logger.debug(f"VMT send error: {e}")

    def send_vmc(self, bone_name, pos, rot=None):
        if self.vmc is None:
            return
        try:
            rotation = rot if rot else [0.0, 0.0, 0.0, 1.0]
            self.vmc.send_message("/VMC/Ext/Tr/Cal", [bone_name, 0, *pos, *rotation])
        except Exception as e:
            logger.debug(f"VMC send error: {e}")

    def start_calibration(self):
        self.calibrating = True
        self.calib_start_time = time.time()
        self.calib_samples = []
        logger.info("Calibration started")
        self.log_msg.emit("INFO", "Calibration started - stand in T-pose")

    def stop(self):
        self.running = False
        self.wait(2000)
        logger.info("TrackingEngine stopped")

    def reset_filters(self):
        for f in self.filters.values():
            f.reset()
        logger.debug("All filters reset")

    def run(self):
        logger.info("Starting tracking loop")

        mp_pose = mp.solutions.pose
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils

        pose = mp_pose.Pose(
            model_complexity=self.cfg.get('tracking', 'model_complexity'),
            min_detection_confidence=self.cfg.get('tracking', 'min_detection_confidence'),
            min_tracking_confidence=self.cfg.get('tracking', 'min_tracking_confidence'),
            static_image_mode=False
        )

        hands = None
        use_fingers = self.cfg.get('tracking', 'use_fingers')
        mode = self.cfg.get('tracking', 'mode')

        if use_fingers or mode == "Hands Only":
            hands = mp_hands.Hands(
                model_complexity=0,
                min_detection_confidence=0.3,
                min_tracking_confidence=0.3
            )

        cap = self._init_camera()
        if cap is None:
            self.log_msg.emit("ERR", "Failed to initialize camera")
            return

        last_time = time.time()
        frame_count = 0
        confidence_sum = 0

        while self.running:
            frame_start = time.time()

            # Watchdog check
            if self.watchdog.check_frame_timeout():
                logger.warning("Camera frame timeout detected")
                if self.camera_connected:
                    self.camera_connected = False
                    self.camera_lost.emit()
                    self.log_msg.emit("WARN", "Camera connection lost")

                if self.watchdog.should_retry():
                    self.watchdog.increment_retry()
                    cap.release()
                    time.sleep(self.watchdog.retry_delay)
                    cap = self._init_camera()
                    if cap:
                        self.camera_connected = True
                        self.camera_restored.emit()
                        self.log_msg.emit("INFO", "Camera reconnected")
                        self.watchdog.reset()
                continue

            ret, frame = cap.read()
            if not ret:
                continue

            self.watchdog.record_frame()
            if not self.camera_connected:
                self.camera_connected = True
                self.camera_restored.emit()

            if self.cfg.get('camera', 'flip_horizontal'):
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            tracking_active = False
            current_confidence = 0.0

            # --- POSE ---
            res_p = pose.process(rgb)
            if res_p.pose_landmarks:
                tracking_active = True
                lms = res_p.pose_landmarks.landmark
                current_confidence = res_p.pose_landmarks.visibility[0] if hasattr(res_p.pose_landmarks, 'visibility') else 1.0
                confidence_sum += current_confidence

                # Head
                if self.cfg.get('trackers', 'enable_head'):
                    head_pos = self.apply_filter(0, self.to_vr(lms[0].x, lms[0].y, lms[0].z))
                    self.send_vmt(self.tracker_indices['head'], head_pos)
                    if self.use_vmc:
                        self.send_vmc('Head', head_pos)

                # Waist
                if self.cfg.get('trackers', 'enable_waist'):
                    wx = (lms[23].x + lms[24].x) / 2
                    wy = (lms[23].y + lms[24].y) / 2
                    wz = (lms[23].z + lms[24].z) / 2
                    waist_pos = self.apply_filter(3, self.to_vr(wx, wy, wz))
                    self.send_vmt(self.tracker_indices['waist'], waist_pos)
                    if self.use_vmc:
                        self.send_vmc('Hips', waist_pos)

                # Knees (NEW)
                if self.cfg.get('trackers', 'enable_knees', default=False):
                    lk_pos = self.apply_filter(25, self.to_vr(lms[25].x, lms[25].y, lms[25].z))
                    self.send_vmt(self.tracker_indices['left_knee'], lk_pos)
                    rk_pos = self.apply_filter(26, self.to_vr(lms[26].x, lms[26].y, lms[26].z))
                    self.send_vmt(self.tracker_indices['right_knee'], rk_pos)

                # Hips (NEW)
                if self.cfg.get('trackers', 'enable_hips', default=False):
                    lh_pos = self.apply_filter(27, self.to_vr(lms[23].x, lms[23].y, lms[23].z))
                    self.send_vmt(self.tracker_indices['left_hip'], lh_pos)
                    rh_pos = self.apply_filter(28, self.to_vr(lms[24].x, lms[24].y, lms[24].z))
                    self.send_vmt(self.tracker_indices['right_hip'], rh_pos)

                # Feet
                if self.cfg.get('trackers', 'enable_feet', default=False):
                    lf_pos = self.apply_filter(29, self.to_vr(lms[27].x, lms[27].y, lms[27].z))
                    self.send_vmt(self.tracker_indices['left_foot'], lf_pos)
                    rf_pos = self.apply_filter(30, self.to_vr(lms[28].x, lms[28].y, lms[28].z))
                    self.send_vmt(self.tracker_indices['right_foot'], rf_pos)

                # Hands
                if not hands and self.cfg.get('trackers', 'enable_hands'):
                    p_l = self.apply_filter(11, self.to_vr(lms[15].x, lms[15].y, lms[15].z))
                    p_r = self.apply_filter(12, self.to_vr(lms[16].x, lms[16].y, lms[16].z))
                    self.send_vmt(self.tracker_indices['left_hand'], p_l)
                    self.send_vmt(self.tracker_indices['right_hand'], p_r)
                    if self.use_vmc:
                        self.send_vmc('LeftHand', p_l)
                        self.send_vmc('RightHand', p_r)

                    if self.cfg.get('visuals', 'show_skeleton'):
                        cv2.circle(frame, (int(lms[15].x*640), int(lms[15].y*480)), 6, (0, 255, 0), -1)
                        cv2.circle(frame, (int(lms[16].x*640), int(lms[16].y*480)), 6, (0, 255, 0), -1)

                # Calibration
                if self.calibrating and (time.time() - self.calib_start_time) >= 3.0:
                    fy = (lms[27].y + lms[28].y) / 2
                    self.calib_samples.append([[lms[0].x, lms[0].y, lms[0].z], [0, fy, 0]])

                if self.cfg.get('visuals', 'show_skeleton'):
                    mp_draw.draw_landmarks(frame, res_p.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # --- HANDS ---
            if hands and self.cfg.get('trackers', 'enable_hands'):
                res_h = hands.process(rgb)
                if res_h.multi_hand_landmarks:
                    for i, h_lms in enumerate(res_h.multi_hand_landmarks):
                        wrist = h_lms.landmark[0]
                        label = res_h.multi_handedness[i].classification[0].label
                        vmt_idx = self.tracker_indices['left_hand'] if label == 'Left' else self.tracker_indices['right_hand']
                        hand_pos = self.apply_filter(vmt_idx + 5, self.to_vr(wrist.x, wrist.y, wrist.z))
                        self.send_vmt(vmt_idx, hand_pos)
                        if self.use_vmc:
                            bone = 'LeftHand' if label == 'Left' else 'RightHand'
                            self.send_vmc(bone, hand_pos)

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
                        logger.info(f"Calibration complete: scale={self.scale:.2f}, offset_y={self.offset_y:.2f}")
                self.calibrating = False
                self.calib_status.emit("calib_success", 0)

            # --- QUALITY ---
            curr = time.time()
            dt = curr - last_time
            fps = int(1.0 / dt) if dt > 0 else 0
            frame_count += 1

            if frame_count % 30 == 0:
                avg_conf = confidence_sum / 30
                confidence_sum = 0
                latency = (curr - frame_start) * 1000
                self.quality_monitor.record(fps, avg_conf, latency)
                self.quality_data.emit(self.quality_monitor.get_stats())

            self.fps_updated.emit(fps)
            last_time = curr

            if not self.calibrating:
                status = "TRACKING" if tracking_active else "SEARCHING"
                color = "#a8ffbc" if tracking_active else "#ffaa00"
                self.status_changed.emit(status, color)

            self.frame_ready.emit(frame)

        cap.release()
        logger.info("Tracking loop ended")

    def _init_camera(self):
        device_id = self.cfg.get('camera', 'device_id')
        for attempt in range(3):
            cap = cv2.VideoCapture(device_id)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.get('camera', 'width', default=640))
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.get('camera', 'height', default=480))
                cap.set(cv2.CAP_PROP_FPS, self.cfg.get('camera', 'fps', default=60))
                logger.info(f"Camera initialized: {device_id}")
                return cap
            logger.warning(f"Camera attempt {attempt + 1} failed")
            time.sleep(1)

        logger.warning("Falling back to default camera (0)")
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            return cap
        return None
