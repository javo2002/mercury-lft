# Use the official lightweight Python 3.12 image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies for building scientific libraries
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and essential build tools
RUN pip install --upgrade pip setuptools wheel

# Copy only the requirements file first (for Docker layer caching)
COPY requirements.txt .

# Install all Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application into the container
COPY . .

# Expose your app’s port (optional, for clarity)
EXPOSE 8080

# Set the command to run the development web server
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
