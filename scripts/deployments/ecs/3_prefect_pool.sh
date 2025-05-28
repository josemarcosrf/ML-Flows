#!/bin/bash

# Simple Prefect Pool setup script for AWS ECS Fargate
# This script sets up the necessary AWS infrastructure for running Prefect flows on ECS Fargate
# Make sure to configure Prefect CLI and have necessary permissions

set -e

# 👇 ================ Configuration - Update these values =================👇
POOL_NAME="my-ecs-pool"
# 👆 ================ Configuration - Update these values =================👆

echo "🎱 Starting Set Up for Prefect Pool..."

if prefect work-pool inspect ${POOL_NAME} >/dev/null 2>&1; then
    echo "✅ Prefect work pool '${POOL_NAME}' already exists."
else
    # 1. Create Prefect work pool for ECS
    echo "🔧 Creating Prefect work pool for ECS..."
    prefect work-pool create --type ecs ${POOL_NAME} \
        --description "ECS Fargate Pool for Prefect"

    echo "✅ Prefect work pool '${POOL_NAME}' created successfully."

    # 2. Update Prefect work pool with ECS configuration
    # NOTE: Ensure that ecs-job-template.json is properly configured
    # with your ECS settings
    echo "🔄 Updating Prefect work pool with ECS configuration..."
    prefect work-pool update ${POOL_NAME} \
        --base-job-template scripts/deployments/ecs/ecs-pool-job-template.json
fi

# 3. Run the Prefect Pool worker
echo "🚀 Starting Prefect Pool Worker..."
prefect worker start --pool ${POOL_NAME}

echo "✅ Prefect Pool ${POOL_NAME} setup completed successfully!"

