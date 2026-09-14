#!/usr/bin/env bash
set -euo pipefail
bash /work/scripts/dependencies.sh
arch=$(rpm --eval '%{_arch}')
# Build artifacts are unsigned at this stage; production DNF uses both checks.
packages=(/packages/incus-[0-9]*."$arch".rpm /packages/incus-client-[0-9]*."$arch".rpm \
          /packages/incus-agent-[0-9]*."$arch".rpm /packages/incus-tools-[0-9]*."$arch".rpm)
dnf install -y "${packages[@]}"
incus --version
incus-agent --version
/usr/libexec/incus/incusd --version
test -f /usr/lib/systemd/system/incus.service
test -d /var/lib/incus
