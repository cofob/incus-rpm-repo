#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
artifacts=${1:-$root/dist}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/repo/scripts" "$work/repo/keys" "$work/repo/packaging" "$work/keyring"
chmod 700 "$work/keyring"
cp "$root/scripts/sign.sh" "$work/repo/scripts/"
printf 'test-key-password\n' > "$work/password"
gpg --homedir "$work/keyring" --batch --pinentry-mode loopback --passphrase-file "$work/password" \
    --quick-generate-key 'RPM CI Test <ci@example.invalid>' ed25519 sign 1d
fingerprint=$(gpg --homedir "$work/keyring" --with-colons --list-keys | awk -F: '$1 == "fpr" { print $10; exit }')
gpg --homedir "$work/keyring" --armor --export "$fingerprint" > "$work/repo/keys/repository.asc"
printf '{"repository_signer":"%s"}\n' "$fingerprint" > "$work/repo/packaging/provenance.json"
GPG_KEY=$(gpg --homedir "$work/keyring" --batch --pinentry-mode loopback --passphrase-file "$work/password" \
    --armor --export-secret-keys "$fingerprint")
export GPG_KEY
export GPG_PASSPHRASE=test-key-password
bash "$work/repo/scripts/sign.sh" "$artifacts" "$work/signed"
# CI runs DNF in a fresh native x86_64 EL10 container with only public data.
if [[ ${TEST_DNF_DOCKER:-false} == true ]]; then
    docker run --rm --platform linux/amd64 \
        -v "$root:/work:ro" -v "$work/signed:/repo:ro" \
        -v "$work/repo/keys/repository.asc:/public.asc:ro" \
        quay.io/rockylinux/rockylinux:10@sha256:827d37bc128288ccf160ee318bb3cb92d591164cb217e92f8bc61e3982ae1834 \
        bash /work/scripts/test-dnf.sh install
fi
# Native EL10 fixture runs do not require a nested Docker engine.
if [[ ${TEST_DNF_NATIVE:-false} == true ]]; then
    ln -s "$work/signed" /repo
    ln -s "$work/repo/keys/repository.asc" /public.asc
    bash "$root/scripts/test-dnf.sh" fixture
fi
if GPG_PASSPHRASE=wrong bash "$work/repo/scripts/sign.sh" "$artifacts" "$work/wrong"; then
    echo 'Incorrect password was accepted' >&2; exit 1
fi
if GPG_PASSPHRASE='' bash "$work/repo/scripts/sign.sh" "$artifacts" "$work/missing"; then
    echo 'Missing password was accepted' >&2; exit 1
fi
mkdir "$work/rpmdb"
rpm --dbpath "$work/rpmdb" --import "$work/repo/keys/repository.asc"
package=$(find "$work/signed/x86_64/Packages" -name '*.rpm' -print -quit)
cp "$package" "$work/tampered.rpm"
printf 'tampered' >> "$work/tampered.rpm"
if rpm --dbpath "$work/rpmdb" --checksig "$work/tampered.rpm"; then
    echo 'Altered RPM was accepted' >&2; exit 1
fi
metadata="$work/signed/x86_64/repodata/repomd.xml"
printf 'tampered' >> "$metadata"
if gpg --homedir "$work/keyring" --verify "$metadata.asc" "$metadata"; then
    echo 'Altered metadata was accepted' >&2; exit 1
fi
if [[ ${TEST_DNF_DOCKER:-false} == true ]]; then
    docker run --rm --platform linux/amd64 \
        -v "$root:/work:ro" -v "$work/signed:/repo:ro" \
        -v "$work/repo/keys/repository.asc:/public.asc:ro" \
        quay.io/rockylinux/rockylinux:10@sha256:827d37bc128288ccf160ee318bb3cb92d591164cb217e92f8bc61e3982ae1834 \
        bash /work/scripts/test-dnf.sh bad-metadata
fi
if [[ ${TEST_DNF_NATIVE:-false} == true ]]; then
    dnf clean all
    bash "$root/scripts/test-dnf.sh" bad-metadata
    rm /repo /public.asc /etc/yum.repos.d/incus-test.repo
fi
printf 'Protected-key signing and tamper tests passed\n'
