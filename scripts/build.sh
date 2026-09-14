#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -m) == x86_64 ]] || { echo "This builder requires x86_64 EL10" >&2; exit 1; }
export PATH="/usr/local/go/bin:$PATH"
export GOTOOLCHAIN=local
root=$(cd "$(dirname "$0")/.." && pwd)
top=/build/rpmbuild
bash "$root/scripts/dependencies.sh"
dnf install -y rpm-build rpmdevtools golang gcc gcc-c++ make gnupg2 python3 \
  tar xz diffutils findutils systemd-rpm-macros
# Build and test the missing libraries before resolving Incus build dependencies.
useradd -m builder
bash "$root/scripts/build-dependencies.sh" "$top"
python3 "$root/scripts/prepare.py" "$1" "$top"
dnf builddep -y --define "_topdir $top" "$top/SPECS/incus.spec"
# Compile as a dedicated user without publishing credentials.
chown -R builder:builder /build
runuser -u builder -- env PATH="$PATH" GOTOOLCHAIN=local \
  rpmbuild -ba --define "_topdir $top" --define 'dist .el10' "$top/SPECS/incus.spec"
mkdir -p /output
cp "$top"/RPMS/x86_64/*.rpm "$top"/SRPMS/*.rpm "$top/release.json" /output/
