"""
WebHTC Diagnostics Module
Performs system checks for SteamVR, VMT, and Camera status.
"""
import socket
import cv2
import psutil
import platform
import os
from localization import TRANSLATIONS

class SystemDiagnostics:
    def __init__(self, lang="EN"):
        self.lang = lang
        self.t = TRANSLATIONS.get(lang, TRANSLATIONS["EN"])
        
    def check_steamvr(self):
        """Checks if SteamVR (vrserver.exe) is running."""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in ['vrserver.exe', 'vrmonitor.exe']:
                return True, "SteamVR Detected"
        return False, "SteamVR Not Found"

    def check_vmt_driver(self):
        """Checks if VMT driver is installed in SteamVR."""
        # Method 1: Check running SteamVR process path
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] in ['vrserver.exe', 'vrmonitor.exe'] and proc.info['exe']:
                    # vrserver is usually in SteamVR/bin/win64/vrserver.exe
                    # We need to go up 3 levels to get to SteamVR/
                    steamvr_bin = os.path.dirname(proc.info['exe'])
                    steamvr_path = os.path.abspath(os.path.join(steamvr_bin, "../../.."))
                    vmt_path = os.path.join(steamvr_path, "drivers", "vmt")
                    if os.path.exists(vmt_path):
                        return True, "VMT Driver Found (Active SteamVR Path)"
            except: pass

        # Method 2: Check Registry (HKLM and HKCU)
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                base_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 250820"
                key = winreg.OpenKey(hive, base_key)
                steamvr_path, _ = winreg.QueryValueEx(key, "InstallLocation")
                if steamvr_path:
                    vmt_path = os.path.join(steamvr_path, "drivers", "vmt")
                    if os.path.exists(vmt_path):
                        return True, "VMT Driver Found in Registry Path"
            except: pass

        # Method 3: Common default paths
        for p in [r"C:\Program Files (x86)\Steam\steamapps\common\SteamVR\drivers\vmt",
                  r"D:\SteamLibrary\steamapps\common\SteamVR\drivers\vmt"]:
            if os.path.exists(p): return True, "VMT Found in Default Path"

        # Method 4: Port check
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('0.0.0.0', 39570))
            sock.close()
            return False, "VMT Driver Not Listening (Port 39570 Free)"
        except OSError:
            return True, "Port 39570 Busy (Likely VMT)"
            
    def check_cameras(self):
        """Checks for available cameras."""
        available = []
        for i in range(4):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        
        if available:
            return True, f"Cameras Found: {available}"
        return False, "No Cameras Detected"

    def run_all_checks(self):
        steam_ok, steam_msg = self.check_steamvr()
        vmt_ok, vmt_msg = self.check_vmt_driver()
        cam_ok, cam_msg = self.check_cameras()
        
        return {
            "steamvr": {"ok": steam_ok, "msg": steam_msg},
            "vmt": {"ok": vmt_ok, "msg": vmt_msg},
            "camera": {"ok": cam_ok, "msg": cam_msg}
        }
