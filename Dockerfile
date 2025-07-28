# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY mfnewsscraper.py ./

# Set the default command to run the scraper
CMD ["uvicorn", "mfnewsscraper:app", "--host", "0.0.0.0", "--port", "8000"]
