FROM python:3.11-slim

# Set up work directory in container
WORKDIR /app

# Copy dependency list to container
COPY requirements.txt .

# Install all dependencies to container
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (Flask default)
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]