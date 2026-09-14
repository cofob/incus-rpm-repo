#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
top=$1
python3 "$root/scripts/prepare_dependencies.py" "$top"
for name in raft cowsql; do
    dnf builddep -y --define "_topdir $top" "$top/SPECS/$name.spec"
    chown -R builder:builder "$top"
    runuser -u builder -- rpmbuild -ba --define "_topdir $top" \
        --define 'dist .el10' "$top/SPECS/$name.spec"
    arch=$(rpm --eval '%{_arch}')
    dnf install -y "$top/RPMS/$arch/$name"-[0-9]*.rpm \
        "$top/RPMS/$arch/$name-devel"-[0-9]*.rpm
done
