#!/bin/bash

# Fix missing dependencies for Gmail Backup Manager
echo "Fixing missing dependencies..."

# Navigate to backend directory
cd backend

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install missing HTTP client dependencies
echo "Installing aiohttp and httpx..."
pip install aiohttp==3.9.1 httpx==0.25.2

# Update requirements.txt if needed
echo "Updating requirements.txt..."
pip freeze | grep -E "(aiohttp|httpx)" >> requirements.txt

# Verify installation
echo "Verifying installation..."
python -c "import aiohttp; import httpx; print('aiohttp and httpx installed successfully')"

# Deactivate virtual environment
deactivate

echo "Dependencies fixed! You can now restart the background sync service."
echo ""
echo "To restart the background sync:"
echo "1. Stop the current service: ./manage_background_sync.sh stop"
echo "2. Start it again: ./manage_background_sync.sh start"
