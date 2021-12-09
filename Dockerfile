FROM python:3.9-slim-buster 
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
WORKDIR /app
COPY bot /app/bot
CMD ["python", "-m", "bot"]