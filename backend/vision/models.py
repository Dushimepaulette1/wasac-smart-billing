"""Load the three models once, on CPU. A missing or broken file never stops the API from starting."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from vision.config import GuidanceConfig, load_model_config, weights_dir, yolo_weights_name

logger = logging.getLogger(__name__)

# model_config.json names the positive class ("unreadable") but not its index. The gate was trained
# with an ImageFolder-style alphabetical class order (readable=0, unreadable=1).
QUALITY_GATE_UNREADABLE_INDEX = 1

LOADED, MISSING, ERROR = "loaded", "missing", "error"


@dataclass
class ModelStatus:
    state: str
    detail: str = ""

    def label(self) -> str:
        return self.state if not self.detail else f"{self.state}: {self.detail}"


class QualityGate:
    """MobileNetV2 with a 2-class head; score() is P(unreadable) for a cropped number window."""

    def __init__(self, weights_path: Path, gate_config: dict):
        import torch
        import torchvision
        from torchvision import transforms

        model = torchvision.models.mobilenet_v2(weights=None)
        model.classifier[1] = torch.nn.Linear(model.last_channel, 2)
        model.load_state_dict(torch.load(weights_path, map_location="cpu"))
        self.model = model.eval()
        h, w = gate_config["input_size"]
        self.transform = transforms.Compose([
            transforms.Resize((h, w)),
            transforms.ToTensor(),
            transforms.Normalize(gate_config["normalize_mean"], gate_config["normalize_std"]),
        ])
        self.threshold = float(gate_config["threshold"])
        self._torch = torch

    def score(self, pil_image) -> float:
        with self._torch.no_grad():
            x = self.transform(pil_image.convert("RGB")).unsqueeze(0)
            probs = self._torch.softmax(self.model(x), dim=1)[0]
        return float(probs[QUALITY_GATE_UNREADABLE_INDEX])


class ModelRegistry:
    def __init__(self):
        self.yolo = None
        self.reader = None
        self.quality_gate: Optional[QualityGate] = None
        self.model_config: dict = {}
        self.guidance: Optional[GuidanceConfig] = None
        self.status: Dict[str, ModelStatus] = {
            name: ModelStatus(MISSING, "not loaded yet") for name in ("yolo", "reader", "quality_gate")
        }

    @property
    def ready(self) -> bool:
        """The photo pipeline needs the cropper and the reader; the quality gate is optional."""
        return self.yolo is not None and self.reader is not None

    def load(self, directory: Optional[Path] = None) -> "ModelRegistry":
        directory = Path(directory or weights_dir())
        self.model_config = load_model_config()
        self.guidance = GuidanceConfig.load(quality_threshold=self.model_config["quality_gate"]["threshold"])
        self.yolo = self._load("yolo", directory / yolo_weights_name(self.model_config), self._make_yolo)
        reader_cfg = self.model_config["reader"]
        self.reader = self._load("reader", directory / reader_cfg["weights"],
                                 lambda p: self._make_reader(p, reader_cfg["arch"]))
        gate_cfg = self.model_config["quality_gate"]
        self.quality_gate = self._load("quality_gate", directory / gate_cfg["weights"],
                                       lambda p: QualityGate(p, gate_cfg))
        return self

    def _load(self, name, path: Path, factory):
        if not path.exists():
            self.status[name] = ModelStatus(MISSING, str(path))
            logger.warning("Model %s missing at %s; the app will offer manual entry.", name, path)
            return None
        try:
            model = factory(path)
        except Exception as e:  # a corrupt or incompatible file must not stop the API
            self.status[name] = ModelStatus(ERROR, f"{type(e).__name__}: {e}")
            logger.exception("Could not load model %s from %s", name, path)
            return None
        self.status[name] = ModelStatus(LOADED, path.name)
        return model

    def _make_yolo(self, path: Path):
        from ultralytics import YOLO

        model = YOLO(str(path))
        model.predict(source=np.zeros((320, 320, 3), dtype=np.uint8), imgsz=320, device="cpu", verbose=False)
        return model

    @staticmethod
    def _make_reader(path: Path, arch: str):
        from PIL import Image
        from wasac_models import MeterReader

        reader = MeterReader(str(path), arch=arch, device="cpu")
        reader.read(Image.new("RGB", (256, 64)))
        return reader

    def guidance_config(self) -> GuidanceConfig:
        if self.guidance is None:
            self.guidance = GuidanceConfig.load(
                quality_threshold=load_model_config()["quality_gate"]["threshold"]
            )
        return self.guidance

    def health(self) -> Dict[str, str]:
        return {name: status.label() for name, status in self.status.items()}


registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    return registry
