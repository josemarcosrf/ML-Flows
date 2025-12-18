# Use the official Prefect image as a base
FROM prefecthq/prefect:3-latest

# We might need some additional system dependencies,
# Docling seems to fail due to missing libGL.so.1
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app

# Install any additional dependencies
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install -r /app/requirements.txt

# Copy the flow files into the container
COPY flows/ /app/flows/

# Set the working directory
WORKDIR /app

# Default command (optional, usually overridden in deployments)
CMD ["python", "-m", "flows", "ls"]
