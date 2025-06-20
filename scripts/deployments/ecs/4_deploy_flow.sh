#!/bin/bash

# Simple ECS Fargate deployment script
# Make sure to configure AWS CLI and have necessary permissions

set -e

# ================ Flow Selector =================
flows=(
  "index_document_file|flows/preproc/__init__.py|preproc.deus.dev"
  "run_qa_playbook|flows/shrag/__init__.py|shrag.deus.dev"
  "hello|flows/examples/hello_flow.py|fargate-dummy"
)

printf "\nAvailable Flows to Deploy:\n"
printf "%-3s %-25s %-40s %-20s\n" "No." "Flow Name" "Path" "Deployment Name"
for i in "${!flows[@]}"; do
  IFS='|' read -r fname fpath dname <<< "${flows[$i]}"
  printf "%-3s %-25s %-40s %-20s\n" "$((i+1))" "$fname" "$fpath" "$dname"
done

echo ""
read -p "Enter the number of the flow to deploy: " selection

if ! [[ "$selection" =~ ^[1-9][0-9]*$ ]] || (( selection < 1 || selection > ${#flows[@]} )); then
  echo "Invalid selection. Exiting."
  exit 1
fi

IFS='|' read -r FLOW_NAME FLOW_PATH DEPLOYMENT_NAME <<< "${flows[$((selection-1))]}"
POOL_NAME="my-ecs-pool"

# ================ End Flow Selector =============

echo "🚀 Starting Prefect Flow Deployment on AWS ECS Fargate..."

prefect deploy "${FLOW_PATH}:${FLOW_NAME}" \
  --name ${DEPLOYMENT_NAME} \
  --pool "${POOL_NAME}" \
  --prefect-file prefect.yaml

echo "✅ Deployment ${DEPLOYMENT_NAME} for flow ${FLOW_NAME} completed successfully!"
