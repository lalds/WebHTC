"""
WebHTC Professional Settings GUI
Modern, commercial-grade interface with live preview
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sv_ttk

class SettingsGUI:
    def __init__(self, config_manager):
        self.cfg = config_manager
        self.root = tk.Tk()
        self.root.title("WebHTC Pro - Settings")
        self.root.geometry("700x650")
        self.root.resizable(False, False)
        
        # Apply modern theme
        try:
            sv_ttk.set_theme("dark")
        except:
            pass  # Fallback to default if sv_ttk not installed
        
        self.create_ui()
    
    def create_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1a1a2e", height=80)
        header.pack(fill=tk.X)
        
        title = tk.Label(header, text="WebHTC Professional", 
                        font=("Segoe UI", 24, "bold"), 
                        bg="#1a1a2e", fg="#00d9ff")
        title.pack(pady=20)
        
        subtitle = tk.Label(header, text="Full Body Tracking for SteamVR", 
                           font=("Segoe UI", 10), 
                           bg="#1a1a2e", fg="#888")
        subtitle.pack()
        
        # Main container with tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tabs
        self.create_network_tab(notebook)
        self.create_camera_tab(notebook)
        self.create_tracking_tab(notebook)
        self.create_calibration_tab(notebook)
        
        # Bottom buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="Reset to Defaults", 
                  command=self.reset_defaults).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Launch Tracker", 
                  command=self.save_and_launch, 
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(btn_frame, text="Save", 
                  command=self.save_config).pack(side=tk.RIGHT, padx=5)
    
    def create_network_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Network")
        
        # VMT Settings
        group = ttk.LabelFrame(frame, text="Virtual Motion Tracker", padding=15)
        group.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(group, text="IP Address:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vmt_ip = ttk.Entry(group, width=30)
        self.vmt_ip.insert(0, self.cfg.get('network', 'vmt_ip'))
        self.vmt_ip.grid(row=0, column=1, pady=5)
        
        ttk.Label(group, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.vmt_port = ttk.Spinbox(group, from_=1024, to=65535, width=28)
        self.vmt_port.set(self.cfg.get('network', 'vmt_port'))
        self.vmt_port.grid(row=1, column=1, pady=5)
        
        info = ttk.Label(group, text="ℹ️ Default VMT port is 39570", 
                        foreground="gray")
        info.grid(row=2, column=0, columnspan=2, pady=5)
    
    def create_camera_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Camera")
        
        group = ttk.LabelFrame(frame, text="Camera Settings", padding=15)
        group.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(group, text="Device ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cam_id = ttk.Spinbox(group, from_=0, to=10, width=28)
        self.cam_id.set(self.cfg.get('camera', 'device_id'))
        self.cam_id.grid(row=0, column=1, pady=5)
        
        ttk.Label(group, text="Resolution:").grid(row=1, column=0, sticky=tk.W, pady=5)
        res_frame = ttk.Frame(group)
        res_frame.grid(row=1, column=1, pady=5)
        
        self.cam_width = ttk.Combobox(res_frame, values=[320, 640, 1280], width=10)
        self.cam_width.set(self.cfg.get('camera', 'width'))
        self.cam_width.pack(side=tk.LEFT)
        
        ttk.Label(res_frame, text=" x ").pack(side=tk.LEFT)
        
        self.cam_height = ttk.Combobox(res_frame, values=[240, 480, 720], width=10)
        self.cam_height.set(self.cfg.get('camera', 'height'))
        self.cam_height.pack(side=tk.LEFT)
        
        ttk.Label(group, text="FPS:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.cam_fps = ttk.Combobox(group, values=[15, 30, 60], width=28)
        self.cam_fps.set(self.cfg.get('camera', 'fps'))
        self.cam_fps.grid(row=2, column=1, pady=5)
        
        self.flip_h = tk.BooleanVar(value=self.cfg.get('camera', 'flip_horizontal'))
        ttk.Checkbutton(group, text="Flip Horizontal (Mirror)", 
                       variable=self.flip_h).grid(row=3, column=0, columnspan=2, pady=5)
    
    def create_tracking_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Tracking")
        
        # Model Settings
        group1 = ttk.LabelFrame(frame, text="MediaPipe Model", padding=15)
        group1.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(group1, text="Complexity:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.model_complex = ttk.Combobox(group1, 
                                         values=["0 (Fast)", "1 (Balanced)", "2 (Accurate)"], 
                                         width=28, state="readonly")
        self.model_complex.current(self.cfg.get('tracking', 'model_complexity'))
        self.model_complex.grid(row=0, column=1, pady=5)
        
        ttk.Label(group1, text="Detection Confidence:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.det_conf = tk.DoubleVar(value=self.cfg.get('tracking', 'min_detection_confidence'))
        ttk.Scale(group1, from_=0.1, to=1.0, variable=self.det_conf, 
                 orient=tk.HORIZONTAL).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group1, textvariable=self.det_conf).grid(row=1, column=2, padx=5)
        
        ttk.Label(group1, text="Tracking Confidence:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.track_conf = tk.DoubleVar(value=self.cfg.get('tracking', 'min_tracking_confidence'))
        ttk.Scale(group1, from_=0.1, to=1.0, variable=self.track_conf, 
                 orient=tk.HORIZONTAL).grid(row=2, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group1, textvariable=self.track_conf).grid(row=2, column=2, padx=5)
        
        ttk.Label(group1, text="Smoothing:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.smooth = tk.DoubleVar(value=self.cfg.get('tracking', 'smooth_factor'))
        ttk.Scale(group1, from_=0.1, to=0.9, variable=self.smooth, 
                 orient=tk.HORIZONTAL).grid(row=3, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group1, textvariable=self.smooth).grid(row=3, column=2, padx=5)
        
        # Tracker Toggles
        group2 = ttk.LabelFrame(frame, text="Active Trackers", padding=15)
        group2.pack(fill=tk.X, padx=20, pady=10)
        
        self.enable_head = tk.BooleanVar(value=self.cfg.get('trackers', 'enable_head'))
        self.enable_hands = tk.BooleanVar(value=self.cfg.get('trackers', 'enable_hands'))
        self.enable_waist = tk.BooleanVar(value=self.cfg.get('trackers', 'enable_waist'))
        
        ttk.Checkbutton(group2, text="Head (HMD)", variable=self.enable_head).pack(anchor=tk.W)
        ttk.Checkbutton(group2, text="Hands (Wrists)", variable=self.enable_hands).pack(anchor=tk.W)
        ttk.Checkbutton(group2, text="Waist (Hip)", variable=self.enable_waist).pack(anchor=tk.W)
    
    def create_calibration_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Calibration")
        
        group = ttk.LabelFrame(frame, text="Position & Scale", padding=15)
        group.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(group, text="Scale (Sensitivity):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.scale = tk.DoubleVar(value=self.cfg.get('calibration', 'scale'))
        ttk.Scale(group, from_=0.5, to=3.0, variable=self.scale, 
                 orient=tk.HORIZONTAL).grid(row=0, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group, textvariable=self.scale).grid(row=0, column=2, padx=5)
        
        ttk.Label(group, text="Offset X (Left/Right):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.offset_x = tk.DoubleVar(value=self.cfg.get('calibration', 'offset_x'))
        ttk.Scale(group, from_=-2.0, to=2.0, variable=self.offset_x, 
                 orient=tk.HORIZONTAL).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group, textvariable=self.offset_x).grid(row=1, column=2, padx=5)
        
        ttk.Label(group, text="Offset Y (Height):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.offset_y = tk.DoubleVar(value=self.cfg.get('calibration', 'offset_y'))
        ttk.Scale(group, from_=-2.0, to=2.0, variable=self.offset_y, 
                 orient=tk.HORIZONTAL).grid(row=2, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group, textvariable=self.offset_y).grid(row=2, column=2, padx=5)
        
        ttk.Label(group, text="Offset Z (Depth):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.offset_z = tk.DoubleVar(value=self.cfg.get('calibration', 'offset_z'))
        ttk.Scale(group, from_=-2.0, to=2.0, variable=self.offset_z, 
                 orient=tk.HORIZONTAL).grid(row=3, column=1, sticky=tk.EW, pady=5)
        ttk.Label(group, textvariable=self.offset_z).grid(row=3, column=2, padx=5)
        
        info = ttk.Label(frame, text="💡 Tip: Adjust these in real-time using WASD keys during tracking", 
                        foreground="gray", wraplength=600)
        info.pack(pady=10)
    
    def save_config(self):
        """Save all settings to config"""
        try:
            # Network
            self.cfg.set('network', 'vmt_ip', self.vmt_ip.get())
            self.cfg.set('network', 'vmt_port', int(self.vmt_port.get()))
            
            # Camera
            self.cfg.set('camera', 'device_id', int(self.cam_id.get()))
            self.cfg.set('camera', 'width', int(self.cam_width.get()))
            self.cfg.set('camera', 'height', int(self.cam_height.get()))
            self.cfg.set('camera', 'fps', int(self.cam_fps.get()))
            self.cfg.set('camera', 'flip_horizontal', self.flip_h.get())
            
            # Tracking
            self.cfg.set('tracking', 'model_complexity', self.model_complex.current())
            self.cfg.set('tracking', 'min_detection_confidence', round(self.det_conf.get(), 2))
            self.cfg.set('tracking', 'min_tracking_confidence', round(self.track_conf.get(), 2))
            self.cfg.set('tracking', 'smooth_factor', round(self.smooth.get(), 2))
            
            # Trackers
            self.cfg.set('trackers', 'enable_head', self.enable_head.get())
            self.cfg.set('trackers', 'enable_hands', self.enable_hands.get())
            self.cfg.set('trackers', 'enable_waist', self.enable_waist.get())
            
            # Calibration
            self.cfg.set('calibration', 'scale', round(self.scale.get(), 2))
            self.cfg.set('calibration', 'offset_x', round(self.offset_x.get(), 2))
            self.cfg.set('calibration', 'offset_y', round(self.offset_y.get(), 2))
            self.cfg.set('calibration', 'offset_z', round(self.offset_z.get(), 2))
            
            self.cfg.save()
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")
    
    def save_and_launch(self):
        """Save and close to launch tracker"""
        self.save_config()
        self.root.destroy()
    
    def reset_defaults(self):
        """Reset all settings to defaults"""
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            from core.config_manager import DEFAULT_CONFIG
            self.cfg.config = DEFAULT_CONFIG.copy()
            self.cfg.save()
            self.root.destroy()
            self.__init__(self.cfg)
    
    def show(self):
        """Display the settings window"""
        self.root.mainloop()
