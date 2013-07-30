Name:		python-stageportal
Version:	0.0
Release:	1%{?dist}
Summary:	Python library and cli to work with stage portal

Group:		Development/Python
License:	GPLv3+
URL:		https://github.com/RedHatQE/python-stageportal
Source0:	%{name}-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch:  noarch

BuildRequires:	python-devel
Requires:	python-requests python-BeautifulSoup

%description
%summary

%prep
%setup -q

%build

%install
mkdir -p $RPM_BUILD_ROOT%{python_sitelib}/
mkdir -p $RPM_BUILD_ROOT%{_bindir}
cp stageportal.py $RPM_BUILD_ROOT%{python_sitelib}/
cp stageportal $RPM_BUILD_ROOT%{_bindir}
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc COPYING
%{python_sitelib}/*.py*
%{_bindir}/stageportal

%changelog
