# Incus RPM repository for EL10

Signed Incus RPMs for **EL10 x86_64 and aarch64 (ARM64)**, served at
[incusrpmrepo.cofob.dev](https://incusrpmrepo.cofob.dev).

- **latest** follows the newest stable release.
- **lts** follows the newest LTS series and its updates.

Both channels can advance to a new major version. Enable only one.

## Install

On Rocky Linux 10, enable EPEL and CRB:

```sh
sudo dnf install -y dnf-plugins-core epel-release
sudo dnf config-manager --set-enabled crb
```

DNF selects the system architecture automatically. This repository supplies
`cowsql` and `raft` for both architectures. COPR is not required.
For an existing installation, follow the [COPR migration guide](docs/migrate-from-copr.md).

Download the signing key and check its fingerprint:

```sh
curl -fsSLo /tmp/RPM-GPG-KEY-incus https://incusrpmrepo.cofob.dev/RPM-GPG-KEY-incus
gpg --show-keys --with-fingerprint /tmp/RPM-GPG-KEY-incus
```

Expected fingerprint: `06FB41B7A8B4AAD8E9820FAC3BA91725C212825F`.
The key file also has a [detached signature](keys/repository.sig.asc) from
[Egor Ternovoi's main key](https://cofob.dev/pgp).

Import it and install the LTS channel; replace `lts` with `latest` if wanted:

```sh
sudo rpm --import /tmp/RPM-GPG-KEY-incus
curl -fsSLo /tmp/incus-lts.repo https://incusrpmrepo.cofob.dev/incus-lts.repo
sudo install -m 0644 /tmp/incus-lts.repo /etc/yum.repos.d/incus-lts.repo
sudo dnf install incus incus-agent incus-tools
sudo systemctl enable --now incus.socket
sudo incus admin init
```

Package and metadata signature checks are enabled. Source RPMs are available
through the disabled `incus-lts-source` or `incus-latest-source` repository.

Update with `sudo dnf upgrade --refresh`. Before major upgrades, back up Incus
and read the [release notes](https://github.com/lxc/incus/releases). Disable the
old channel before switching; do not downgrade an existing Incus database.

## Automation

Actions checks daily at **03:17 UTC**, builds new stable releases, signs RPMs
and metadata, then publishes complete S3 snapshots for both architectures. Failed releases are retried;
old snapshots remain available. Packaging changes can require maintenance.

Set these repository secrets:

| Secret | Value |
| --- | --- |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 credentials |
| `AWS_REGION` | S3 region |
| `S3_BUCKET_NAME` | Bucket name |
| `S3_ENDPOINT_URL` | HTTPS S3 API endpoint |
| `GPG_KEY` | Armored private key matching the public key |
| `GPG_PASSPHRASE` | Private-key password |

Allow bucket `ListBucket` and object `GetObject`/`PutObject` for `snapshots/*`,
`channels/*`, `state/*`, `incus-*.repo`, and `RPM-GPG-KEY-incus`. Serve the bucket
at `incusrpmrepo.cofob.dev`; preserve cache headers and return 404 for missing
objects. S3 uses path-style addressing.

Push to the default branch to enable scheduled runs. For manual runs, select
**Actions → Publish Incus RPMs → Run workflow**. Choose a channel and optionally
`build_only` to test without publication.

## Development

Packaging derives from the neelc/incus EL10 SRPM recorded in
[packaging/provenance.json](packaging/provenance.json). CI builds both initial
releases, builds and tests the pinned [dependency sources](packaging/dependencies/provenance.json),
and checks native installation without COPR, signing, and tamper rejection on
both architectures. A failed architecture build stops publication for its channel.
Bump `rpm_release` in `packaging/provenance.json` when packaging or dependencies
change; this rebuilds both channels even if upstream versions are unchanged.

```sh
python3 -m unittest discover -s tests -v
nix-shell -p zizmor --run 'zizmor .github/workflows'
nix-shell -p actionlint shellcheck --run 'actionlint && shellcheck scripts/*.sh'
```
