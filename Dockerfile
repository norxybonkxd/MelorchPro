FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir flask flask-cors

# Copy application files
COPY app.py .
COPY config.py .
COPY tokenizer.py .
COPY model.py .
COPY model.pth .
COPY index.html .

# Expose port
EXPOSE 7860

# Run the app
CMD ["python", "-u", "app.py"]
