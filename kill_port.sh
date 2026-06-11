#!/bin/bash
# Script to kill processes running on a specific port

# Default port is 8000 (matching start_server.py)
PORT=${1:-8000}

# Check if port is a valid number
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: Port must be a number"
    echo "Usage: $0 [PORT]"
    echo "Example: $0 8000"
    exit 1
fi

# Find processes using the port
PIDS=$(lsof -ti:$PORT 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "No process found running on port $PORT"
    exit 0
fi

echo "Found processes on port $PORT:"
lsof -i:$PORT

echo ""
read -p "Kill these processes? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Killing processes on port $PORT..."
    kill -9 $PIDS
    sleep 1
    
    # Verify they're killed
    REMAINING=$(lsof -ti:$PORT 2>/dev/null)
    if [ -z "$REMAINING" ]; then
        echo "Successfully killed all processes on port $PORT"
    else
        echo "Warning: Some processes may still be running on port $PORT"
        echo "Remaining PIDs: $REMAINING"
    fi
else
    echo "Cancelled"
    exit 0
fi

