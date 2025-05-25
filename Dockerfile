# Use the official Prefect image as a base
FROM prefecthq/prefect:3-latest

# Copy your flow into the container
RUN mkdir -p /app
COPY flows/ /app/flows/
COPY requirements.txt /app/requirements.txt

# Install any additional dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set the working directory
WORKDIR /app

# Default command (optional, usually overridden in deployments)
CMD ["python", "-m", "flows", "ls"]
