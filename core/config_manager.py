"""
WebHTC Configuration Manager v2.0
With profiles support and export/import functionality
"""
import json
import os
import shutil
from datetime import datetime

CONFIG_FILE = "webhtc_config.json"
PROFILES_DIR = "profiles"

DEFAULT_CONFIG = {
    "network": {
        "vmt_ip": "127.0.0.1",
        "vmt_port": 39570,
        "use_vmc": False,
        "vmc_ip": "127.0.0.1",
        "vmc_port": 39580
    },
    "camera": {
        "device_id": 1,
        "width": 640,
        "height": 480,
        "fps": 60,
        "flip_horizontal": True
    },
    "tracking": {
        "mode": "Upper Body",
        "use_fingers": False,
        "model_complexity": 0,
        "min_detection_confidence": 0.77,
        "min_tracking_confidence": 0.75,
        "smooth_factor": 0.57,
        "static_image_mode": False
    },
    "visuals": {
        "show_skeleton": True,
        "neon_style": True,
        "show_hud": True,
        "language": "EN",
        "theme": "Terminal",
        "frame_reduction": 1,
        "overlay_mode": False,
        "show_tracker_overlay": True
    },
    "calibration": {
        "scale": 1.1912948602338154,
        "offset_x": 0.0,
        "offset_y": 1.0,
        "offset_z": 1.0,
        "rotation_y": 180.0
    },
    "trackers": {
        "enable_head": True,
        "enable_hands": True,
        "enable_waist": True,
        "enable_knees": False,
        "enable_hips": False,
        "enable_feet": False,
        "head_index": 0,
        "left_hand_index": 1,
        "right_hand_index": 2,
        "waist_index": 3
    },
    "system": {
        "first_run": False,
        "last_profile": "default",
        "auto_start": True,
        "minimize_to_tray": True
    },
    "profiles": {
        "active": "default"
    }
}


class ConfigManager:
    def __init__(self):
        self.config = self._deep_copy(DEFAULT_CONFIG)
        self.profiles = {}
        self.load()
        self._ensure_profiles_dir()

    def _deep_copy(self, d):
        """Глубокое копирование словаря"""
        return json.loads(json.dumps(d))

    def _ensure_profiles_dir(self):
        """Создание директории профилей"""
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)

    def load(self):
        """Загрузка конфигурации из файла"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self._deep_update(self.config, loaded)
            except Exception as e:
                print(f"Config load error: {e}")

        # Загрузка профилей
        self._load_profiles()

    def _load_profiles(self):
        """Загрузка всех профилей из директории"""
        self._ensure_profiles_dir()
        self.profiles = {"default": self._deep_copy(self.config)}

        for filename in os.listdir(PROFILES_DIR):
            if filename.endswith('.json'):
                profile_name = filename[:-5]
                try:
                    with open(os.path.join(PROFILES_DIR, filename), 'r', encoding='utf-8') as f:
                        self.profiles[profile_name] = json.load(f)
                except Exception as e:
                    print(f"Profile load error ({filename}): {e}")

    def save(self):
        """Сохранение конфигурации в файл"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")

    def _deep_update(self, base, update):
        """Рекурсивное обновление словаря"""
        for key, value in update.items():
            if isinstance(value, dict) and key in base:
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get(self, *keys, default=None):
        """Получение значения: get('camera', 'width', default=640)"""
        value = self.config
        for key in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(key)
            if value is None:
                return default
        return value

    def set(self, *args):
        """Установка значения: set('system', 'first_run', False)"""
        keys = args[:-1]
        value = args[-1]
        config = self.config
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    # === Profile Management ===

    def save_profile(self, name):
        """Сохранение текущего конфига как профиль"""
        self._ensure_profiles_dir()
        profile_data = self._deep_copy(self.config)
        profile_data['profiles']['active'] = name

        filepath = os.path.join(PROFILES_DIR, f"{name}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=4)

        self.profiles[name] = profile_data
        self.set('profiles', 'active', name)
        print(f"Profile '{name}' saved")

    def load_profile(self, name):
        """Загрузка профиля"""
        if name == "default":
            self.config = self._deep_copy(DEFAULT_CONFIG)
        elif name in self.profiles:
            self.config = self._deep_copy(self.profiles[name])
        else:
            filepath = os.path.join(PROFILES_DIR, f"{name}.json")
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.profiles[name] = self._deep_copy(self.config)
            else:
                return False

        self.set('profiles', 'active', name)
        print(f"Profile '{name}' loaded")
        return True

    def delete_profile(self, name):
        """Удаление профиля"""
        if name == "default":
            return False

        filepath = os.path.join(PROFILES_DIR, f"{name}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            if name in self.profiles:
                del self.profiles[name]
            return True
        return False

    def list_profiles(self):
        """Список всех профилей"""
        self._load_profiles()
        return list(self.profiles.keys())

    def get_active_profile(self):
        """Текущий активный профиль"""
        return self.get('profiles', 'active', default='default')

    # === Export/Import ===

    def export_config(self, filepath):
        """Экспорт конфигурации в файл"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False

    def import_config(self, filepath):
        """Импорт конфигурации из файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            self._deep_update(self.config, imported)
            self.save()
            return True
        except Exception as e:
            print(f"Import error: {e}")
            return False

    def backup_config(self):
        """Создание бэкапа конфигурации"""
        if os.path.exists(CONFIG_FILE):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"config_backup_{timestamp}.json"
            shutil.copy(CONFIG_FILE, backup_path)
            return backup_path
        return None

    def reset_to_defaults(self):
        """Сброс к настройкам по умолчанию"""
        self.config = self._deep_copy(DEFAULT_CONFIG)
        self.save()
