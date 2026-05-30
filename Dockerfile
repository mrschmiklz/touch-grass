FROM python:3.12-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .

# Sidecar default: listen on all interfaces inside the private compose network.
# Do NOT publish this port to the host without adding authentication.
ENV TOUCH_GRASS_HOST=0.0.0.0 \
    TOUCH_GRASS_PORT=8765

EXPOSE 8765

# Run it with the ESP32 device passed through, e.g.:
#   docker run --device=/dev/ttyUSB0 touch-grass
ENTRYPOINT ["touch-grass", "serve"]
