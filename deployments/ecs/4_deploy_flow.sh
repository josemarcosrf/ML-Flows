#!/bin/bash

# Simple ECS Fargate deployment script
# Make sure to configure AWS CLI and have necessary permissions

set -e

# ================ Flow Selector =================
flows=(
  "hello|flows/examples/hello_flow.py"
  "index_document_file|flows/preproc/__init__.py"
  "run_qa_playbook|flows/shrag/__init__.py"
)

printf "\nAvailable Flows to Deploy:\n"
printf "%-3s %-25s %-40s\n" "No." "Flow Name" "Path"
for i in "${!flows[@]}"; do
  IFS='|' read -r fname fpath <<< "${flows[$i]}"
  printf "%-3s %-25s %-40s\n" "$((i+1))" "$fname" "$fpath"
done

echo ""
read -p "Enter the number of the flow to deploy: " selection

if ! [[ "$selection" =~ ^[1-9][0-9]*$ ]] || (( selection < 1 || selection > ${#flows[@]} )); then
  echo "Invalid selection. Exiting."
  exit 1
fi

IFS='|' read -r FLOW_NAME FLOW_PATH <<< "${flows[$((selection-1))]}"
POOL_NAME="my-ecs-pool"

# ================ Deployment Name Selector =============

deployment_options=("deus.dev" "deus.prod" "Other (enter manually)")
printf "\nAvailable Deployment Names:\n"
for i in "${!deployment_options[@]}"; do
  printf "%d) %s\n" "$((i+1))" "${deployment_options[$i]}"
done

echo ""
read -p "Select deployment name (1-${#deployment_options[@]}): " dep_selection

if [[ "$dep_selection" == "1" ]]; then
  DEPLOYMENT_NAME="deus.dev"
elif [[ "$dep_selection" == "2" ]]; then
  DEPLOYMENT_NAME="deus.prod"
elif [[ "$dep_selection" == "3" ]]; then
  read -p "Enter custom deployment name: " DEPLOYMENT_NAME
  if [[ -z "$DEPLOYMENT_NAME" ]]; then
    echo "No deployment name entered. Exiting."
    exit 1
  fi
else
  echo "Invalid selection. Exiting."
  exit 1
fi

# ================ End Selectors =============

# Select the correct YAML file based on flow
USE_PREFECT_YAML=false
PREFECT_YAML=""
if [[ "$FLOW_NAME" == "index_document_file" ]]; then
  PREFECT_YAML="deployments/preproc.yaml"
  USE_PREFECT_YAML=true
elif [[ "$FLOW_NAME" == "run_qa_playbook" ]]; then
  PREFECT_YAML="deployments/shrag.yaml"
  USE_PREFECT_YAML=true
fi

echo "🚀 Starting Prefect Flow Deployment on AWS ECS Fargate..."

if [ "$USE_PREFECT_YAML" = true ]; then
  echo "Using configuration file: $PREFECT_YAML"
  prefect deploy "${FLOW_PATH}:${FLOW_NAME}" \
    --name ${DEPLOYMENT_NAME} \
    --pool "${POOL_NAME}" \
    --prefect-file "$PREFECT_YAML"
else
  prefect deploy "${FLOW_PATH}:${FLOW_NAME}" \
    --name ${DEPLOYMENT_NAME} \
    --pool "${POOL_NAME}"
fi

echo "✅ Deployment ${DEPLOYMENT_NAME} for flow ${FLOW_NAME} completed successfully!"
