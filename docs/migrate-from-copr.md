# Migrate from the Incus COPR repository

For an existing **EL10 x86_64** installation from `neelc/incus`.
Package names, systemd units, and `/var/lib/incus` are retained.
Do not remove Incus, delete its state, or run `incus admin init` again.

## 1. Check versions and make a backup

Schedule a maintenance window. Record the installed versions and enabled repos:

```sh
rpm -q incus incus-client incus-agent incus-tools cowsql raft
sudo dnf repolist --enabled
sudo incus list --all-projects
```

Choose `lts` or `latest`. The selected version must be at least the installed
version. For example, do not move from 7.4 to 7.0 LTS. Both channels can advance
to a new major series. Read the relevant
[upstream release notes](https://github.com/lxc/incus/releases) first.

Make and verify a full backup using the
[upstream backup guide](https://linuxcontainers.org/incus/docs/main/backup/).
Include `/var/lib/incus`, external storage pools, custom volumes, and
`/etc/subuid` and `/etc/subgid`. Stop workloads and Incus when taking a cold
backup. A database copy or an instance snapshot alone is not a full backup.
Keep the backup outside the affected storage and save the old RPMs and repo files.

For a cluster, plan the upgrade for every member using the
[upstream cluster upgrade procedure](https://linuxcontainers.org/incus/docs/main/howto/cluster_manage/#upgrade-cluster-members).
Check that all members are online before starting. Use the same channel and
version on all members.

## 2. Change repositories

Keep EPEL and CRB enabled. Disable COPR using its ID from `dnf repolist`:

```sh
sudo dnf config-manager --set-disabled 'copr:copr.fedorainfracloud.org:neelc:incus'
```

If you used another COPR repo file, use its actual ID instead. Disable any other
Incus channel. Remove any global `exclude=incus*` setting or Incus version lock
that would block the upgrade. The old exclusion inside the disabled COPR repo
can remain.

The commands below select LTS. Change `channel=lts` to `channel=latest` if needed:

```sh
channel=lts
curl -fsSLo /tmp/RPM-GPG-KEY-incus https://incusrpmrepo.cofob.dev/RPM-GPG-KEY-incus
gpg --show-keys --with-fingerprint /tmp/RPM-GPG-KEY-incus
```

Check the fingerprint before continuing:
`06FB41B7A8B4AAD8E9820FAC3BA91725C212825F`.

```sh
sudo rpm --import /tmp/RPM-GPG-KEY-incus
curl -fsSLo "/tmp/incus-$channel.repo" "https://incusrpmrepo.cofob.dev/incus-$channel.repo"
sudo install -m 0644 "/tmp/incus-$channel.repo" "/etc/yum.repos.d/incus-$channel.repo"
sudo dnf clean metadata
sudo dnf --refresh list --showduplicates incus cowsql raft
sudo dnf --refresh --assumeno upgrade 'incus*' cowsql raft
```

Check that Incus, cowsql, and raft come from `incus-lts` or `incus-latest`.
Stop if the transaction requires removals or a downgrade. Do not add
`--allowerasing`, `--nogpgcheck`, or use `distro-sync` to force it.

## 3. Upgrade and check

```sh
sudo dnf --refresh upgrade 'incus*' cowsql raft
sudo systemctl restart incus.service
sudo incus info
sudo incus list --all-projects
sudo dnf list --installed 'incus*' cowsql raft
sudo journalctl -u incus.service -n 50 --no-pager
```

Check storage, networks, and application health. Restart workloads stopped for
the backup. DNF uses this repository for the libraries as well as Incus.

## Recovery

If DNF stops before installation, correct the reported error and repeat the preview.
If the new daemon has started, it might have upgraded the database. Do not use
`dnf history undo` to downgrade it. Restore the matching pre-upgrade server state,
storage, and packages during a maintenance window. See upstream's
[database upgrade guidance](https://linuxcontainers.org/incus/docs/main/installing/#upgrade-incus).
