# Use the official Prefect image as a base
FROM prefecthq/prefect:3-latest

# Copy your flow into the container
# TODO: Copy all the ./flows directory to the container
RUN mkdir -p /app
COPY flows/examples/hello_flow.py /app/flows/examples/hello_flow.py

# Set the working directory
WORKDIR /app

# Default command (optional, usually overridden in deployments)
CMD ["python", "flows/exmaples/hello_flow.py"]
