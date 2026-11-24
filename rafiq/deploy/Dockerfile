FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home studio \
    && install -d -o studio -g studio /data
WORKDIR /app
COPY rafiq/studio/requirements.txt /tmp/studio-requirements.txt
RUN pip install --no-cache-dir -r /tmp/studio-requirements.txt
COPY rafiq/studio/ rafiq/studio/
COPY rafiq/notebooks/Rafiq_GPU_Job.ipynb rafiq/notebooks/Rafiq_GPU_Job.ipynb

ENV RAFIQ_DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1
USER studio
CMD ["python", "-m", "rafiq.studio", "--host", "0.0.0.0", "--port", "8787"]
