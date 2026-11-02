FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Tehran

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Database and logs live here; mount a volume so they survive container rebuilds.
RUN mkdir -p /app/backups
VOLUME /app/backups

CMD ["python", "main.py"]
