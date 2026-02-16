"""
WebHTC Configuration Manager
Handles all settings persistence and validation
"""
import json
import os

CONFIG_FILE = "webhtc_config.json"

DEFAULT_CONFIG = {
    "network": {
        "vmt_ip": "127.0.0.1",
        "vmt_port": 39570
    },
    "camera": {
        "device_id": 1,
        "width": 640,
        "height": 480,
        "fps": 30,
        "flip_horizontal": True
    },
    "tracking": {
        "mode": "Full Body",  # Options: "Full Body", "Upper Body", "Hands Only"
        "use_fingers": False,
        "model_complexity": 1,
        "min_detection_confidence": 0.5,
        "min_tracking_confidence": 0.5,
        "smooth_factor": 0.3,
        "static_image_mode": False
    },
    "visuals": {
        "show_skeleton": True,
        "neon_style": True,
        "show_hud": True,
        "language": "EN",
        "theme": "Matrix"     # Options: "Matrix", "Terminal", "Void"
    },
    "calibration": {
        "scale": 1.5,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "offset_z": 0.0,
        "rotation_y": 180.0
    },
    "trackers": {
        "enable_head": True,
        "enable_hands": True,
        "enable_waist": True,
        "head_index": 0,
        "left_hand_index": 1,
        "right_hand_index": 2,
        "waist_index": 3
    },
    "system": {
        "first_run": True
    }
}

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self):
        """Load configuration from JSON file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self._deep_update(self.config, loaded)
            except Exception as e:
                print(f"Config load error: {e}")
    
    def save(self):
        """Save configuration to JSON file"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")
    
    def _deep_update(self, base, update):
        """Recursively update nested dictionaries"""
        for key, value in update.items():
            if isinstance(value, dict) and key in base:
                self._deep_update(base[key], value)
            else:
                base[key] = value
    
    def get(self, *keys, default=None):
        """Get nested config value: get('camera', 'width', default=640)"""
        value = self.config
        for key in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(key)
            if value is None:
                return default
        return value
    
    def set(self, *args):
        """Set nested config value: set('system', 'first_run', False)"""
        keys = args[:-1]
        value = args[-1]
        config = self.config
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
