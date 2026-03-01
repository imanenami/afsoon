#!/bin/bash

# Utility for instantiating a LXD instance for snap/rock tests.
#
# Usage: ./init-sandbox.sh [INSTANCE-NAME]


SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
pushd $SCRIPT_DIR

lxc launch ubuntu:24.04 $1

lxc config set $1 \
    security.nesting=true \
    security.syscalls.intercept.mknod=true \
    security.syscalls.intercept.setxattr=true

sleep 5

lxc file push docker-script.sh $1/root/
lxc exec $1 -- /root/docker-script.sh &> /dev/null &
PID=$!

while [ -d /proc/$PID ]; do
    for s in / - \\ \|; do
        printf "\r$s"
        sleep .1
    done
done

popd
