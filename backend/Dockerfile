# WASAC Smart Water Billing API, for a Hugging Face Docker Space (free CPU).
# The model weights are NOT in the image: start.sh downloads them at container start from the
# private links in the MODEL_URLS secret. All configuration comes from environment variables.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Deployments never create the sample customers; DEMO- households are loaded by a script.
    SEED_SAMPLE_DATA=0 \
    # Ultralytics writes its settings file here instead of a read-only home.
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    PORT=7860

# Spaces run the container as user 1000.
RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
# CPU-only torch first (the default CUDA wheels are several GB), then the rest; requirements'
# torch==2.3.0 is satisfied by 2.3.0+cpu. Ultralytics pulls in GUI opencv-python, which needs X11
# libraries: remove it and keep only opencv-python-headless (same version, same cv2).
RUN pip install torch==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt \
 && pip uninstall -y opencv-python \
 && pip install --force-reinstall --no-deps opencv-python-headless==4.11.0.86

COPY --chown=user . .
RUN chmod +x start.sh

USER user
EXPOSE 7860
CMD ["./start.sh"]
