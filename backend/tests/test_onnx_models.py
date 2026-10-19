"""ONNX serving (app/vision/onnx_models.py): the numpy steps match torchvision / Ultralytics / the decoder."""
import numpy as np
import pytest
from PIL import Image

from app.vision.onnx_models import decode_with_confidence, gate_input, letterbox, nms, postprocess, reader_input

GATE_CFG = {"input_size": [128, 384], "normalize_mean": [0.485, 0.456, 0.406], "normalize_std": [0.229, 0.224, 0.225]}


def photo(w=300, h=200, seed=0):
    return Image.fromarray(np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8))


def test_reader_input_matches_torchvision():
    import wasac_models

    img = photo()
    expected = wasac_models.eval_transform()(img.convert("RGB")).unsqueeze(0).numpy()
    assert np.allclose(reader_input(img), expected, atol=1e-6)


def test_gate_input_matches_torchvision():
    from torchvision import transforms

    img = photo(seed=1)
    tf = transforms.Compose([transforms.Resize((128, 384)), transforms.ToTensor(),
                             transforms.Normalize(GATE_CFG["normalize_mean"], GATE_CFG["normalize_std"])])
    assert np.allclose(gate_input(img, GATE_CFG), tf(img).unsqueeze(0).numpy(), atol=1e-5)


def test_ctc_decode_matches_the_torch_decoder():
    import torch
    import wasac_models

    rng = np.random.default_rng(3)
    for _ in range(20):
        logits = rng.normal(size=(32, 11)).astype(np.float32)
        log_probs = torch.from_numpy(logits).log_softmax(-1)
        raw, mean, low = wasac_models.decode_with_confidence(log_probs.unsqueeze(0))[0]
        got = decode_with_confidence(log_probs.numpy())
        assert got[0] == raw and got[1] == pytest.approx(mean, abs=1e-6) and got[2] == pytest.approx(low, abs=1e-6)


@pytest.mark.parametrize("shape, auto, out_shape, pad", [
    ((480, 640), True, (480, 640), (0, 0)),        # already a multiple of 32
    ((1080, 1920), True, (384, 640), (0, 12)),     # 360 rows -> padded to 384
    ((1080, 1920), False, (640, 640), (0, 140)),   # square
    ((1600, 1200), True, (640, 480), (0, 0)),
])
def test_letterbox(shape, auto, out_shape, pad):
    out, gain, got_pad = letterbox(np.zeros((*shape, 3), np.uint8), 640, auto=auto)
    assert out.shape[:2] == out_shape and got_pad == pad
    assert gain == pytest.approx(min(640 / shape[0], 640 / shape[1]))
    if pad[1]:
        assert (out[0] == 114).all()  # grey border


def test_nms_keeps_the_best_of_overlapping_boxes():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 10, 10], [20, 20, 30, 30]], float)
    assert nms(boxes, np.array([0.9, 0.8, 0.7]), 0.7).tolist() == [0, 2]


def test_postprocess_filters_suppresses_per_class_and_undoes_the_letterbox():
    # 4 anchors, 3 classes; boxes as centre x, centre y, width, height in letterboxed pixels.
    anchors = np.array([
        # cx,  cy,  w,  h, c0,  c1,  c2
        [100, 112, 40, 20, 0.9, 0.0, 0.0],
        [101, 112, 40, 20, 0.8, 0.0, 0.0],   # same class, overlapping: suppressed
        [101, 112, 40, 20, 0.0, 0.85, 0.0],  # other class, same place: kept
        [300, 300, 10, 10, 0.0, 0.0, 0.1],   # below conf
    ], dtype=np.float32)
    cls, xyxy, conf = postprocess(anchors.T[None], conf=0.15, gain=0.5, pad=(0, 12), orig_shape=(1000, 2000))
    assert sorted(cls.tolist()) == [0, 1]
    first = xyxy[cls.tolist().index(0)]
    assert first == pytest.approx([160, 180, 240, 220])  # ((100-20)/0.5, (112-10-12)/0.5, ...)


def test_registry_prefers_onnx_files(tmp_path, monkeypatch):
    from app.vision.models import ModelRegistry

    reg = ModelRegistry()
    reg.model_config = {"cropper": {"yolo_weights": "best.pt (Benax)"}}
    monkeypatch.delenv("VISION_BACKEND", raising=False)
    assert reg._use_onnx(tmp_path) is False
    (tmp_path / "best.onnx").write_bytes(b"x")
    assert reg._use_onnx(tmp_path) is True
    monkeypatch.setenv("VISION_BACKEND", "torch")
    assert reg._use_onnx(tmp_path) is False
