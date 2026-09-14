# Keep upstream Go checks enabled.
%bcond check 1
# Go -trimpath removes local source paths. Keep debuginfo, omit empty debugsource.
%undefine _debugsource_packages

# Supplied by scripts/prepare.py from the verified upstream release.
%{!?source_version:%global source_version 7.4}
%{!?rpm_version:%global rpm_version 7.4.0}
%{!?rpm_release:%global rpm_release 3}
%{!?has_lxd_migrate:%global has_lxd_migrate 0}
Version:        %{rpm_version}
%global golicenses COPYING
%global gobuilddir %{_builddir}/incus-output

Name:           incus
Release:        %{rpm_release}%{?dist}
Summary:        Powerful system container and virtual machine manager
License:        Apache-2.0
URL:            https://linuxcontainers.org/incus
Source0:        https://linuxcontainers.org/downloads/%{name}/%{name}-%{source_version}.tar.xz

# Systemd units
Source101:      %{name}.socket
Source102:      %{name}.service
Source103:      %{name}-startup.service
Source104:      %{name}-user.socket
Source105:      %{name}-user.service

# Ensure Incus groups exist
Source106:      %{name}-sysusers.conf

# Ensure state directories (/var/lib/incus, /var/cache/incus, /var/log/incus) exist
Source107:      %{name}-tmpfiles.conf

# Ensure system dnsmasq ignores Incus network bridge
Source108:      %{name}-dnsmasq.conf

# Raise number of inotify user instances
Source109:      %{name}-sysctl.conf

# Helper script for incusd shutdown
Source110:      shutdown

%global bashcompletiondir %(pkg-config --variable=completionsdir bash-completion 2>/dev/null || :)

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  golang
BuildRequires:  gettext
BuildRequires:  glibc-static
BuildRequires:  help2man
BuildRequires:  pkgconfig(bash-completion)
BuildRequires:  pkgconfig(cowsql)
BuildRequires:  pkgconfig(libacl)
BuildRequires:  pkgconfig(libcap)
BuildRequires:  pkgconfig(libseccomp)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(lxc)
BuildRequires:  pkgconfig(raft)
BuildRequires:  pkgconfig(sqlite3)
BuildRequires:  systemd-rpm-macros
%{?sysusers_requires_compat}

Requires:       %{name}-client = %{version}-%{release}
Requires:       (container-selinux >= 2.245.0 if selinux-policy)
Requires:       attr
Requires:       dnsmasq
Requires:       iptables, ebtables
Requires:       (nftables if iptables-nft)
Requires:       lxcfs
Requires:       rsync
Requires:       shadow-utils
Requires:       squashfs-tools
Requires:       tar
Requires:       xdelta
Requires:       xz
%{?systemd_requires}

%ifnarch %{ix86} %{arm32}
Requires:       skopeo
# Not yet packaged in Fedora
#Requires:       umoci
%endif

%if %{with check}
BuildRequires:  btrfs-progs
BuildRequires:  dnsmasq
BuildRequires:  nftables
%endif

Recommends:     %{name}-agent = %{version}-%{release}

# This package no longer exists as container-selinux supersedes it
Obsoletes: %{name}-selinux < 6.19.1-4
Conflicts: %{name}-selinux < 6.19.1-4

%description
Container hypervisor based on LXC
Incus offers a REST API to remotely manage containers over the network,
using an image based work-flow and with support for live migration.

This package contains the Incus daemon.

%pre
%sysusers_create_package %{name} %{SOURCE106}
%tmpfiles_create_package %{name} %{SOURCE107}

%post
%systemd_post %{name}.socket
%systemd_post %{name}.service
%systemd_post %{name}-startup.service
%systemd_post %{name}-user.socket
%systemd_post %{name}-user.service

%preun
%systemd_preun %{name}.socket
%systemd_preun %{name}.service
%systemd_preun %{name}-startup.service
%systemd_preun %{name}-user.socket
%systemd_preun %{name}-user.service

%postun
%systemd_postun_with_restart %{name}.socket
%systemd_postun_with_restart %{name}.service
%systemd_postun_with_restart %{name}-user.socket
%systemd_postun_with_restart %{name}-user.service

%files
%license %{golicenses}
%config(noreplace) %{_sysconfdir}/dnsmasq.d/%{name}.conf
%{_sysctldir}/10-incus-inotify.conf
%{_unitdir}/%{name}.socket
%{_unitdir}/%{name}.service
%{_unitdir}/%{name}-startup.service
%{_unitdir}/%{name}-user.socket
%{_unitdir}/%{name}-user.service
%{_libexecdir}/%{name}/
%{_sysusersdir}/%{name}.conf
%{_tmpfilesdir}/%{name}.conf
%{_mandir}/man1/incusd*.1.*
%attr(700,root,root) %dir %{_localstatedir}/cache/%{name}
%attr(700,root,root) %dir %{_localstatedir}/log/%{name}
%attr(711,root,root) %dir %{_localstatedir}/lib/%{name}

%dnl ----------------------------------------------------------------------------

%package client
Summary:        Container hypervisor based on LXC - Client
License:        Apache-2.0

Requires:       gettext

%description client
Incus offers a REST API to remotely manage containers over the network,
using an image based work-flow and with support for live migration.

This package contains the command line client.

%files client -f incus.lang
%license %{golicenses}
%{_bindir}/%{name}
%dir %{bashcompletiondir}
%{bashcompletiondir}/%{name}
%dir %{_datadir}/fish/vendor_completions.d
%{_datadir}/fish/vendor_completions.d/%{name}.fish
%dir %{_datadir}/zsh/site-functions
%{_datadir}/zsh/site-functions/_%{name}
%{_mandir}/man1/%{name}*.1.*
%exclude %{_mandir}/man1/incusd*.1.*
%exclude %{_mandir}/man1/incus-agent.1.*
%exclude %{_mandir}/man1/incus-benchmark.1.*
%exclude %{_mandir}/man1/incus-migrate.1.*
%exclude %{_mandir}/man1/lxc-to-incus.1.*
%if %{has_lxd_migrate}
%exclude %{_mandir}/man1/lxd-to-incus.1.*
%endif

%dnl ----------------------------------------------------------------------------

%package tools
Summary:        Container hypervisor based on LXC - Extra Tools
License:        Apache-2.0

Requires:       incus%{?_isa} = %{version}-%{release}
# fuidshift is also shipped with lxd
Conflicts:      lxd-tools

%description tools
Incus offers a REST API to remotely manage containers over the network,
using an image based work-flow and with support for live migration.

This package contains extra tools provided with Incus.
 - fuidshift - A tool to map/unmap filesystem uids/gids
 - lxc-to-incus - A tool to migrate LXC containers to Incus
%if %{has_lxd_migrate}
 - lxd-to-incus - A tool to migrate an existing LXD environment to Incus
%endif
 - incus-benchmark - A Incus benchmark utility
 - incus-migrate - A physical to container migration tool

%files tools
%license %{golicenses}
%{_bindir}/fuidshift
%{_bindir}/incus-benchmark
%{_bindir}/incus-migrate
%{_bindir}/lxc-to-incus
%if %{has_lxd_migrate}
%{_bindir}/lxd-to-incus
%endif
%{_mandir}/man1/fuidshift.1.*
%{_mandir}/man1/incus-benchmark.1.*
%{_mandir}/man1/incus-migrate.1.*
%{_mandir}/man1/lxc-to-incus.1.*
%if %{has_lxd_migrate}
%{_mandir}/man1/lxd-to-incus.1.*
%endif

%dnl ----------------------------------------------------------------------------

%package agent
Summary:        Incus guest agent
License:        Apache-2.0

# Virtual machine support requires additional packages
%ifarch aarch64
Recommends:     edk2-aarch64
%else
Recommends:     edk2-ovmf
%endif
Recommends:     xorriso
Recommends:     qemu-audio-spice
Recommends:     qemu-char-spice
Recommends:     qemu-device-display-virtio-vga
Recommends:     qemu-device-display-virtio-gpu
Recommends:     qemu-device-usb-redirect
Recommends:     qemu-img
Recommends:     qemu-kvm-core

%description agent
This packages provides an agent to run inside Incus virtual machine guests.

It has to be installed on the Incus host if you want to allow agent
injection capability when creating a virtual machine.

%files agent
%license %{golicenses}
%{_bindir}/incus-agent
%{_mandir}/man1/incus-agent.1.*

%dnl ----------------------------------------------------------------------------

%prep
%setup -q -n incus-%{source_version}

%build
rm -rf %{gobuilddir}
export GOTOOLCHAIN=local
export GOFLAGS=-mod=vendor
export CGO_LDFLAGS_ALLOW="(-Wl,-wrap,pthread_create)|(-Wl,-z,now)"
mkdir -p %{gobuilddir}/{bin,lib,completions}
for cmd in incusd incus-user; do
    go build -trimpath -tags libsqlite3 -o %{gobuilddir}/lib/$cmd ./cmd/$cmd
done
for cmd in incus fuidshift incus-benchmark lxc-to-incus; do
    go build -trimpath -tags libsqlite3 -o %{gobuilddir}/bin/$cmd ./cmd/$cmd
done
%if %{has_lxd_migrate}
go build -trimpath -tags libsqlite3 -o %{gobuilddir}/bin/lxd-to-incus ./cmd/lxd-to-incus
%endif
CGO_ENABLED=0 go build -trimpath -tags netgo -o %{gobuilddir}/bin/incus-migrate ./cmd/incus-migrate
CGO_ENABLED=0 go build -trimpath -tags 'agent netgo' -o %{gobuilddir}/bin/incus-agent ./cmd/incus-agent
%{gobuilddir}/bin/incus completion bash > %{gobuilddir}/completions/incus.bash
%{gobuilddir}/bin/incus completion fish > %{gobuilddir}/completions/incus.fish
%{gobuilddir}/bin/incus completion zsh > %{gobuilddir}/completions/incus.zsh

# build translations
rm -f po/zh_Hans.po po/zh_Hant.po    # remove invalid locales
make %{?_smp_mflags} build-mo

# generate man-pages
mkdir %{gobuilddir}/man
%{gobuilddir}/bin/incus manpage %{gobuilddir}/man/
%{gobuilddir}/lib/incusd manpage %{gobuilddir}/man/
help2man %{gobuilddir}/bin/fuidshift -n "uid/gid shifter" --no-info --no-discard-stderr > %{gobuilddir}/man/fuidshift.1
help2man %{gobuilddir}/bin/incus-benchmark -n "The container lightervisor - benchmark" --no-info --no-discard-stderr > %{gobuilddir}/man/incus-benchmark.1
help2man %{gobuilddir}/bin/incus-migrate -n "Physical to container migration tool" --no-info --no-discard-stderr > %{gobuilddir}/man/incus-migrate.1
help2man %{gobuilddir}/bin/lxc-to-incus -n "Convert LXC containers to Incus" --no-info --no-discard-stderr > %{gobuilddir}/man/lxc-to-incus.1
%if %{has_lxd_migrate}
help2man %{gobuilddir}/bin/lxd-to-incus -n "LXD to Incus migration tool" --no-info --no-discard-stderr > %{gobuilddir}/man/lxd-to-incus.1
%endif
help2man %{gobuilddir}/bin/incus-agent -n "Incus virtual machine guest agent" --no-info --no-discard-stderr > %{gobuilddir}/man/incus-agent.1

%install
# install binaries
install -d %{buildroot}%{_bindir}
install -m0755 -vp %{gobuilddir}/bin/* %{buildroot}%{_bindir}/

# install systemd units
install -d %{buildroot}%{_unitdir}
install -m0644 -vp %{SOURCE101} %{buildroot}%{_unitdir}/
install -m0644 -vp %{SOURCE102} %{buildroot}%{_unitdir}/
%ifarch aarch64
sed -i 's@INCUS_EDK2_PATH=/usr/share/edk2/ovmf@INCUS_EDK2_PATH=/usr/share/AAVMF@' %{buildroot}%{_unitdir}/incus.service
%endif
install -m0644 -vp %{SOURCE103} %{buildroot}%{_unitdir}/
install -m0644 -vp %{SOURCE104} %{buildroot}%{_unitdir}/
install -m0644 -vp %{SOURCE105} %{buildroot}%{_unitdir}/
install -D -m0644 -vp %{SOURCE106} %{buildroot}%{_sysusersdir}/%{name}.conf
install -D -m0644 -vp %{SOURCE107} %{buildroot}%{_tmpfilesdir}/%{name}.conf

# extra configs
install -D -m0644 -vp %{SOURCE108} %{buildroot}%{_sysconfdir}/dnsmasq.d/%{name}.conf
install -D -m0644 -vp %{SOURCE109} %{buildroot}%{_sysctldir}/10-incus-inotify.conf

# install helper libs
install -d %{buildroot}%{_libexecdir}/%{name}
install -m0755 -vp %{SOURCE110} %{buildroot}%{_libexecdir}/%{name}/
install -m0755 -vp %{gobuilddir}/lib/* %{buildroot}%{_libexecdir}/%{name}/

# install manpages
install -d %{buildroot}%{_mandir}/man1
cp -p %{gobuilddir}/man/*.1 %{buildroot}%{_mandir}/man1/

# install shell completions
install -D -m0644 -vp %{gobuilddir}/completions/%{name}.bash %{buildroot}%{bashcompletiondir}/%{name}
install -D -m0644 -vp %{gobuilddir}/completions/%{name}.fish %{buildroot}%{_datadir}/fish/vendor_completions.d/%{name}.fish
install -D -m0644 -vp %{gobuilddir}/completions/%{name}.zsh %{buildroot}%{_datadir}/zsh/site-functions/_%{name}

# cache and log directories
install -d -m0700 %{buildroot}%{_localstatedir}/cache/%{name}
install -d -m0700 %{buildroot}%{_localstatedir}/log/%{name}
install -d -m0711 %{buildroot}%{_localstatedir}/lib/%{name}

# language files
for mofile in po/*.mo ; do
    install -D -m0644 -vp ${mofile} %{buildroot}%{_datadir}/locale/$(basename ${mofile%%.mo})/LC_MESSAGES/%{name}.mo
done
%find_lang incus

%if %{with check}
%check
export GOTOOLCHAIN=local
export GOFLAGS=-mod=vendor
export CGO_LDFLAGS_ALLOW="(-Wl,-wrap,pthread_create)|(-Wl,-z,now)"
# Keep the base package's exclusions: privileged integration tests and
# lxc-to-incus tests (ganto/copr-lxc4#23). All other Go packages are tested.
go list -tags libsqlite3 ./... | grep -Ev '/test(/|$)|/cmd/lxc-to-incus$' > packages.test
# Run packages in sequence to avoid contention in heartbeat timing tests.
xargs -a packages.test go test -p 1 -tags libsqlite3 -timeout 20m
%endif

%changelog
* Thu Apr 09 2026 Carl George <carlwgeorge@fedoraproject.org> - 6.23-3
- Remove incus dependency from incus-agent rhbz#2456888

* Mon Apr 06 2026 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> - 6.23-2
- Fix static builds of vendored dependencies (RHBZ 2419661)

* Mon Apr 06 2026 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> - 6.23-1
- Update to 6.23

* Mon Mar 30 2026 Neal Gompa <ngompa@fedoraproject.org> - 6.19.1-4
- Drop selinux subpackage in favor of container-selinux

* Tue Feb 03 2026 Maxwell G <maxwell@gtmx.me> - 6.19.1-3
- Rebuild for https://fedoraproject.org/wiki/Changes/golang1.26

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 6.19.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Dec 10 2025 Robby Callicotte <rcallicotte@fedoraproject.org> - 6.19.1-1
- Update to 6.19.1

* Sun Dec 07 2025 Neal Gompa <ngompa@fedoraproject.org> - 6.18-3
- Build incus-migrate and incus-migrate with cgo disabled

* Sat Dec 06 2025 Neal Gompa <ngompa@fedoraproject.org> - 6.18-2
- Build incus-agent as a fully statically linked binary (rhbz#2419661)

* Mon Nov 03 2025 Robby Callicotte <rcallicotte@fedoraproject.org> - 6.18-1
- Updated to incus-6.18

* Fri Oct 10 2025 Alejandro Sáez <asm@redhat.com> - 6.15-3
- rebuild

* Fri Aug 15 2025 Maxwell G <maxwell@gtmx.me> - 6.15-2
- Rebuild for golang-1.25.0

* Sun Aug 03 2025 Robby Callicotte <rcallicotte@fedoraproject.org> - 6.15-1
- Updated to incus-6.15

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 6.14-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Mon Jun 30 2025 Robby Callicotte <rcallicotte@fedoraproject.org> - 6.14-1
- Updated to incus-6.14
- Added patch for non-constant format strings

* Fri May 30 2025 Robby Callicotte <rcallicotte@fedoraproject.org> - 6.13-1
- Updated to incus-6.13

* Mon May 05 2025 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> - 6.12-1
- Update to incus-6.12

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 6.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Dec 18 2024 Neal Gompa <ngompa@fedoraproject.org> - 6.8-1
- Update to 6.8
- Another fix for incus socket

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 6.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Tue Jul 02 2024 Neal Gompa <ngompa@fedoraproject.org> - 6.2-2
- Drop devel subpackage

* Thu Jun 06 2024 Neal Gompa <ngompa@fedoraproject.org> - 6.2-1
- Update to 6.2

* Thu May 16 2024 Fabian Mettler <dev@maveonair.com> - 6.1.0-1
- Update to 6.1.0

* Sat Apr 27 2024 Neal Gompa <ngompa@fedoraproject.org> - 6.0.0-1
- Update to 6.0.0
- Move libexec content to libexecdir
- Move sockets to rundir

* Wed Mar 27 2024 Neal Gompa <ngompa@fedoraproject.org> - 0.7-1
- Update to 0.7

* Thu Feb 29 2024 Neal Gompa <ngompa@fedoraproject.org> - 0.6-1
- Update to 0.6

* Fri Jan 26 2024 Neal Gompa <ngompa@fedoraproject.org> - 0.5-1
- Update to 0.5
- Disable building documentation
- Restructure packaging to be easier to conditionalize

* Wed Jan 10 2024 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.4-0.4
- Add incus-selinux sub package

* Thu Dec 28 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.4-0.3
- Fix typo in tmpfiles config

* Wed Dec 27 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.4-0.2
- Use systemd sysusers/tmpfiles
- Update dependencies to use 'Recommends'
- Remove unneeded incus-agent script and systemd unit

* Thu Dec 21 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.4-0.1
- Update to 0.4
- Update swagger-ui to v5.10.5

* Fri Nov 10 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.2-0.2
- Fix envvar for OVMF and documentation

* Mon Oct 30 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.2-0.1
- Update to 0.2
- Update swagger-ui to v5.9.1

* Sun Oct 15 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.1-0.2
- Fix libdir path

* Sun Oct 15 2023 Reto Gantenbein <reto.gantenbein@linuxmonk.ch> 0.1-0.1
- Initial package
