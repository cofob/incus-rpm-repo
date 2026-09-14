#!/usr/bin/env bash
set -euo pipefail
# Runs only in a disposable EL10 container. /repo and /public.asc are test data.
cat > /etc/yum.repos.d/incus-test.repo <<'EOF'
[incus-test]
name=Incus signature test
baseurl=file:///repo/$basearch
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=file:///public.asc
EOF
if [[ "$1" == bad-metadata ]]; then
    if dnf -y --disablerepo='*' --enablerepo=incus-test makecache; then
        echo 'DNF accepted altered metadata' >&2; exit 1
    fi
    exit 0
fi
dnf -y --disablerepo='*' --enablerepo=incus-test makecache
if [[ "$1" == fixture ]]; then
    dnf -y --disablerepo='*' --enablerepo=incus-test install incus-signing-test
else
    bash /work/scripts/dependencies.sh
    # Both libraries must be supplied by this channel, with no COPR enabled.
    if dnf -q repolist --enabled | grep -qi copr; then
        echo 'Unexpected COPR repository' >&2; exit 1
    fi
    for dependency in cowsql raft; do
        candidates=$(dnf -q repoquery --available --repo=incus-test "$dependency")
        [[ -n "$candidates" ]]
    done
    dnf -y install incus incus-agent incus-tools
    incus --version
fi
