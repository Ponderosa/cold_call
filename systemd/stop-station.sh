#!/usr/bin/env bash
# Stop the Cold Calls service (for maintenance or testing)
sudo systemctl stop cold-call
echo "Cold Calls stopped. Run start-station.sh to resume."
