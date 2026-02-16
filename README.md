# 🛰️ WebHTC: XR Accessibility Suite

**WebHTC** is a professional-grade, high-performance full-body and hand tracking solution that uses standard webcams and neural networks to inject tracking data into SteamVR. No expensive Lighthouse base stations or specialized trackers required.

![WebHTC Demo](WebHTC.gif)

---

## 🚀 Key Features

*   **Neural Tracking Architecture**: Powered by MediaPipe for high-precision pose and hand estimation.
*   **Zero-Hardware FBT**: Full body tracking with just a single RGB webcam.
*   **Virtual Motion Tracker (VMT) Integration**: Seamless communication with SteamVR.
*   **Retro-Cyberpunk Interface**: Professional console-style dashboard with live feedback.
*   **System Diagnostics**: Built-in wizard to verify SteamVR and driver connectivity.
*   **Bilingual Support**: Full support for English and Russian operators.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
*   **SteamVR**: Must be installed and running.
*   **Python 3.8+**: Recommended version is 3.10.

### 2. Install VMT Driver (Crucial)
WebHTC transmits data via the **Virtual Motion Tracker** protocol.
1.  **Download**: Get the latest VMT release from [VMT GitHub](https://github.com/gpsnmeajp/VirtualMotionTracker/releases).
2.  **Install**:
    *   Extract the downloaded archive.
    *   Run `VMT_Manager.exe`.
    *   Click the **"Install"** button.
    *   Restart SteamVR.
3.  **SteamVR Configuration**:
    *   Open SteamVR Settings -> Manage Trackers.
    *   Ensure "VMT" trackers are assigned to the correct roles (Waist, Left Foot, Right Foot).

### 3. Clone & Install Dependencies
```bash
git clone https://github.com/yourusername/WebHTC.git
cd WebHTC
pip install -r requirements.txt
```

### 4. Running the Suite
```bash
python tracking.py
```

---

## 🎮 How to Use

1.  **Launch SteamVR** and ensure your headset is active.
2.  **Start WebHTC** and follow the **Boot Sequence** diagnostics.
3.  On the first run, the **Setup Wizard** will guide you through the handshake process.
4.  **Stand in view** of your camera (full body visibility recommended).
5.  Use the **Spatial Calibration** sliders in the dashboard to match your physical position with the VR space.
6.  **Pinch Gesture**: To trigger a "Click/Trigger" action in VR, join the tips of your thumb and index finger.

---

## 📂 Project Structure

*   `tracking.py`: Main application entry point and UI.
*   `tracking_engine.py`: Core neural processing and OSC transmission logic.
*   `diagnostics.py`: System health check and dependency verification.
*   `setup_wizard.py`: Multi-step onboarding for new users.
*   `boot_sequence.py`: Stylized startup splash screen.
*   `config_manager.py`: Persistent settings management.

---

## 🤝 Contributing & License

This project is open-source. Feel free to submit pull requests or report issues.
**License**: MIT

---

# 🛰️ WebHTC: XR Accessibility Suite (RU)

**WebHTC** — это профессиональное решение для трекинга всего тела и рук, которое использует обычную веб-камеру и нейронные сети для передачи данных в SteamVR. Никаких дорогих базовых станций или специальных трекеров.

## 🛠️ Установка и Настройка

### 1. Драйвер VMT (Обязательно)
WebHTC передает данные через протокол **Virtual Motion Tracker**.
1.  **Скачать**: Загрузите последнюю версию VMT с [VMT GitHub](https://github.com/gpsnmeajp/VirtualMotionTracker/releases).
2.  **Установить**:
    *   Распакуйте архив.
    *   Запустите `VMT_Manager.exe`.
    *   Нажмите кнопку **"Install"**.
    *   Перезапустите SteamVR.
3.  **Настройка SteamVR**:
    *   Настройки SteamVR -> Устройства -> Управление трекерами.
    *   Убедитесь, что трекеры VMT назначены на нужные роли (Пояс, Левая нога, Правая нога).

### 2. Клонирование и Запуск
```bash
git clone https://github.com/yourusername/WebHTC.git
cd WebHTC
```
### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```
### 4. Запуск
```bash
python tracking.py
```

---

Свободно для распространения и использования, при возникновении проблем, создайте свою ветку в issues.