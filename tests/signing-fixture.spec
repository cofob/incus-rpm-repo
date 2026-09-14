Name: incus-signing-test
Version: 1
Release: 1
Summary: Test fixture for the RPM signing pipeline
License: MIT
BuildArch: noarch
%description
Test fixture. Never published.
%package client
Summary: Test client
%description client
Test fixture.
%package agent
Summary: Test agent
%description agent
Test fixture.
%package tools
Summary: Test tools
%description tools
Test fixture.
%install
mkdir -p %{buildroot}/usr/share/incus-signing-test
for name in main client agent tools; do
  echo test > %{buildroot}/usr/share/incus-signing-test/$name
done
%files
/usr/share/incus-signing-test/main
%files client
/usr/share/incus-signing-test/client
%files agent
/usr/share/incus-signing-test/agent
%files tools
/usr/share/incus-signing-test/tools
