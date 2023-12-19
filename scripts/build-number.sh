#!/bin/ash

set -e
set -x

apk add --no-progress --quiet git

if [ -z "${DRONE_TAG}" ]; then
  BUILD_COUNT=$(drone build ls --server https://${DRONE_SYSTEM_HOST} --branch ${DRONE_BRANCH} --limit 200 --format "{{ .Number }}" ${DRONE_REPO} | wc -l)
  DRONE_TAG=${DRONE_BRANCH##*/v}rc$((++BUILD_COUNT))
fi

git tag $DRONE_TAG