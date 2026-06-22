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
COPY index.html .

# Note: model.pth is optional and app will run with untrained model if not present
# To use a trained model, mount it as a volume or add it to the container

# Expose port
EXPOSE 7860

# Run the app with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "120", "wsgi:app"]
