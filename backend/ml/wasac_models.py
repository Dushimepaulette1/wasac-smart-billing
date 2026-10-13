"""WASAC meter reading models, shared by the training notebook and the FastAPI backend."""
import torch
import torch.nn as nn
import torchvision
from torchvision import transforms
from PIL import Image

from wasac_preprocessing import pad_reading, digits_to_m3

BLANK = 10            # CTC blank symbol; digits are 0..9
NUM_CLASSES = 11
IMG_H, IMG_W = 64, 256


def eval_transform():
    return transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((IMG_H, IMG_W)),
        transforms.ToTensor(),
        transforms.Normalize([0.5], [0.5]),
    ])


def _conv(cin, cout):
    return [nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]


class CRNN(nn.Module):
    """CNN feature extractor -> 2-layer BiLSTM -> per-column symbol scores (32 columns)."""

    def __init__(self, num_classes=NUM_CLASSES, hidden=256):
        super().__init__()
        self.cnn = nn.Sequential(
            *_conv(1, 64), nn.MaxPool2d(2, 2),            # 64x256 -> 32x128
            *_conv(64, 128), nn.MaxPool2d(2, 2),          # -> 16x64
            *_conv(128, 256), *_conv(256, 256),
            nn.MaxPool2d(2, 2),                           # -> 8x32
            *_conv(256, 256), nn.Dropout2d(0.1),
            nn.MaxPool2d((2, 1)),                         # -> 4x32 (height only)
            nn.AdaptiveAvgPool2d((1, None)),              # -> 1x32
        )
        self.rnn = nn.LSTM(256, hidden, num_layers=2, bidirectional=True, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden * 2, num_classes)

    def forward(self, x):
        features = self.cnn(x).squeeze(2).permute(0, 2, 1)   # (batch, 32, 256)
        out, _ = self.rnn(features)
        return self.fc(out).log_softmax(-1)                  # (batch, 32, 11)


class ResNetGRU(nn.Module):
    """ResNet18 (layers 1-3) -> 2-layer BiGRU -> per-column symbol scores (32 columns)."""

    def __init__(self, num_classes=NUM_CLASSES, hidden=256, imagenet=False):
        super().__init__()
        weights = torchvision.models.ResNet18_Weights.IMAGENET1K_V1 if imagenet else None
        r = torchvision.models.resnet18(weights=weights)
        r.layer3[0].conv1.stride = (2, 1)            # shrink height only -> 32 columns
        r.layer3[0].downsample[0].stride = (2, 1)
        self.backbone = nn.Sequential(r.conv1, r.bn1, r.relu, r.maxpool, r.layer1, r.layer2, r.layer3)
        self.pool = nn.AdaptiveAvgPool2d((1, None))
        self.rnn = nn.GRU(256, hidden, num_layers=2, bidirectional=True, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden * 2, num_classes)

    def forward(self, x):
        if x.size(1) == 1:
            x = x.repeat(1, 3, 1, 1)                 # grayscale -> 3 channels for ResNet
        features = self.pool(self.backbone(x)).squeeze(2).permute(0, 2, 1)
        out, _ = self.rnn(features)
        return self.fc(out).log_softmax(-1)


def build_model(arch, imagenet=False):
    if arch == "crnn":
        return CRNN()
    if arch == "resnet_gru":
        return ResNetGRU(imagenet=imagenet)
    raise ValueError(f"Unknown architecture: {arch}")


def greedy_decode(log_probs):
    """CTC greedy decoding: best symbol per column, merge repeats, drop blanks."""
    texts = []
    for seq in log_probs.argmax(-1).cpu().numpy():
        out, prev = [], None
        for p in seq:
            if p != prev and p != BLANK:
                out.append(str(int(p)))
            prev = p
        texts.append("".join(out))
    return texts


def decode_with_confidence(log_probs):
    """Like greedy_decode, plus the mean and the lowest probability of the emitted digits."""
    probs = log_probs.exp()
    best_p, best_i = probs.max(-1)
    results = []
    for ps, ids in zip(best_p.cpu().numpy(), best_i.cpu().numpy()):
        out, conf, prev = [], [], None
        for p, i in zip(ps, ids):
            if i != prev and i != BLANK:
                out.append(str(int(i)))
                conf.append(float(p))
            prev = i
        results.append(("".join(out), sum(conf) / len(conf) if conf else 0.0, min(conf) if conf else 0.0))
    return results


class MeterReader:
    """Loads trained weights and reads a CROPPED meter display (see wasac_preprocessing.crop_display)."""

    def __init__(self, weights_path, arch="crnn", device="cpu"):
        self.device = torch.device(device)
        self.model = build_model(arch).to(self.device)
        self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
        self.model.eval()
        self.tf = eval_transform()

    @torch.no_grad()
    def read(self, image):
        if not isinstance(image, Image.Image):
            image = Image.open(image)
        x = self.tf(image.convert("RGB")).unsqueeze(0).to(self.device)
        raw, conf_mean, conf_min = decode_with_confidence(self.model(x))[0]
        padded = pad_reading(raw)
        return {
            "raw_digits": raw,                 # exactly what the model read
            "reading_digits": padded,          # 8 digits, or None if the length is impossible
            "reading_m3": digits_to_m3(padded),
            "confidence_mean": round(conf_mean, 4),
            "confidence_min": round(conf_min, 4),
            "needs_check": padded is None,
        }
