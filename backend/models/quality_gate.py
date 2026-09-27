import cv2
import numpy as np
from PIL import Image
from typing import Tuple


class QualityGate:
    """
    Stage 1: MobileNetV2 image quality classifier.
    Determines whether a meter photo is readable.

    Real implementation: loads weights from quality_gate_mobilenetv2.pt
    Current stub: uses Laplacian variance as a blurriness proxy.
    """

    BLUR_THRESHOLD = 100.0

    def predict(self, image_path: str) -> Tuple[str, float, str]:
        """
        Returns (status, confidence, guidance_message).
        status: "readable" | "unreadable"
        """
        try:
            img = Image.open(image_path).convert("RGB")
            img_array = np.array(img)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()

            if variance >= self.BLUR_THRESHOLD:
                return "readable", 0.92, ""
            else:
                guidance = (
                    "Image is too blurry. Please hold your phone steady, "
                    "clean the meter glass, and ensure good lighting."
                )
                return "unreadable", 0.45, guidance
        except Exception as e:
            return "unreadable", 0.0, f"Could not process image: {str(e)}"

    def predict_from_bytes(self, image_bytes: bytes) -> Tuple[str, float, str]:
        """Accepts raw image bytes instead of a file path."""
        import io
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        try:
            return self.predict(tmp_path)
        finally:
            os.unlink(tmp_path)
