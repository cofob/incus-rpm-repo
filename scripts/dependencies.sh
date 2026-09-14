#!/usr/bin/env bash
set -euo pipefail
dnf install -y dnf-plugins-core epel-release
dnf config-manager --set-enabled crb
# Use this setup in clean builders and installation tests. Never enable COPR.
