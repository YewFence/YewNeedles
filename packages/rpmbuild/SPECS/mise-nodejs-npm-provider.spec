Name:           mise-nodejs-npm-provider
Version:        1.0
Release:        1%{?dist}
Summary:        Virtual nodejs-npm provider backed by mise
License:        MIT
BuildArch:      noarch

Provides:       nodejs-npm

%description
Virtual RPM package that satisfies packages requiring nodejs-npm.
The actual node and npm commands are expected to be provided by mise shims.

%prep

%build

%install

%files

%changelog
* Thu Jul 02 2026 YewFence <yewfence@localhost> - 1.0-1
- Initial virtual provider package
