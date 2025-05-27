# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any - for SQLite, usually not needed beyond python)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package

# Install Python dependencies
# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# We use 0.0.0.0 to make the server accessible from outside the container
# Migrations should ideally be run as a separate step in a CI/CD pipeline or entrypoint script for production
# For simplicity in development, we can include it or run it manually after starting the container.
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# For a more robust startup, you might use an entrypoint script
# For now, let's ensure migrations can be run easily.
# The CMD will start the server. Migrations can be run via `docker exec` or before this CMD in a real setup.
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"] 