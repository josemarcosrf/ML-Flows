#!/bin/bash

# Simple ECS Fargate deployment script
# Make sure to configure AWS CLI and have necessary permissions

set -e

# 👇 ================ Configuration - Update these values =================👇
# Indexing flow configuration
# FLOW_NAME="index_files"
# FLOW_PATH="flows/preproc/__init__.py"
# POOL_NAME="my-ecs-pool"
# DEPLOYMENT_NAME="preproc.deus.dev" # Should match the deployment name in prefect.yaml

# PlaybookQA flow configuration
FLOW_NAME="playbook_qa"
FLOW_PATH="flows/shrag/__init__.py"
POOL_NAME="my-ecs-pool"
DEPLOYMENT_NAME="shrag.deus.dev" # Should match the deployment name in prefect.yaml

# Dummy flow configuration
# FLOW_NAME="hello"
# FLOW_PATH="flows/examples/hello_flow.py"
# POOL_NAME="my-ecs-pool"
# DEPLOYMENT_NAME="fargate-dummy" # Should match the deployment name in prefect.yaml

# 👆 ================ Configuration - Update these values =================👆

echo "🚀 Starting Prefect Flow Deployment on AWS ECS Fargate..."


prefect deploy "${FLOW_PATH}:${FLOW_NAME}" \
  --name ${DEPLOYMENT_NAME} \
  --pool "${POOL_NAME}" \
  --prefect-file prefect.yaml


echo "✅ Deployment ${DEPLOYMENT_NAME} for flow ${FLOW_NAME} completed successfully!"
