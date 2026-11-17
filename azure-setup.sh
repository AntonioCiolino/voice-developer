#!/bin/bash
set -e

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-VOICE-DEVELOPER_GROUP_99208973}"
VM_NAME="${AZURE_VM_NAME:-voice-developer}"

if [ "$#" -gt 2 ]; then
  echo "Usage: $0 [resource-group] [vm-name]" >&2
  exit 2
fi

RESOURCE_GROUP="${1:-$RESOURCE_GROUP}"
VM_NAME="${2:-$VM_NAME}"

echo "Opening port 8040 on $VM_NAME in $RESOURCE_GROUP..."
az vm open-port --port 8040 --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --priority 900

echo "Waiting 10 seconds before opening next port..."
sleep 10

echo "Opening port 5773 on $VM_NAME in $RESOURCE_GROUP..."
az vm open-port --port 5773 --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --priority 901

echo "Done. Ports 8040 and 5773 were requested for $VM_NAME in $RESOURCE_GROUP. This script does not install or start Voice Developer."
