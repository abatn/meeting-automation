#!/bin/bash
# Skript zur Einrichtung der Entwicklungsumgebung

echo "Setting up backend development environment..."

# Navigate to the backend directory
# This script should be sourced from the project root, so we'll operate relative to it.

# Create a virtual environment if it doesn't exist in backend/.venv
if [ ! -d "backend/.venv" ]; then
    echo "Creating virtual environment in backend/.venv..."
    python3 -m venv backend/.venv
fi

# Activate the virtual environment for dependency installation within this script's context
echo "Activating virtual environment for dependency installation..."
source backend/.venv/bin/activate

# Install dependencies
echo "Installing dependencies from backend/requirements.txt..."
pip install -r backend/requirements.txt

# Create a symbolic link for 'python' in the backend directory to the virtual environment's python
# This ensures 'python' command works directly after 'cd backend'
if [ ! -f "backend/python" ]; then
    echo "Creating symbolic link for 'python' to 'backend/.venv/bin/python'..."
    ln -s ".venv/bin/python" backend/python
fi

echo "Backend setup complete."

# Add the virtual environment's bin directory to the PATH for the current shell
export PATH="$(pwd)/backend/.venv/bin:$PATH"

# Instruct the user to source this script for persistent activation
echo "To ensure the environment is fully set up in your current shell, please run: source scripts/setup-dev.sh"
echo "Then you can run the test command: cd backend && python -c \"from app.core.database import engine; print('Datenbankverbindung OK')\""
