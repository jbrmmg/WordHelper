#!/bin/bash
# Build Date:    ${build.timestamp}
# Build Version: ${project.version}
#
# Stop the WordHelper service before deployment.

echo Stop WordHelper version ${project.version} ${build.timestamp}

echo Repository           : $1
echo ComponentName        : $2
echo Deployment Directory : $3

if [ "$1" = "maven-releases" ]; then
    ServiceName="wordhelper"
    ServiceName2="wordclue"
else
    ServiceName="wordhelper-dev"
    ServiceName2="wordclue-dev"
fi
echo Service Name         : ${ServiceName}
echo Service Name 2       : ${ServiceName2}

Running="$(systemctl is-active ${ServiceName} >/dev/null 2>&1 && echo YES || echo NO)"
echo Is ${ServiceName} active? ${Running}
if [ "${Running}" = "YES" ]; then
    echo Stopping ${ServiceName}
    sudo systemctl stop ${ServiceName}
fi

Running="$(systemctl is-active ${ServiceName2} >/dev/null 2>&1 && echo YES || echo NO)"
echo Is ${ServiceName2} active? ${Running}
if [ "${Running}" = "YES" ]; then
    echo Stopping ${ServiceName2}
    sudo systemctl stop ${ServiceName2}
fi
