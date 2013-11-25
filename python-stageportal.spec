Name:		python-stageportal
Version:	0.1
Release:	1%{?dist}
Summary:	Python library and cli to work with stage portal

Group:		Development/Python
License:	GPLv3+
URL:		https://github.com/RedHatQE/python-stageportal
Source0:	%{name}-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch:  noarch

BuildRequires:	python-devel
Requires:	python-requests python-rhsm

%description
%summary

%prep
%setup -q

%build

%install
mkdir -p $RPM_BUILD_ROOT%{python_sitelib}/
mkdir -p $RPM_BUILD_ROOT%{_bindir}
cp -r stageportal $RPM_BUILD_ROOT%{python_sitelib}/
cp bin/stageportal $RPM_BUILD_ROOT%{_bindir}
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc COPYING
%{python_sitelib}/stageportal/*.py*
%{_bindir}/stageportal

%changelog
* Tue Jul 30 2013 Vitaly Kuznetsov <vitty@redhat.com> 0.1-1
- new package built with tito


