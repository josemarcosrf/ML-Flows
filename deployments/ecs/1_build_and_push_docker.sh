#!/bin/bash

# Simple ECS Docker build and push script
# This script builds a Docker image and pushes it to AWS ECR
# Make sure to configure AWS CLI and have necessary permissions

set -e

# 👇 ================ Configuration - Update these values =================👇
read -p "Enter AWS_REGION [eu-central-1]: " AWS_REGION
AWS_REGION=${AWS_REGION:-eu-central-1}

read -p "Enter AWS_ACCOUNT_ID [677276117552]: " AWS_ACCOUNT_ID
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-677276117552}

read -p "Enter ECR_REPO_NAME [deus-flows]: " ECR_REPO_NAME
ECR_REPO_NAME=${ECR_REPO_NAME:-deus-flows}
# 👆 ================ Configuration - Update these values =================👆

echo "🚀 Starting Docker creation, tagging and push..."

# 1. Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository..."
aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${AWS_REGION} 2>/dev/null || \
aws ecr create-repository --repository-name ${ECR_REPO_NAME} --region ${AWS_REGION}

# 2. Get ECR login token and login to Docker
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com

# 3. Build Docker image
echo "🔨 Building Docker image..."
docker build --platform linux/amd64 -t ${ECR_REPO_NAME} .

# 4. Tag image for ECR
echo "🏷️  Tagging image..."
docker tag ${ECR_REPO_NAME}:latest "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

# 5. Push image to ECR
echo "⬆️  Pushing image to ECR..."
docker push "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"
