#!/usr/bin/env bash

set -euo pipefail

mkdir -p $(dirname $2)
cp -fp $1 $2
