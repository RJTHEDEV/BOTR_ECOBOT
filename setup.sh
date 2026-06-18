#!/bin/bash
# setup.sh - Run this on your Linux Cloud Server (Ubuntu/Debian)

echo "Starting deployment setup..."

# 1. Update package lists
sudo apt-get update

# 2. Install system dependencies (FFmpeg for music, python3-pip)
echo "Installing system dependencies (ffmpeg, python3-pip)..."
sudo apt-get install -y ffmpeg python3-pip python3-venv

# 3. (Optional but recommended) Create and activate a virtual environment
# python3 -m venv venv
# source venv/bin/activate

# 4. Install Python requirements
echo "Installing Python requirements..."
pip3 install -r requirements.txt --break-system-packages

echo "Setup complete! You can now run the bot with: python3 bot.py"
