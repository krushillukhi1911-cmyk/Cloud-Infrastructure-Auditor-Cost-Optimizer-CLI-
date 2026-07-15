#!/bin/bash
# Compilation script for Cloud Infrastructure Auditor & Cost Optimizer CLI

set -e

echo "=================================================="
echo "Building cloud-auditor CLI binary with PyInstaller"
echo "=================================================="

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null
then
    echo "PyInstaller not found. Installing from requirements.txt..."
    pip install pyinstaller
fi

# Run PyInstaller build
echo "Running PyInstaller compiler..."
pyinstaller --onefile --name cloud-auditor --clean app/cli/main.py

echo "=================================================="
echo "Build succeeded! Executable artifact location:"
echo "./dist/cloud-auditor"
echo "=================================================="
