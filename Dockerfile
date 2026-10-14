FROM python:3.12-slim
WORKDIR /app
COPY hunt.py monitor.py ./
RUN useradd --uid 10001 --create-home hunter && mkdir /data && chown hunter:hunter /data
USER hunter
VOLUME /data
CMD ["python", "monitor.py", "--data", "/data", "--send-telegram"]
