#!/usr/bin/env python
# -*- encoding: utf-8 -*-

""" SubscriptionManagementPortal module """

import requests
import json
import re
import tempfile
import os
import time
import csv
import random
import inspect
from rhsm import connection

from baseportal import BasePortal, BasePortalException


class SMPortalException(BasePortalException):
    """ SMPortalException """
    pass


class SMPortal(BasePortal):
    """ SMPortal """

    def __init__(self, api_url=None, candlepin_url=None, portal_url=None, login='admin', password='admin', maxtries=40, insecure=None):
        BasePortal.__init__(self, login, password, maxtries, insecure, api_url, portal_url)
        self.candlepin_url = candlepin_url
        self.con = connection.UEPConnection(self.candlepin_url, username=self.login, password=self.password, insecure=insecure)

    def _get_subscriptions(self):
        """ Get existing subsctiptions """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        owners = self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.login)
        self.logger.debug("Owners: %s" % owners)
        subscriptions = []
        for own in owners:
            pools = self._retr(self.con.getPoolsList, lambda res: res is not None, 1, True, self.portal_login, owner=own['key'])
            for pool in pools:
                subscriptions.append(pool['subscriptionId'])
            self.logger.debug("Subscriptions: %s" % subscriptions)
        return set(subscriptions)

    def check_subscriptions(self, uid_list, external_heal = None):
        """ Check subscription status """
        uid_set = set([str(uid) for uid in uid_list])
        if not external_heal:
            heal = self.portal_login
        else:
            heal = lambda: (external_heal(), self.portal_login())
        sub_set = self._retr(self._get_subscriptions, lambda res: uid_set <= res, 30, False, heal)
        if sub_set is not None:
            return "<Response [200]>"
        else:
            self.logger.error("Can't find subscriptions")
            return None

    def create_distributor(self, name, distributor_version='sam-1.3'):
        """ Create new SAM distributor on portal"""
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        distributor = self._retr(self.con.registerConsumer, lambda res: 'uuid' in res, 1, True, self.portal_login,
                                 name=name, type={'id': '5', 'label': 'sam', 'manifest': True}, facts={'distributor_version': distributor_version})
        return distributor['uuid']

    def create_satellite(self, name, distributor_version='sat-5.6'):
        """ Create new Satellite5 distributor on portal"""
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        distributor = self._retr(self.con.registerConsumer, lambda res: 'uuid' in res, 1, True, self.portal_login,
                                 name=name, type={'id': '9', 'label': 'satellite', 'manifest': True},
                                 facts={'distributor_version': distributor_version, 'system.certificate_version': '3.0'})
        return distributor['uuid']

    def distributor_available_subscriptions(self, uuid):
        """ Get available/attached subscriptions """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        owners = self._retr(self.con.getOwnerList, lambda res: 'key' in res[0], 1, True, self.portal_login, self.login)
        subscriptions = []
        for own in owners:
            pools = self._retr(self.con.getPoolsList, lambda res: res is not None, 1, True, self.portal_login, owner=own['key'])
            for pool in pools:
                if 'subscriptionSubKey' in pool and pool['subscriptionSubKey'] == 'derived':
                    # skip derived pools
                    continue
                if pool['quantity'] >= 0:
                    count = pool['quantity'] - pool['consumed']
                else:
                    # unlimited pool
                    count = pool['quantity']
                if count != 0:
                    subscriptions.append({'id': pool['id'],
                                          'name': pool['productName'],
                                          'quantity': count,
                                          'subscriptionId': pool['subscriptionId'],
                                          'productId': pool['productId'],
                                          'date_start': pool['startDate'],
                                          'date_end': pool['endDate']})
        return subscriptions

    def distributor_attached_subscriptions(self, uuid):
        """ Get available/attached subscriptions """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        subscriptions = []
        entitlements = self._retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, consumerId=uuid)
        for entitlement in entitlements:
            serials = []
            for cert in entitlement['certificates']:
                serials.append(cert['serial']['serial'])
            pool = entitlement['pool']
            subscriptions.append({'id': pool['id'],
                                  'name': pool['productName'],
                                  'quantity': pool['consumed'],
                                  'date_start': pool['startDate'],
                                  'date_end': pool['endDate'],
                                  'serials': serials})
        return subscriptions

    def distributor_attach_everything(self, uuid):
        """ Attach all available subscriptions to distributor """
        return self.distributor_attach_subscriptions(uuid, subscriptions=None)

    def distributor_attach_subscriptions(self, uuid, subscriptions=None):
        """ Attach subscriptions to distributor """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        if subscriptions is None:
            subscriptions = self.distributor_available_subscriptions(uuid)
            for sub in subscriptions:
                if sub['quantity'] < 0:
                    # unlimited pool, add 64
                    sub['quantity'] = 64
        if subscriptions is None or subscriptions == []:
            raise SMPortalException("Nothing to attach")
        for sub in subscriptions:
            self._retr(self.con.bindByEntitlementPool, lambda res: res is not None, 1, True, self.portal_login, uuid, sub['id'], sub['quantity'])
        return "<Response [200]>"

    def distributor_detach_subscriptions(self, uuid, subscriptions=[]):
        """ Detach subscriptions from distributor """
        detach_serials = []
        detach_subs = []
        attached_subs = self.distributor_attached_subscriptions(uuid)
        for sub in attached_subs:
            if sub['id'] in subscriptions:
                # this sub should be detached
                detach_serials += sub['serials']
                detach_subs.append(sub['id'])
        diff = list(set(subscriptions) - set(detach_subs))
        if len(diff) != 0:
            raise SMPortalException("Can't detach subs: %s" % diff)
        self.con.ping()
        for serial in detach_serials:
            self._retr(self.con.unbindBySerial, lambda res: True, 1, True, self.portal_login, uuid, serial)
        return "<Response [200]>"

    def distributor_download_manifest(self, uuid):
        """ Download manifest """
        req = self._retr(requests.get, lambda res: res.status_code == 200, 1, True, self.portal_login,
                         "https://%s%s/consumers/%s/export" % (self.con.host, self.con.handler, uuid), verify=False, auth=(self.login, self.password))
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tfile.write(req.content)
        tfile.close()
        return tfile.name

    def satellite_download_cert(self, uuid):
        """ Download satellite cert """
        session = self.portal_login()
        req = self._retr(session.get, lambda res: res.status_code == 200 and res.headers['content-type'] == 'application/octet-stream', 10, True, self.portal_login,
                         self.portal_url + "/management/distributors/%s/certificate/satellite?" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
        tfile.write(req.content)
        tfile.close()
        return tfile.name

    def delete_distributor(self, uuid):
        """ Delete distributor """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        self._retr(self.con.unregisterConsumer, lambda res: True, 1, True, self.portal_login, uuid)
        return "<Response [200]>"

    def _register_hypervisor(self, org=None, sys_name=None):
        """ Register hypervisor """
        if sys_name is None:
            sys_name = 'TestHypervisor' + ''.join(random.choice('0123456789ABCDEF') for i in range(6))

        sys = self._retr(self.con.registerConsumer, lambda res: res is not None, 1, True, self.portal_login,
                         name=sys_name, type={'id': '6', 'label': 'hypervisor', 'manifest': True}, facts={}, owner=org)
        self.logger.info("Hypervisor %s created with uid %s" % (sys_name, sys['uuid']))
        return (sys_name, sys['uuid'])

    def _register_system(self, org=None, sys_name=None, cores=1, sockets=1, memory=2, arch='x86_64',
                         dist_name='RHEL', dist_version='6.4', installed_products=[], is_guest=False,
                         virt_uuid='', entitlement_dir=None):
        """ Register system """
        if sys_name is None:
            sys_name = 'Testsys' + ''.join(random.choice('0123456789ABCDEF') for i in range(6))

        facts = {}
        facts['virt.is_guest'] = is_guest
        if is_guest:
            facts['virt.uuid'] = virt_uuid
        if sockets is not None:
            facts['cpu.cpu_socket(s)'] = sockets
            if cores is not None:
                facts['cpu.core(s)_per_socket'] = cores / sockets
        if memory is not None:
            facts['memory.memtotal'] = str(memory * 1024 * 1024)
        facts['uname.machine'] = arch
        facts['system.certificate_version'] = '3.2'
        facts['distribution.name'], facts['distribution.version'] = (dist_name, dist_version)

        sys = self._retr(self.con.registerConsumer, lambda res: res is not None, 1, True, self.portal_login,
                         name=sys_name, facts=facts, installed_products=installed_products, owner=org)

        self.logger.info("Sys %s created with uid %s" % (sys_name, sys['uuid']))
        if entitlement_dir is not None:
            try:
                with open(entitlement_dir + '/%s.json' % sys_name, 'w') as filed:
                    filed.write(json.dumps(sys))
            except:
                self.logger.error("Failed to write system data to %s" % entitlement_dir)

        return (sys_name, sys['uuid'])

    @staticmethod
    def _get_suitable_pools(pools, productid, is_virtual):
        """ Get suitable pools """
        pool_ids = []
        for pool in pools:
            if pool['productId'] == productid and (pool['consumed'] < pool['quantity'] or pool['quantity'] == -1):
                if is_virtual in [True, 'true', 'True'] and pool['subscriptionSubKey'] != 'master':
                    pool_ids.insert(0, pool['id'])
                elif pool['subscriptionSubKey'] == 'master':
                    pool_ids.append(pool['id'])
                else:
                    # skip derived pools for non-virtual systems
                    pass
        return pool_ids

    def subscribe_systems(self, systems=None, csv_file=None, org=None, update=False):
        """ Subscribe systems """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        if systems is None and csv_file is None:
            self.logger.error('Neither csv_file nor systems were specified!')
            return None

        if systems is None and org is None:
            self.logger.error('Neither org nor systems were specified!')
            return None

        if systems is not None:
            all_systems = systems[::]
        else:
            all_systems = []
            for consumer in self._retr(self.con.getConsumers, lambda res: res is not None, 1, True, self.portal_login, owner=org):
                # put physical systems in front
                if not 'facts' in consumer:
                    # need to fetch additional data
                    consumer = self._retr(self.con.getConsumer, lambda res: res is not None, 1, True, self.portal_login, consumer['uuid'])

                if consumer['facts']['virt.is_guest'] in [True, 'true', 'True']:
                    all_systems.append(consumer)
                else:
                    all_systems.insert(0, consumer)

        if org is None:
            owners = self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.login)
            self.logger.debug("Owners: %s" % owners)
        else:
            owners = [org]

        ext_subs = {}

        if systems is None:
            data = csv.DictReader(open(csv_file))
            for row in data:
                num = 0
                total = int(row['Count'])
                subscriptions = []
                if row['Subscriptions']:
                    for sub in row['Subscriptions'].split(';'):
                        [sub_id, sub_name] = sub.split('|')
                        subscriptions.append({'productId': sub_id, 'productName': sub_name})
                while num < total:
                    num += 1
                    name = self._namify(row['Name'], num)
                    ext_subs[name] = subscriptions

        for sys in all_systems:
            pools = []
            if org is None:
                for own in owners:
                    own_pools = self._retr(self.con.getPoolsList, lambda res: res is not None, 1, True, self.portal_login, sys['uuid'], owner=own['key'])
                    pools += own_pools
            else:
                pools = self._retr(self.con.getPoolsList, lambda res: res is not None, 1, True, self.portal_login, sys['uuid'], owner=org)

            existing_subs = []
            if update:
                for ent in self._retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, sys['uuid']):
                    existing_subs.append(ent['pool']['productId'])

            processed_subs = []

            if systems is None:
                if sys['name'] in ext_subs:
                    system_subs = ext_subs[sys['name']]
                else:
                    self.logger.error('No subscription data for %s:%s' % (sys['name'], sys['uuid']))
                    system_subs = []
            else:
                system_subs = sys['subscriptions']

            if org is not None:
                # we need to bind as customer
                idcert = self._retr(self.con.getConsumer, lambda res: res is not None, 1, True, self.portal_login, sys['uuid'])
                tf_cert = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                tf_cert.write(idcert['idCert']['cert'])
                tf_cert.close()
                tf_key = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                tf_key.write(idcert['idCert']['key'])
                tf_key.close()
                con_client = connection.UEPConnection(self.candlepin_url, insecure=self.insecure, cert_file=tf_cert.name, key_file=tf_key.name)
            else:
                con_client = self.con
                tf_cert = None
                tf_key = None

            for sub in system_subs:
                processed_subs.append(sub['productId'])
                if not sub['productId'] in existing_subs:
                    # we need to attach sub
                    pool_ids = self._get_suitable_pools(pools, sub['productId'], sys['facts']['virt.is_guest'])
                    attached = None
                    for pool_id in pool_ids:
                        maxtries_old = self.maxtries
                        self.maxtries = 2
                        req = self._retr(con_client.bindByEntitlementPool, lambda res: res is not None, 1, False, None, sys['uuid'], pool_id)
                        self.maxtries = maxtries_old
                        if req is not None:
                            attached = pool_id
                            break
                    if attached is not None:
                        self.logger.info('Successfully subscribed system %s:%s to pool %s' % (sys['name'], sys['uuid'], attached))
                    else:
                        self.logger.error('Failed to find appropriate pool for system %s:%s' % (sys['name'], sys['uuid']))
            if update:
                for ent in self._retr(con_client.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, sys['uuid']):
                    if not ent['pool']['productId'] in processed_subs:
                        # unbinding everything else
                        serial = ent['certificates'][0]['serial']['serial']
                        req = self._retr(con_client.unbindBySerial, lambda res: res is not None, 1, True, self.portal_login, sys['uuid'], serial)
            if tf_cert is not None:
                os.unlink(tf_cert.name)
            if tf_key is not None:
                os.unlink(tf_key.name)

        return "<Response [200]>"

    def create_systems(self, csv_file, entitlement_dir=None, org=None, subscribe=True, update=False):
        """
        Register a bunch of systems from CSV file

        # CSV: Name,Count,Org Label,Environment Label,Groups,Virtual,Host,OS,Arch,Sockets,RAM,Cores,SLA,Products,Subscriptions
        """
        all_systems = []
        host_systems = {}

        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)

        if org is None:
            org = self._retr(self.con.getOwnerList, lambda res: res is not None and res != [] and 'key' in res[0], 1, True, self.portal_login, self.login)[0]['key']
            self.logger.debug("Using %s owner as org" % org)

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
                sockets = int(row['Sockets'])
            except ValueError:
                sockets = None
            try:
                memory = int(row['RAM'])
            except ValueError:
                memory = None
            arch = row['Arch']
            if row['OS'].find(' ') != -1:
                dist_name, dist_version = row['OS'].split(' ')
            else:
                dist_name, dist_version = ('RHEL', row['OS'])
            consumer_type = 'System'
            if 'Type' in row:
                consumer_type = row['Type']

            installed_products = []
            if row['Products']:
                for product in row['Products'].split(';'):
                    [product_number, product_name] = product.split('|')
                    installed_products.append({'productId': int(product_number), 'productName': product_name})

            subscriptions = []
            if row['Subscriptions']:
                for sub in row['Subscriptions'].split(';'):
                    [sub_id, sub_name] = sub.split('|')
                    subscriptions.append({'productId': sub_id, 'productName': sub_name})

            while num < total:
                num += 1
                name = self._namify(row['Name'], num)
                if row['Virtual'] in ['Yes', 'Y', 'y']:
                    is_guest = True
                    virt_uuid = name
                else:
                    is_guest = False
                    virt_uuid = ''

                ntry = 0
                while ntry < self.maxtries:
                    try:
                        if consumer_type in ['system', 'System']:
                            (sys_name, sys_uid) = self._register_system(org, name, cores, sockets, memory, arch, dist_name,
                                                                        dist_version, installed_products, is_guest, virt_uuid, entitlement_dir)
                        elif consumer_type in ['hypervisor', 'Hypervisor']:
                            (sys_name, sys_uid) = self._register_hypervisor(org, name)
                        else:
                            self.logger.error("Unknown consumer type %s for %s" % (consumer_type, name))
                        break
                    except:
                        time.sleep(1)
                        ntry += 1

                all_systems.append({'name': sys_name, 'uuid': sys_uid, 'subscriptions': subscriptions, 'facts': {'virt.is_guest': is_guest}})

                if row['Host'] is not None and row['Host'] != '':
                    host_name = self._namify(row['Host'], num)
                    if not host_name in host_systems:
                        for sys in all_systems:
                            if sys['name'] == host_name:
                                host_systems[host_name] = [sys['uuid']]
                    if host_name in host_systems:
                        host_systems[host_name].append(name)

        self.logger.debug("Host/guest allocation: %s" % host_systems)

        for host in host_systems:
            # setting host/guest allocation
            host_detail = host_systems[host]
            if len(host_detail) > 1:
                self.logger.debug("Setting host/guest allocation for %s, VMs: %s" % (host_detail[0], host_detail[1::]))
                self._retr(self.con.updateConsumer, lambda res: True, 1, True, self.portal_login, host_detail[0], guest_uuids=host_detail[1::])

        if subscribe:
            return self.subscribe_systems(systems=all_systems, csv_file=None, org=org, update=update)
        return all_systems

    def heal_entire_org(self, owner=None, wait=False, timeout=None):
        """ Heal Entire Org """
        if owner is None:
            owner_list = self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.con.username)
            if owner_list is None or owner_list == []:
                self.logger.error('Failed to get owner list')
                return None
            else:
                if len(owner_list) > 1:
                    self.logger.info('There are multiple owners available, will heal the first one: %s' % owner_list[0]['key'])
                owner = owner_list[0]['key']
        url = 'https://%s%s/owners/%s/entitlements' % (self.con.host, self.con.handler, owner)
        req = self._retr(requests.post, lambda res: res.status_code == 202, 1, True, self.portal_login, url,
                         auth=(self.con.username, self.con.password), verify=False)
        if not wait:
            return req
        else:
            # tmp
            return req

    def get_pools(self, owner=None):
        """ Get pools """
        if owner is None:
            owner_list = self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.con.username)
            if owner_list is None or owner_list == []:
                self.logger.error('Failed to get owner list')
                return None
            else:
                if len(owner_list) > 1:
                    self.logger.info('There are multiple owners available, will heal the first one: %s' % owner_list[0]['key'])
                owner = owner_list[0]['key']
        return self._retr(self.con.getPoolsList, lambda res: res is not None, 1, True, self.portal_login, owner=owner)

    def get_entitlements(self, uuid):
        """ Get entitlements (with certs)"""
        entitlements_list = self._retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, uuid)
        return [self._retr(self.con.getEntitlement, lambda res: res is not None, 1, True, self.portal_login, x['id']) for x in entitlements_list]

    def get_owners(self):
        """ Get owners """
        return self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.con.username)

    def get_owner_info(self, owner=None):
        """ Get owner info """
        if owner is None:
            owner_list = self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.con.username)
            if owner_list is None or owner_list == []:
                self.logger.error('Failed to get owner list')
                return None
            else:
                if len(owner_list) > 1:
                    self.logger.info('There are multiple owners available, will heal the first one: %s' % owner_list[0]['key'])
                owner = owner_list[0]['key']
        return self._retr(self.con.getOwnerInfo, lambda res: res is not None, 1, True, self.portal_login, owner)

    def checkin_consumer(self, uuid):
        """ Checkin consumer """
        return self._retr(self.con.checkin, lambda res: res is not None, 1, True, self.portal_login, uuid)

    def establish_client_con(self, uuid):
        """ Connect with client cert """
        self.logger.debug("Trying to connect as %s", uuid)
        data = self._retr(self.con.getConsumer, lambda res: res is not None, 1, True, self.portal_login, uuid)
        tf_cert = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        tf_cert.write(data['idCert']['cert'])
        tf_cert.close()
        tf_key = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        tf_key.write(data['idCert']['key'])
        tf_key.close()
        con_client = connection.UEPConnection(self.candlepin_url, insecure=self.insecure, cert_file=tf_cert.name, key_file=tf_key.name)
        self.logger.debug("Created client connection for %s", uuid)
        return con_client

    def get_client_compliance(self, uuid):
        """ Get client compliance status """
        self.logger.debug("Getting compliance status for %s", uuid)
        con_client = self.establish_client_con(uuid)
        assert con_client is not None
        ret = self._retr(con_client.getCompliance, lambda res: res is not None, 1, True, self.portal_login, uuid)
        os.unlink(con_client.cert_file)
        os.unlink(con_client.key_file)
        return ret

    def cdn_get_file(self, uuid, url, verify=False):
        """ Try accessing content on CDN """
        self.logger.debug("Checking content access, uuid: %s, url: %s", uuid, url)
        con_client = self.establish_client_con(uuid)
        assert con_client is not None
        if 'request_certs' in inspect.getargspec(self.con.getEntitlementList)[0]:
            entitlements = self._retr(con_client.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, uuid, request_certs=True)
        else:
            entitlements = self._retr(con_client.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, uuid)
        req = None
        for entitlement in entitlements:
            # Try all entitlements available
            if 'cert' in entitlement['certificates'][0]:
                entitlement_data = entitlement
            else:
                entitlement_data = self._retr(con_client.getEntitlement, lambda res: res is not None, 1, True, self.portal_login, entitlement['id'])
            tcert = tempfile.NamedTemporaryFile(delete=False)
            tkey = tempfile.NamedTemporaryFile(delete=False)
            tcert.write(entitlement_data['certificates'][0]['cert'])
            tkey.write(entitlement_data['certificates'][0]['key'])
            tcert.close()
            tkey.close()
            req = self._retr(requests.get, lambda res: res is not None, 1, True, None, url, verify=verify, cert=(tcert.name, tkey.name))
            os.unlink(tcert.name)
            os.unlink(tkey.name)
            if req.status_code == 200:
                break
        os.unlink(con_client.cert_file)
        os.unlink(con_client.key_file)
        return req
