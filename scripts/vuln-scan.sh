#!/bin/bash

# Utility for building rocks from source and running Trivy scans against them.
# This utility uses a LXD instance as sandbox environment.
#
# Usage: ./vuln-scan.sh [LXD-INSTANCE-NAME] [ROCK-REPOSITORY-NAME] [BRANCH]


DOCKER_ENABLED_CONTAINER=$1
REPO=$2
BRANCH=$3

CWD=$(pwd)
STAGE_PATH="$CWD/stage-rock-repo"

git clone https://github.com/canonical/$REPO --branch $BRANCH $STAGE_PATH
OUTFILE="$REPO--$BRANCH-results.json"
echo $OUTFILE

pushd $STAGE_PATH

rockcraft pack -v

ROCK_FILE=$(ls -1 $STAGE_PATH/*.rock | tail -n 1)

OCI_FILENAME="$REPO-$BRANCH.tar"

rockcraft.skopeo --insecure-policy copy \
    --dest-tls-verify=false oci-archive:$ROCK_FILE docker-archive:./$OCI_FILENAME

lxc file push ./$OCI_FILENAME $DOCKER_ENABLED_CONTAINER/root/

lxc exec $DOCKER_ENABLED_CONTAINER -- trivy image \
    --severity MEDIUM,HIGH,CRITICAL --format json \
    -o /root/results.json --input /root/$OCI_FILENAME

lxc file pull $DOCKER_ENABLED_CONTAINER/root/results.json $CWD/$OUTFILE

lxc exec $DOCKER_ENABLED_CONTAINER -- rm /root/$OCI_FILENAME /root/results.json

popd
rm -rf $STAGE_PATH
