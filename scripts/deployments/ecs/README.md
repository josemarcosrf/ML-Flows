# 🌉 Deploying Prefect 3 Flows on AWS ECS Fargate


This guide outlines the steps to deploy [Prefect 3 flows on AWS ECS Fargate](https://prefecthq.github.io/prefect-aws/ecs_guide/). It covers building and pushing Docker images, setting up AWS infrastructure, and configuring Prefect work pools.

## Prerequisites

* **AWS CLI**: Ensure you have the AWS CLI installed and configured with appropriate permissions.
* **Docker**: Install Docker to build and manage container images.
* **Prefect CLI**: Install the Prefect CLI for managing flows and deployments.

## 1. Build and Push Docker Image to Amazon ECR

### a. Build the Docker Image

```bash
docker build -t dummy-prefect-flow .
```

This command builds a Docker image named `dummy-prefect-flow` using the Dockerfile in the current directory.

### b. [Create an ECR Repository](https://prefecthq.github.io/prefect-aws/ecs_guide/#2-create-an-ecr-repository)

```bash
aws ecr create-repository --repository-name dummy-prefect-flow
```

Creates a new Amazon Elastic Container Registry (ECR) repository named `dummy-prefect-flow` to store your Docker images.

### c. Authenticate Docker with ECR

```bash
aws ecr get-login-password | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<region>.amazonaws.com
```

Authenticates your Docker client to your ECR registry. Replace `<your-aws-account-id>` and `<region>` with your AWS account ID and desired region.

### d. Tag and Push the Image

```bash
docker tag dummy-prefect-flow:latest <your-ecr-repo-uri>:latest
docker push <your-ecr-repo-uri>:latest
```

Tags your local image with the ECR repository URI and pushes it to ECR.

## 2. Set Up AWS Infrastructure

### a. [Create an IAM ECS Task Execution Role](https://prefecthq.github.io/prefect-aws/ecs_guide/#2-create-the-iam-roles)

```bash
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
```

Creates an IAM role named `ecsTaskExecutionRole` that allows ECS tasks to assume the role.

### b. [Attach Policies to the Role](https://prefecthq.github.io/prefect-aws/ecs_guide/#3-attach-the-policy-to-the-role)

```bash
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

Attaches the Amazon ECS Task Execution Role Policy to the role, granting necessary permissions for ECS tasks.

### c. Create a Virtual Private Cloud (VPC)

```bash
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=PrefectFargateVPC}]'
```

Creates a new VPC with the specified CIDR block and tags it for identification.

### d. Create and Attach an Internet Gateway

```bash
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=PrefectFargateIGW}]'

aws ec2 attach-internet-gateway \
  --internet-gateway-id <your-igw-id> \
  --vpc-id <your-vpc-id>
```

Creates an Internet Gateway and attaches it to your VPC to enable internet access.

### e. Create a Route Table and Route

```bash
aws ec2 create-route-table \
  --vpc-id <your-vpc-id> \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=PublicRouteTable}]'

aws ec2 create-route \
  --route-table-id <your-route-table-id> \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id <your-igw-id>
```

Creates a route table and adds a route to direct internet-bound traffic through the Internet Gateway.

### f. Create Public Subnets

#### Subnet A

```bash
aws ec2 create-subnet \
  --vpc-id <your-vpc-id> \
  --cidr-block 10.0.1.0/24 \
  --availability-zone <your-availability-zone-a> \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=PublicSubnetA}]'

aws ec2 modify-subnet-attribute \
  --subnet-id <your-subnet-a-id> \
  --map-public-ip-on-launch
```

#### Subnet B

```bash
aws ec2 create-subnet \
  --vpc-id <your-vpc-id> \
  --cidr-block 10.0.2.0/24 \
  --availability-zone <your-availability-zone-b> \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=PublicSubnetB}]'

aws ec2 modify-subnet-attribute \
  --subnet-id <your-subnet-b-id> \
  --map-public-ip-on-launch
```

Creates two public subnets in different availability zones and configures them to assign public IPs to instances launched within them.

### g. Associate Subnets with the Route Table

```bash
aws ec2 associate-route-table \
  --subnet-id <your-subnet-a-id> \
  --route-table-id <your-route-table-id>

aws ec2 associate-route-table \
  --subnet-id <your-subnet-b-id> \
  --route-table-id <your-route-table-id>
```

Associates both subnets with the public route table to enable internet access.

### h. Create a Security Group

```bash
aws ec2 create-security-group \
  --group-name PrefectFargateSG \
  --description "Allow outbound to Prefect Cloud" \
  --vpc-id <your-vpc-id>
```

Creates a security group named `PrefectFargateSG` within your VPC.

### i. Configure Security Group Rules

#### Allow Outbound HTTPS

```bash
aws ec2 authorize-security-group-egress \
  --group-id <your-security-group-id> \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

#### Allow All Outbound Traffic (Optional)

```bash
aws ec2 authorize-security-group-egress \
  --group-id <your-security-group-id> \
  --ip-permissions IpProtocol=-1,IpRanges=[{CidrIp=0.0.0.0/0}]
```

Configures the security group to allow outbound HTTPS traffic and optionally all outbound traffic.

## 3. Prefect Work Pool

### a. [Create a Prefect ECS work pool](https://prefecthq.github.io/prefect-aws/ecs_guide/#step-1-set-up-an-ecs-work-pool)

```bash
prefect work-pool create --type ecs my-ecs-pool
```

### b. Update the pool
> To compose the ecs-job-template you can first check: `prefect work-pool inspect my-ecs-pool`

```bash
prefect work-pool update my-ecs-pool \
    --base-job-template @ecs-job-template.json
```

Updates the Prefect work pool named `my-ecs-pool` with the specified base job template, configuring it to use the ECS cluster, task definition, and network settings you've set up.


## 4. Deploy the Flow

```bash
prefect deploy flows/dummy.py:hello \
  --name "fargate-dummy" \
  --pool my-ecs-pool
```

And finally, launch with:

```bash
prefect deployment run 'hello/fargate-dummy'
```

---

By following these steps, you can set up AWS ECS Fargate to run your Prefect 3 flows. Ensure you replace placeholders like `<your-aws-account-id>`, `<region>`, `<your-vpc-id>`, `<your-igw-id>`, `<your-route-table-id>`, `<your-subnet-a-id>`, `<your-subnet-b-id>`, `<your-availability-zone-a>`, `<your-availability-zone-b>`, and `<your-security-group-id>` with your actual AWS resource identifiers.

For more detailed guidance on deploying Prefect flows with AWS ECS Fargate, refer to the official Prefect documentation: [ECS Worker Guide - Prefect Docs](https://docs.prefect.io/integrations/prefect-aws/ecs_guide)

---
