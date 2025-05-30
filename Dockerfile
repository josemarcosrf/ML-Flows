# Use the official Prefect image as a base
FROM prefecthq/prefect:3-latest


RUN mkdir -p /app

# Install any additional dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the flow files into the container
COPY flows/ /app/flows/

# Set the working directory
WORKDIR /app

# Default command (optional, usually overridden in deployments)
CMD ["python", "-m", "flows", "ls"]
