"""
============================================================
 AI Hybrid Traffic Lights Control System
 Vehicle Detector Module — YOLOv8 Based
============================================================

 Detects and counts vehicles (car, truck, bus, motorcycle)
 in traffic camera frames using YOLOv8-nano model.

============================================================
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
import time


class VehicleDetector:
    """Detects and counts vehicles in camera frames using YOLOv8."""

    # COCO class IDs for vehicles
    VEHICLE_CLASSES = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

    def __init__(self, model_path=None, confidence=0.4):
        """
        Initialize the vehicle detector.

        Args:
            model_path: Path to YOLO model. If None, downloads yolov8n.pt automatically.
            confidence: Minimum confidence threshold for detections.
        """
        self.confidence = confidence

        if model_path and os.path.exists(model_path):
            self.model = YOLO(model_path)
        else:
            # Auto-download YOLOv8-nano (smallest, fastest)
            print("[DETECTOR] Downloading YOLOv8-nano model...")
            self.model = YOLO("yolov8n.pt")

        print(f"[DETECTOR] Model loaded. Confidence threshold: {self.confidence}")

    def count_vehicles(self, image_data):
        """
        Count vehicles in a JPEG image.

        Args:
            image_data: Raw JPEG bytes from ESP32-CAM.

        Returns:
            dict: {
                "count": int,
                "vehicles": [{"class": str, "confidence": float, "bbox": [x1,y1,x2,y2]}],
                "processing_time_ms": float
            }
        """
        start_time = time.time()

        # Decode JPEG bytes to OpenCV image
        np_arr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return {"count": 0, "vehicles": [], "processing_time_ms": 0, "error": "Failed to decode image"}

        # Run YOLO inference
        results = self.model(frame, conf=self.confidence, verbose=False)

        vehicles = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                # Only count vehicles
                if cls_id in self.VEHICLE_CLASSES:
                    bbox = box.xyxy[0].tolist()
                    vehicles.append({
                        "class": self.VEHICLE_CLASSES[cls_id],
                        "confidence": round(conf, 3),
                        "bbox": [round(c, 1) for c in bbox],
                    })

        processing_time = (time.time() - start_time) * 1000

        return {
            "count": len(vehicles),
            "vehicles": vehicles,
            "processing_time_ms": round(processing_time, 1),
        }

    def count_from_file(self, image_path):
        """Count vehicles from an image file on disk."""
        with open(image_path, "rb") as f:
            return self.count_vehicles(f.read())


# ── Standalone test ──
if __name__ == "__main__":
    detector = VehicleDetector()
    print("[TEST] Vehicle detector initialized successfully.")
    print("[TEST] Ready to process frames.")
