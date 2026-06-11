FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 DATA_DIR=/app/data DATABASE_PATH=/app/data/meetings.db

EXPOSE 8000

CMD ["python", "start_server.py"]

