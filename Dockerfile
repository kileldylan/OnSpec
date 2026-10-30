# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Keep the repository root as the working directory so project imports resolve.
WORKDIR /app

# Install system dependencies (needed for PostgreSQL and some Python packages)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY ACI_backend/requirements.txt /app/ACI_backend/requirements.txt
RUN pip install --no-cache-dir -r /app/ACI_backend/requirements.txt

# Copy the rest of the application
COPY ACI_backend/ /app/ACI_backend/

# Copy the start script and make it executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Run the start script
CMD ["/app/start.sh"]