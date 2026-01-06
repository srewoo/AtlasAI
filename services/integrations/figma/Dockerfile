FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

# Install base module
COPY ../base /app/base
RUN pip install -e /app/base || true

ENV PYTHONPATH=/app

EXPOSE 8018

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8018"]
