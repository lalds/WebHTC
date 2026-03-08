## 2024-03-08 - Numpy float arrays in hot loops
**Learning:** Applying simple arithmetic (like `* 0.6`) to a sliced uint8 numpy array implicitly creates a large temporary float64 array before casting back. In a high-FPS video processing loop (like `ui/tracking.py`'s `update_video`), this array allocation and garbage collection causes measurable latency (approx 0.45ms per frame).
**Action:** Use `cv2.convertScaleAbs(array, alpha=0.6)` for direct C++ saturation casting. It operates ~3.5x faster by avoiding intermediate float array creation.
