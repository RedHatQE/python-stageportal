#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import logging
import time
import hashlib
import xml.etree.ElementTree as ET
import csv
from BeautifulSoup import BeautifulSoup

try:
    from rhn import rpclib
except ImportError:
    # try to avoid dependency
    pass

from baseportal import *


class RhnClassicPortalException(BasePortalException):
    pass


class RhnClassicPortal(BasePortal):
    xmlrpc_url = "http://xmlrpc.example.com/XMLRPC"

    def __init__(self, xmlrpc_url=None, login='admin', password='admin', maxtries=40, insecure=None, webui_url=None, api_url=None, portal_url=None):
        BasePortal.__init__(self, login, password, maxtries, insecure, api_url, portal_url)
        self.xmlrpc_url = xmlrpc_url
        self.rpc = rpclib.Server(xmlrpc_url)
        self.rpc_api = rpclib.Server(xmlrpc_url.replace('/XMLRPC', '/rpc/api'))
        self.systems = {}
        self.webui_url = webui_url
        if webui_url is None:
            self.webui_url = xmlrpc_url
            self.webui_url = self.webui_url.replace('/XMLRPC', '')
            self.webui_url = self.webui_url.replace('http://xmlrpc.', 'http://')
            self.webui_url = self.webui_url.replace('https://xmlrpc.', 'https://')

    def _gen_uuid(self, name, dashed=True):
        md5 = hashlib.md5(self.login + name).hexdigest()
        if dashed:
            return md5[0:8] + '-' + md5[8:12] + '-' + md5[12:16] + '-' + md5[16:20] + '-' + md5[20:]
        else:
            return md5

    @staticmethod
    def _parse_system_details(details):
        root = ET.fromstring(details)
        params = {}
        for sub1 in root.findall('param'):
            for sub2 in sub1.findall('value'):
                for sub3 in sub2.findall('struct'):
                    for sub4 in sub3.findall('member'):
                        name = None
                        strval = None
                        for item in sub4.getchildren():
                            if item.tag == 'name':
                                name = item.text
                            if item.tag == 'value':
                                for subitem in item.getchildren():
                                    if subitem.tag == 'string':
                                        strval = subitem.text
                        if name is not None and strval is not None:
                            params[name] = strval
        return params

    def _get_num_id(self, system):
        return int(self.systems[system]['info']['system_id'].replace('ID-', ''))

    def _get_login_token(self):
        return self._retr(self.rpc_api._request, lambda res: res is not None, 1, True, None, 'auth.login', (self.login, self.password))

    def _register_system(self, sys_name=None, cores=1, memory=2, arch='x86_64', release_name='redhat-release-server', dist_version='6Server', is_guest=False, org_id=None, basechannel=None):
        system = {'username': self.login,
                  'password': self.password,
                  'release_name': release_name,
                  'profile_name': sys_name,
                  'architecture': arch,
                  'os_release': dist_version,
                  'smbios': {u'smbios.system.version': u'',
                             u'smbios.system.uuid': self._gen_uuid(sys_name)}}
        if is_guest:
            system['smbios'][u'smbios.system.product'] = u'KVM'
            system['smbios'][u'smbios.system.family'] = u'Red Hat Enterprise Linux'
            system['smbios'][u'smbios.bios.vendor'] = u'Seabios'
            system['smbios'][u'smbios.system.manufacturer'] = u'Red Hat'
            system['smbios'][u'smbios.system.skunumber'] = u'Not Specified'

        if org_id is not None and org_id != '':
            system['org_id'] = org_id

        if basechannel is not None and basechannel != '':
            system['channel'] = basechannel

        self.logger.debug('Registering system %s' % system)
        details = self._retr(self.rpc._request, lambda res: res is not None, 1, True, None, 'registration.new_system', (system,))
        self.logger.debug('Got %s' % details)

        self.systems[sys_name] = {'details': details, 'info': self._parse_system_details(details)}

        hardware = [{u'bogomips': u'1234.56',
                     u'cache': u'8192 KB',
                     u'class': u'CPU',
                     u'desc': u'Processor',
                     u'model': u'Intel(R) Xeon(R) CPU           W3550  @ 3.07GHz',
                     u'model_number': u'6',
                     u'model_rev': u'5',
                     u'model_ver': u'26',
                     u'other': u'fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe syscall nx rdtscp lm constant_tsc arch_perfmon pebs bts rep_good xtopology nonstop_tsc aperfmperf pni dtes64 monitor ds_cpl vmx est tm2 ssse3 cx16 xtpr pdcm dca sse4_1 sse4_2 popcnt lahf_lm ida dts tpr_shadow vnmi flexpriority ept vpid',
                     u'platform': u'x86_64',
                     u'speed': 1595,
                     u'type': u'GenuineIntel'},
                    {u'class': u'NETINFO',
                     u'hostname': sys_name,
                     u'ipaddr': u'1.2.3.4'}]
        if memory is not None:
            hardware.append({u'class': u'MEMORY', u'ram': str(memory * 1024), u'swap': str(memory * 2048)})
            self.systems[sys_name]['memory'] = str(memory * 1024)
        if cores is not None:
            hardware[0]['count'] = cores
            self.systems[sys_name]['cores'] = cores

        details = self._retr(self.rpc._request, lambda res: res is not None, 1, True, None, 'registration.add_hw_profile', (details, hardware))
        return details

    def _set_virt_host(self, host, guest_ids):
        if not host in self.systems:
            raise RhnClassicPortalException("Host system %s is not in systems list" % host)
        system = self.systems[host]['details']
        ut = int(time.time())
        info = [(ut, 'exists', 'system', {'identity': 'host', 'uuid': '0000000000000000'})]
        info.append((ut, 'crawl_began', 'system', {}))
        for guest in guest_ids:
            if not guest in self.systems:
                raise RhnClassicPortalException("Guest system %s is not in systems list" % guest)

            guest_info = self.systems[guest]
            info.append((ut, 'exists', 'domain', {'memory_size': guest_info['memory'],
                                                  'name': guest,
                                                  'state': 'running',
                                                  'uuid': self._gen_uuid(guest, False),
                                                  'vcpus': guest_info['cores'],
                                                  'virt_type': 'fully_virtualized'}))
        info.append((ut, 'crawl_ended', 'system', {}))
        self.logger.debug("Setting hostguest info for %s: %s" % (host, info))
        details = self._retr(self.rpc._request, lambda res: res is not None, 1, True, None, 'registration.virt_notify', (system, info))
        self.logger.debug("Result: %s" % details)
        return details

    def _systems_api_call(self, api, system):
        if not system in self.systems:
            raise RhnClassicPortalException("System %s is not in systems list" % system)
        session_id = self._get_login_token()
        result = self._retr(self.rpc_api._request, lambda res: res is not None, 1, True, None, 'system.%s' % api, (session_id, self._get_num_id(system)))
        return result

    def _list_child_channels(self, system):
        return self._systems_api_call('listChildChannels', system)

    def _get_entitlements(self, system):
        return self._systems_api_call('getEntitlements', system)

    def _add_child_channels(self, system, channels):
        if not system in self.systems:
            raise RhnClassicPortalException("System %s is not in systems list" % system)
        req = self._retr(self.rpc._request, lambda res: res is not None, 1, True, None, 'up2date.subscribeChannels', (self.systems[system]['details'], channels, self.login, self.password))
        return req

    def _list_channels(self, system):
        if not system in self.systems:
            raise RhnClassicPortalException("System %s is not in systems list" % system)
        req = self._retr(self.rpc._request, lambda res: res is not None, 1, True, None, 'up2date.listChannels', (self.systems[system]['details'], ))
        return req

    def _webui_login(self):
        s = requests.session()
        s.verify = False
        req = self._retr(s.get, lambda res: res.status_code == 200, 1, True, None, "%s/rhn/" % self.webui_url)
        bs = BeautifulSoup(req.text)
        tokens = bs.findAll('input', {'name': 'csrf_token'})
        if not tokens or tokens == []:
            raise RhnClassicPortalException('Failed to find CSRF on login page: %s/rhn/' % self.webui_url)
        csrf = tokens[0].get('value')
        req = self._retr(s.post, lambda res: res.status_code == 200, 1, True, None, "%s/rhn/ReLoginSubmit.do" % self.webui_url,
                         data={'csrf_token': csrf,
                               'username': self.login,
                               'password': self.password,
                               'login_cb': 'login',
                               'url_bounce': '/rhn/',
                               'request_method': 'GET'})
        return s

    def get_entitlements_list(self, hosted=False):
        result = {}
        if not hosted:
            s = self._webui_login()
        else:
            s = self.portal_login()
        req = self._retr(s.get, lambda res: res.status_code == 200, 1, True, None, "%s/rhn/channels/software/Entitlements.do" % self.webui_url)
        n = 0
        while True:
            self.logger.debug("Parsing page No %s with entitlements" % n)
            n += 1
            data = {}
            bs = BeautifulSoup(req.text)
            headers = []
            if bs.findAll('table', {'class': 'list'}) == []:
                # no channel entitlements
                break
            for header in bs.findAll('table', {'class': 'list'})[0].findAll('tr')[0].findAll('th'):
                # figuring out header names for columns
                headers.append(header.text)
            for row in bs.findAll('table', {'class': 'list'})[0].findAll('tr')[1:]:
                # parsing channel lines
                td_num = 0
                result_line = {}
                for td in row.findAll('td'):
                    result_line[headers[td_num]] = td.text
                    td_num += 1
                channel_key = None
                if 'Channel Entitlement' in result_line:
                    channel_key = 'Channel Entitlement'
                elif 'Channel Name' in result_line:
                    channel_key = 'Channel Name'
                else:
                    self.logger.error('Error in parsing line: %s' % result_line)

                if channel_key:
                    result[result_line[channel_key]] = {}
                    for key in result_line:
                        if key != channel_key:
                            try:
                                result[result_line[channel_key]][key] = int(result_line[key])
                            except ValueError:
                                self.logger.error('Error in parsing values in line: %s' % result_line)
                                result[result_line[channel_key]][key] = 0

            submit_form = bs.findAll('form', {'action': '/rhn/channels/software/EntitlementsSubmit.do'})[0]
            for iv in submit_form.findAll('input', {'type':'hidden'}):
                # csrf and submit
                data[iv.get('name')] = iv.get('value')
            have_next = False
            if not hosted:
                # Satellite
                for iv in bs.findAll('form', {'action': '/rhn/channels/software/Entitlements.do'})[0].findAll('input', {'type':'hidden'}):
                    # other params
                    data[iv.get('name')] = iv.get('value')
                for key in data:
                    if key[-10:] == '_page_next':
                        data[key + '.x'] = 1
                        data[key + '.y'] = 1
                        have_next = True
                        break
            else:
                # RHN Hosted
                if submit_form.findAll('input', {'name': 'Next'})[0].get('class') == 'list-nextprev-active':
                    have_next = True
                    data['Next.x'] = 1
                    data['Next.y'] = 1
                    data['Next'] = '>'
            if not have_next:
                break
            req = self._retr(s.post, lambda res: res.status_code == 200, 1, True, None, "%s/rhn/channels/software/Entitlements.do" % self.webui_url, data=data)
        return result

    def create_systems(self, csv_file, org=None):
        """
        Register a bunch of systems from CSV file

        # CSV: Name,Count,Org Label,Virtual,Host,Release,Version,Arch,RAM,Cores,Base Channel,Child Channels
        """
        host_systems = {}

        data = csv.DictReader(open(csv_file))
        for row in data:
            if row['Name'].startswith('#'):
                self.logger.debug("Skipping %s" % row['Name'])
                continue
            num = 0
            total = int(row['Count'])
            try:
                cores = int(row['Cores'])
            except ValueError:
                cores = None
            try:
                memory = int(row['RAM'])
            except ValueError:
                memory = None
            arch = row['Arch']
            release = row['Release']
            version = row['Version']
            org = row['Org Label']
            basechannel = row['Base Channel']

            channels = []
            if row['Child Channels']:
                channels = row['Child Channels'].split(';')

            while num < total:
                num += 1
                name = self._namify(row['Name'], num)

                if row['Virtual'] in ['Yes', 'Y', 'y']:
                    is_guest = True
                else:
                    is_guest = False

                if self._register_system(name, cores, memory, arch, release, version, is_guest, org, basechannel) is None:
                    raise RhnClassicPortalException("Failed to register system %s" % name)

                if channels != []:
                    if self._add_child_channels(name, channels) is None:
                        raise RhnClassicPortalException("Failed to subscribe %s to %s" % (name, channels))

                if row['Host'] is not None and row['Host'] != '':
                    host_name = self._namify(row['Host'], num)
                    if not host_name in host_systems:
                        host_systems[host_name] = [name]
                    else:
                        host_systems[host_name].append(name)

        self.logger.debug("Host/guest allocation: %s" % host_systems)

        for host in host_systems:
            # setting host/guest allocation
            self.logger.debug("Setting host/guest allocation for %s, VMs: %s" % (host, host_systems[host]))
            if self._set_virt_host(host, host_systems[host]) is None:
                raise RhnClassicPortalException("Failed to set host/guest allocation for %s (guests: %s)" % (host, host_systems[host]))

        return self.systems

    def get_rhn_content(self, system, repo, package, verify=False):
        if not system in self.systems:
            raise RhnClassicPortalException("System %s is not in systems list" % system)
        headers = self._retr(self.rpc._request, lambda res: res is not None, 1, True, None, 'up2date.login', (self.systems[system]['details'], ))
        return requests.get("%s/GET-REQ/%s/getPackage/%s" % (self.xmlrpc_url, repo, package), headers=headers, verify=verify)
