# WASAC Smart Water Billing: API

FastAPI backend of the WASAC Smart Water Billing capstone project (African Leadership University).
It reads water-meter photos (YOLOv8 crop, MobileNetV2 quality gate, ResNet18+BiGRU reader), checks
each reading against the household's own history (Isolation Forest plus rules), and bills it.

Deployed as a Docker web service on Render (`../render.yaml`); the models run on ONNX Runtime.
The model files are **not** in this repository or the image: the container downloads them at start
from private links in the `MODEL_URLS` secret. Setup, configuration and the full project are
described in the main repository's README.

Health check: `GET /health`. API docs: `GET /docs`.
