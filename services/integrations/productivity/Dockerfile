FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

ENV PYTHONPATH=/app

EXPOSE 8026

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8026"]
