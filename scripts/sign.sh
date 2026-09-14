#!/usr/bin/env bash
set -euo pipefail
# Never enable shell tracing here.
root=$(cd "$(dirname "$0")/.." && pwd)
input=$(realpath "$1")
output=$(realpath -m "$2")
[[ -n ${GPG_KEY:-} && -n ${GPG_PASSPHRASE:-} ]]
private=$(mktemp -d)
chmod 700 "$private"
export GNUPGHOME="$private/gnupg"
mkdir -m 700 "$GNUPGHOME"
cleanup() {
    gpgconf --kill gpg-agent || true
    rm -rf "$private"
}
trap cleanup EXIT
export SIGN_PASSWORD_FILE="$private/password"
umask 077
printf '%s' "$GPG_PASSPHRASE" > "$SIGN_PASSWORD_FILE"
printf '%s' "$GPG_KEY" | gpg --batch --import
unset GPG_KEY GPG_PASSPHRASE
fingerprint=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["repository_signer"])' "$root/packaging/provenance.json")
gpg --batch --list-secret-keys "$fingerprint" >/dev/null
# Test the password before any output is published.
printf 'Incus RPM signing check\n' > "$private/probe"
gpg --batch --yes --pinentry-mode loopback --passphrase-file "$SIGN_PASSWORD_FILE" \
    --local-user "$fingerprint" --detach-sign "$private/probe"
mkdir -p "$output/x86_64/Packages" "$output/SRPMS/Packages" "$private/rpmdb"
rpm --dbpath "$private/rpmdb" --import "$root/keys/repository.asc"
cat > "$private/gpg-wrapper" <<'EOF'
#!/usr/bin/env bash
exec gpg --batch --pinentry-mode loopback --passphrase-file "$SIGN_PASSWORD_FILE" "$@"
EOF
chmod 700 "$private/gpg-wrapper"
count=0
for package in "$input"/*.rpm; do
    [[ -f "$package" && ! -L "$package" ]]
    arch=$(rpm -qp --qf '%{ARCH}' "$package")
    case "$package" in
        *.src.rpm) target="$output/SRPMS/Packages" ;;
        *) [[ "$arch" == x86_64 || "$arch" == noarch ]]; target="$output/x86_64/Packages" ;;
    esac
    cp "$package" "$target/"
    signed="$target/$(basename "$package")"
    rpmsign --define "_gpg_name $fingerprint" --define "__gpg $private/gpg-wrapper" \
        --define '_gpg_digest_algo sha256' --addsign "$signed"
    rpm --dbpath "$private/rpmdb" --checksig "$signed" | grep -F 'digests signatures OK'
    count=$((count + 1))
done
[[ "$count" -ge 5 ]]
for arch in x86_64 SRPMS; do
    createrepo_c --checksum sha256 "$output/$arch"
    metadata="$output/$arch/repodata/repomd.xml"
    gpg --batch --yes --pinentry-mode loopback --passphrase-file "$SIGN_PASSWORD_FILE" \
        --local-user "$fingerprint" --armor --detach-sign "$metadata"
    # Verify with only the public key, separate from the signing keyring.
    mkdir -p "$private/verify"
    gpg --homedir "$private/verify" --batch --import "$root/keys/repository.asc"
    gpg --homedir "$private/verify" --batch --verify "$metadata.asc" "$metadata"
done
cp "$input/release.json" "$output/release.json"
chmod -R a+rX "$output"
