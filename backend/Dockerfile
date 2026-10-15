# WASAC Smart Water Billing API (Render free web service, or any Docker host).
# The models run on ONNX Runtime: no PyTorch in the image, so it fits a 512 MB instance.
# The model files are NOT in the image: start.sh downloads the three .onnx files at container start
# from the private links in the MODEL_URLS secret. All configuration comes from environment variables.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Deployments never create the sample customers; DEMO- households are loaded by a script.
    SEED_SAMPLE_DATA=0 \
    MODEL_FORMAT=onnx \
    # Fewer malloc arenas: less memory kept back after large photos (512 MB instance).
    MALLOC_ARENA_MAX=2 \
    VISION_BACKEND=onnx \
    # Render sets PORT itself; this is the default elsewhere.
    PORT=7860

RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

COPY --chown=user requirements-serve.txt .
RUN pip install -r requirements-serve.txt

COPY --chown=user . .
RUN chmod +x start.sh

USER user
EXPOSE 7860
CMD ["./start.sh"]
