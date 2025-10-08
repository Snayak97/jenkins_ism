FROM python:3.11-slim

WORKDIR /myapp

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY Backend/ ./

# Expose Flask port
EXPOSE 5000

# Run the application
CMD ["python", "run.py"]
