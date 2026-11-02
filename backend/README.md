# Mubazi: API

FastAPI backend of Mubazi, the WASAC water billing capstone project (African Leadership University).
It reads water-meter photos (YOLOv8 crop, MobileNetV2 quality gate, ResNet18+BiGRU reader), checks
each reading against the household's own history with rules, and bills it. An Isolation Forest was
evaluated on simulated data only and is not deployed.

Deployed as a Docker web service on Render (`../render.yaml`); the models run on ONNX Runtime.
The model files are **not** in this repository or the image: the container downloads them at start
from private links in the `MODEL_URLS` secret. Setup, configuration and the full project are
described in the main repository's README.

Health check: `GET /health`. API docs: `GET /docs`.
