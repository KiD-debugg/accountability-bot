# Dockerfile
# Tells Docker how to build and run the accountability bot

# Use official Python 3.12 slim image as the base
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first (allows Docker to cache this layer)
COPY requirements.txt .

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Tell Docker to run the bot when the container starts
CMD ["python", "bot.py"]