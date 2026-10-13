import base64
import io

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class BadImage(ValueError):
    pass


def load_bgr(data: bytes, max_long_side: int) -> np.ndarray:
    """Decode an uploaded photo, apply the phone's EXIF rotation, shrink the long side to max_long_side."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format == "JPEG":
            img.draft("RGB", (max_long_side, max_long_side))  # decode at a reduced scale: less memory and time
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Image.DecompressionBombError as e:
        raise BadImage(f"Image too large: {e}") from e
    except (UnidentifiedImageError, OSError) as e:
        raise BadImage(f"Not a readable image: {e}") from e
    if max(img.size) > max_long_side:
        img.thumbnail((max_long_side, max_long_side), Image.LANCZOS)
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def bgr_to_pil(img_bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))


def jpeg_base64(img_bgr: np.ndarray, max_width: int, quality: int) -> str:
    h, w = img_bgr.shape[:2]
    if w > max_width:
        img_bgr = cv2.resize(img_bgr, (max_width, max(1, round(h * max_width / w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise BadImage("Could not encode thumbnail")
    return base64.b64encode(buf.tobytes()).decode("ascii")
