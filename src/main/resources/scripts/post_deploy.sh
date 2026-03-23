#!/bin/bash
# Build Date:    ${build.timestamp}
# Build Version: ${project.version}
#
# Install service file, set up Python virtualenv, and start the WordHelper service.

echo Start WordHelper version ${project.version} ${build.timestamp}

echo Repository           : $1
echo ComponentName        : $2
echo Deployment Directory : $3

if [ "$1" = "maven-releases" ]; then
    ServiceName="wordhelper"
    DeployDir="/usr/bin/jbr/wordhelper"
else
    ServiceName="wordhelper-dev"
    DeployDir="/usr/bin/jbr/dev/wordhelper"
fi
echo Service Name         : ${ServiceName}
echo Deploy Directory     : ${DeployDir}

# Install systemd service file
echo Installing service file
sudo mv ./artifactExtract/${ServiceName}.service /lib/systemd/system/${ServiceName}.service

# Verify prerequisites (python3-venv and deploy directory must be set up on the server in advance)
if ! python3 -c "import ensurepip" > /dev/null 2>&1; then
    echo "ERROR: python3-venv is not installed. Run: sudo apt-get install python3-venv"
    exit 1
fi
if [ ! -d "${DeployDir}" ]; then
    echo "ERROR: Deploy directory ${DeployDir} does not exist."
    echo "Run once on the server: sudo mkdir -p ${DeployDir} && sudo chown \$(whoami) ${DeployDir}"
    exit 1
fi

# Copy application files
echo Copying application files
cp -r ./artifactExtract/deploy/* ${DeployDir}/

# Set up Python virtual environment
echo Setting up Python virtual environment
python3 -m venv ${DeployDir}/venv
${DeployDir}/venv/bin/pip install --quiet --upgrade pip
${DeployDir}/venv/bin/pip install --quiet -r ${DeployDir}/requirements.txt

# Enable and start service
echo Enabling and starting ${ServiceName}
sudo systemctl daemon-reload
sudo systemctl enable ${ServiceName}
sudo systemctl start ${ServiceName}
