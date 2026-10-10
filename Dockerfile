FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8000"]
