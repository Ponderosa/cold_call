#!/usr/bin/env bash
# Start (or restart) the Cold Calls service
sudo systemctl restart cold-call
echo "Cold Calls started. Logs: sudo journalctl -u cold-call -f"
