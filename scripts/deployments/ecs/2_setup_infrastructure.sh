#!/bin/bash

# Simple ECS Fargate infrastructure setup script
# Make sure to configure AWS CLI and have necessary permissions

set -e

# 👇 ================ Configuration - Update these values =================👇
AWS_REGION="eu-central-1"
AWS_ACCOUNT_ID="677276117552"
CLUSTER_NAME="prefect-fargate-cluster"
SERVICE_NAME="prefect-worker-service"
TASK_DEFINITION_NAME="prefect-worker-service"
# 👆 ================ Configuration - Update these values =================👆

echo "🚀 Starting Set Up for AWS Infrastructure..."

# 1. Create an ECS Task Execution Role
echo "👷 Creating ECS Task Execution Role..."
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document file://<(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# 2. Attach the AmazonECSTaskExecutionRolePolicy to the role
echo "🔗 Attaching policy to ECS Task Execution Role..."
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# 3. Create a VPC
echo "🏗️  Creating VPC..."
VPC_OUTPUT=$(aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=PrefectFargateVPC}]')

VPC_ID=$(echo "$VPC_OUTPUT" | jq -r '.Vpc.VpcId')
echo "✅ VPC created with ID: $VPC_ID"


# 4. Create an Internet Gateway and attach it to the VPC
echo "🌍 Creating Internet Gateway and attaching it to VPC..."
IGW_OUTPUT=$(aws ec2 create-internet-gateway \
    --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=PrefectFargateIGW}]')

IGW_ID=$(echo "$IGW_OUTPUT" | jq -r '.InternetGateway.InternetGatewayId')
echo "✅ Internet Gateway created with ID: $IGW_ID"

aws ec2 attach-internet-gateway \
  --internet-gateway-id ${VPC_ID} \
  --vpc-id ${VPC_ID}

# 6. Create subnets
echo "🌐 Creating subnets..."
# subnet A
SUBNET_A_OUTPUT=$(aws ec2 create-subnet \
    --vpc-id ${VPC_ID} \
    --cidr-block 10.0.1.0/24 \
    --availability-zone ${AWS_REGION} \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=PublicSubnetA}]')

SUBNET_A_ID=$(echo "$SUBNET_A_OUTPUT" | jq -r '.Subnet.SubnetId')
echo "✅ Subnet A created with ID: $SUBNET_A_ID"

aws ec2 modify-subnet-attribute \
  --subnet-id ${$SUBNET_A_ID} \
  --map-public-ip-on-launch

# subnet B
SUBNET_B_OUTPUT=$(aws ec2 create-subnet \
  --vpc-id ${VPC_ID} \
  --cidr-block 10.0.2.0/24 \
  --availability-zone ${AWS_REGION} \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=PublicSubnetB}]')

aws ec2 modify-subnet-attribute \
  --subnet-id ${$SUBNET_B_ID} \
  --map-public-ip-on-launch

# 7. Create route tables and routes
echo "🛣️ Creating route tables and routes..."
ROUTE_TABLE_OUTPUT=$(aws ec2 create-route-table \
    --vpc-id ${VPC_ID} \
    --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=PublicRouteTable}]')

ROUTE_TABLE_ID=$(echo "$ROUTE_TABLE_OUTPUT" | jq -r '.RouteTable.RouteTableId')
echo "✅ Route Table created with ID: $ROUTE_TABLE_ID"

aws ec2 create-route \
  --route-table-id ${ROUTE_TABLE_ID} \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id ${VPC_ID}

# 8. Associate route table with subnets
echo "🔗 Associating route table with subnets..."
aws ec2 associate-route-table \
  --subnet-id ${SUBNET_A_ID} \
  --route-table-id ${ROUTE_TABLE_ID}

aws ec2 associate-route-table \
  --subnet-id ${SUBNET_A_ID} \
  --route-table-id ${ROUTE_TABLE_ID}

# 9. Create security group
echo "🔒 Creating security group..."
SG_OUTPUT=$(aws ec2 create-security-group \
    --group-name PrefectFargateSG \
    --description "Allow outbound to Prefect Cloud" \
    --vpc-id ${VPC_ID})

SECURITY_GROUP_ID=$(echo "$SG_OUTPUT" | jq -r '.GroupId')
echo "✅ Security Group created with ID: $SECURITY_GROUP_ID"

# 9.a Authorize outbound traffic for the security group
aws ec2 authorize-security-group-egress \
  --group-id ${SECURITY_GROUP_ID} \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# 9.b Authorize all outbound traffic (optional, for testing purposes)
aws ec2 authorize-security-group-egress \
  --group-id <your-security-group-id> \
  --ip-permissions IpProtocol=-1,IpRanges=[{CidrIp=0.0.0.0/0}]

# 10. Create ECS cluster
echo "🏗️  Creating ECS cluster..."
aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION 2>/dev/null || \
aws ecs create-cluster --cluster-name $CLUSTER_NAME --capacity-providers FARGATE --region $AWS_REGION
aws ecs describe-clusters --cluster $CLUSTER_NAME

# 11. Create CloudWatch log group
echo "📝 Creating CloudWatch log group..."
aws logs create-log-group --log-group-name "/ecs/simple-flow" --region $AWS_REGION 2>/dev/null || true

# 12. Register task definition (update the JSON file with actual account ID first)
echo "📋 Registering task definition..."
sed "s/YOUR_ACCOUNT_ID/$AWS_ACCOUNT_ID/g; s/YOUR_REGION/$AWS_REGION/g" task-definition.json > task-definition-updated.json
aws ecs register-task-definition --cli-input-json file://task-definition-updated.json --region $AWS_REGION

# 13. Create or update service
echo "🚀 Creating/updating ECS service..."
aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION 2>/dev/null && \
aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --task-definition $TASK_DEFINITION_NAME --region $AWS_REGION || \
aws ecs create-service \
    --cluster $CLUSTER_NAME \
    --service-name $SERVICE_NAME \
    --task-definition $TASK_DEFINITION_NAME \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_A_ID},${SUBNET_B_ID}],securityGroups=[${SECURITY_GROUP_ID}],assignPublicIp=ENABLED}" \
    --region $AWS_REGION

echo "✅ Infrastructure creation completed!"
echo "📊 Check service status with:"
echo "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"
echo "📝 View logs with:"
echo "   aws logs tail /ecs/simple-flow --follow --region $AWS_REGION"


