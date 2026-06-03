"""Rule-based zone classification from bbox position (per camera, per store).

Store 1 (ST1008) — Brigade Road Bangalore:
  CAM 1 - zone   → Floor cam, left side: Wall Units, Gondola 1+2
  CAM 2 - zone   → Floor cam, right side: Wall Units, Makeup Station
  CAM 3 - entry  → Glass door, customers enter from bottom of frame
  CAM 5 - billing → Cash counter, queue area

Store 2 (ST1076) — Mumbai:
  entry 1/2      → Glass-front entrance
  zone           → Full floor overhead: shelves, display, fragrance/nail, makeup
  billing_area   → Cash counter with LED panel
"""

from __future__ import annotations


class ZoneClassifier:
    def __init__(self, camera_id: str, store_id: str | None = None):
        self.camera_id = camera_id.upper()
        self.store_id = (store_id or "").upper()

        # Detect camera role
        self.is_entry = (
            "ENTRY" in self.camera_id
            or self.camera_id == "CAM3"
        )
        self.is_billing = (
            "BILLING" in self.camera_id
            or self.camera_id == "CAM5"
        )
        self.is_floor = not self.is_entry and not self.is_billing

        # Detect which store
        self.is_store1 = self.store_id in ("ST1008", "STORE_1")
        self.is_store2 = self.store_id in ("ST1076", "STORE_2")

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
            return self._classify_entry(cx, cy)
        if self.is_billing:
            return self._classify_billing(cx, cy)
        if self.is_floor:
            if self.is_store1:
                return self._classify_floor_store1(cx, cy)
            elif self.is_store2:
                return self._classify_floor_store2(cx, cy)
            return self._classify_floor_default(cx, cy)
        return "FOH"

    def _classify_entry(self, cx: float, cy: float) -> str | None:
        """Entry camera: detect entry threshold vs FOH."""
        if cy > 0.52:
            return "ENTRY_THRESHOLD"
        if cy < 0.55 and cx > 0.35:
            return "FOH"
        return None

    def _classify_billing(self, cx: float, cy: float) -> str | None:
        """Billing camera: counter strip and queue area."""
        if cx < 0.55 and cy > 0.25:
            return "BILLING"
        return None

    def _classify_floor_store1(self, cx: float, cy: float) -> str:
        """
        Store 1 floor layout (Brigade Road):
        - Top/back area: BOH (back of house)
        - Left wall: Wall Units 1-6
        - Right wall: Wall Units 7-15
        - Center: Gondola islands, FOH
        - Right mid: Makeup station area
        """
        # CAM1 covers left side
        if self.camera_id in ("CAM1",):
            if cy < 0.30:
                return "WALL_UNIT_LEFT"
            if 0.30 <= cy < 0.55:
                if cx < 0.5:
                    return "GONDOLA_2"
                return "GONDOLA_1"
            return "FOH"

        # CAM2 covers right side
        if self.camera_id in ("CAM2",):
            if cy < 0.30:
                return "WALL_UNIT_RIGHT"
            if 0.30 <= cy < 0.60:
                if cx > 0.55:
                    return "MAKEUP_STATION"
                return "FOH"
            return "FOH"

        return "FOH"

    def _classify_floor_store2(self, cx: float, cy: float) -> str:
        """
        Store 2 floor layout (Mumbai):
        - Top row: Brand shelves (Salon, TFS, Minimalis, Aqualogi, Foxtal, JC)
        - Left wall: Existing glass / backlit
        - Center: Fragrance & Nail Unit, FOH
        - Center-right: Makeup Units
        - Bottom row: Brand walls (Fac, Mars+Nybae, Mens, L'oreal, Beauty)
        - Far right: Cash Counter, Access area
        """
        if cy < 0.25:
            # Top brand shelf row
            if cx < 0.4:
                return "LEFT_SHELF"
            return "CENTER_DISPLAY"

        if cy > 0.75:
            # Bottom brand wall
            if cx > 0.7:
                return "LOREAL_WALL"
            if cx > 0.45:
                return "MENS_WALL"
            return "FOH"

        # Center area
        if 0.25 <= cy <= 0.75:
            if cx < 0.30:
                return "FRAGRANCE_NAIL"
            if cx > 0.75:
                return "BILLING"
            if 0.40 <= cx <= 0.65:
                return "MAKEUP_UNIT"
            return "FOH"

        return "FOH"

    def _classify_floor_default(self, cx: float, cy: float) -> str:
        """Fallback zone classification for unknown stores."""
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
