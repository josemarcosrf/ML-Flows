#!/bin/bash

# Simple ECS Fargate deployment script
# Make sure to configure AWS CLI and have necessary permissions

set -e

# Configuration - Update these values
FLOW_NAME="hello"
FLOW_PATH="flows/examples/hello_flow.py"
POOL_NAME="my-ecs-pool"
DEPLOYMENT_NAME="fargate-dummy"
echo "🚀 Starting Prefect Flow Deployment on AWS ECS Fargate..."


prefect deploy "${FLOW_PATH}:${FLOW_NAME}" \
  --name ${DEPLOYMENT_NAME} \
  --pool "${POOL_NAME}"


echo "✅ Deployment ${DEPLOYMENT_NAME} for flow ${FLOW_NAME} completed successfully!"
