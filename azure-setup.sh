#!/bin/bash
set -e

RESOURCE_GROUP="VOICE-DEVELOPER_GROUP_99208973"
VM_NAME="voice-developer"

echo "Opening port 8040..."
az vm open-port --port 8040 --resource-group $RESOURCE_GROUP --name $VM_NAME --priority 900

echo "Waiting 10 seconds before opening next port..."
sleep 10

echo "Opening port 5773..."
az vm open-port --port 5773 --resource-group $RESOURCE_GROUP --name $VM_NAME --priority 901

echo "Done. Test with: curl http://20.121.65.202:8040/"
