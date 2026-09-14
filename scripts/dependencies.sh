#!/usr/bin/env bash
set -euo pipefail
dnf install -y dnf-plugins-core epel-release
dnf config-manager --set-enabled crb
dnf copr enable -y neelc/incus "rhel+epel-10-$(rpm --eval '%{_arch}')"
# Scope the exclusion to COPR; keep its cowsql/raft dependencies available.
dnf config-manager --save \
  --setopt='copr:copr.fedorainfracloud.org:neelc:incus.excludepkgs=incus*'
