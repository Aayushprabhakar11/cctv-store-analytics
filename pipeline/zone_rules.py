"""Rule-based zone classification from bbox position (per camera).

Tuned for high-angle retail store clips (1080p overhead / high-angle):
  entry.mp4      — glass door, customers enter from bottom of frame
  main_floor*.mp4 — wall gondolas top, makeup station right, FOH centre
  billing.mp4    — cash counter on left, queue in centre-left
"""

from __future__ import annotations


class ZoneClassifier:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id.upper()
        self.is_entry = "ENTRY" in self.camera_id
        self.is_billing = "BILLING" in self.camera_id
        self.is_floor = "MAIN" in self.camera_id or "FLOOR" in self.camera_id

    def classify_bbox(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        frame_shape: tuple,
    ) -> str | None:
        h, w = frame_shape[:2]
        cx = (x1 + x2) / 2 / w
        cy = (y1 + y2) / 2 / h

        if self.is_entry:
            # Door / threshold: lower half of frame (approach from camera side)
            if cy > 0.52:
                return "ENTRY_THRESHOLD"
            if cy < 0.55 and cx > 0.35:
                return "FOH"
            return None

        if self.is_billing:
            # Counter strip on left; queued customers centre-left
            if cx < 0.55 and cy > 0.25:
                return "BILLING"
            return None

        if self.is_floor:
            # Top third = wall bays (skincare / brands)
            if cy < 0.38:
                if cx < 0.35:
                    return "SKINCARE"
                if cx < 0.62:
                    return "FOH"
                return "MENS_CARE"
            # Centre gondola / aisle
            if 0.38 <= cy <= 0.72:
                if 0.35 < cx < 0.62:
                    return "FRAGRANCE"
                if cx >= 0.62:
                    return "MAKEUP"
                return "FOH"
            # Lower foreground
            return "FOH"

        # Fallback
        if cy < 0.35:
            return "SKINCARE"
        if cy > 0.65:
            return "MAKEUP"
        return "FOH"

    @staticmethod
    def staff_heuristic(frame, bbox: tuple[float, float, float, float]) -> bool:
        """Staff uniform detection — avoid flagging customers in dark clothing."""
        try:
            import cv2
            import numpy as np

            x1, y1, x2, y2 = map(int, bbox)
            crop = frame[max(0, y1) : y2, max(0, x1) : x2]
            if crop.size == 0:
                return False
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            purple_mask = cv2.inRange(hsv, (115, 50, 50), (150, 255, 255))
            purple_ratio = float(np.count_nonzero(purple_mask)) / purple_mask.size
            return purple_ratio > 0.30
        except Exception:
            return False
