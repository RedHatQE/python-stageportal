#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import requests
import json
import re
import tempfile
import argparse
import os
import sys
import time
import pprint
import logging
import csv
import datetime
from rhsm import connection

from baseportal import *


class StagePortalException(BasePortalException):
    pass


class StagePortal(BasePortal):
    candlepin_url = "https://subs.example.com"
    portal_url = "https://access.example.com"

    def __init__(self, api_url=None, candlepin_url=None, portal_url=None, login='admin', password='admin', maxtries=40, insecure=None):
        BasePortal.__init__(self, login, password, maxtries, insecure, api_url)
        self.candlepin_url = candlepin_url
        self.portal_url = portal_url
        self.con = connection.UEPConnection(self.candlepin_url, username=self.login, password=self.password, insecure=insecure)

    def portal_login(self):
        """ Perform portal login, accept terms if needed """
        url = self.portal_url

        if url is None:
            return None

        if url.startswith("https://access."):
            url = "https://www." + url[15:]
        url += '/wapps/sso/login.html'

        s = requests.session()
        s.verify = False

        req1 = self._retr(s.post, lambda res: res.status_code == 200, 1, True, None, url,
                         data={'_flowId': 'legacy-login-flow', 'failureRedirect': url,
                               'username': self.login, 'password': self.password},
                         headers={'Accept-Language': 'en-US'})
        if req1.content.find('Welcome&nbsp;') == -1:
            # Accepting terms
            req_checker = lambda res: res.status_code == 200 and (res.content.find('Open Source Assurance Agreement Acceptance Confirmation') != -1 or res.content.find('Welcome&nbsp;') == -1)
            req2 = self._retr(s.post, req_checker, 1, True, None, url, params={'_flowId': 'legacy-login-flow', '_flowExecutionKey': 'e1s1'},
                             data={'accepted': 'true', '_accepted': 'on', 'optionalTerms_28': 'accept', '_eventId_submit': 'Continue', '_flowExecutionKey': 'e1s1', 'redirect': ''})
        req3 = self._retr(s.get, lambda res: res.status_code == 200, 1, True, None, self.portal_url + "/management/" , verify=False, headers={'Accept-Language': 'en-US'})
        return s

    def _get_subscriptions(self):
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

    def check_subscriptions(self, uid_list):
        """ Check subscription status """
        ntry = 0
        uid_set = set([str(uid) for uid in uid_list])
        sub_set = self._retr(self._get_subscriptions, lambda res: uid_set <= res, 30, False, self.portal_login)
        if sub_set is not None:
            return "<Response [200]>"
        else:
            self.logger.error("Can't find subscriptions")
            return None

    def create_distributor(self, name, distributor_version='sam-1.3'):
        """ Create new distributor on portal"""
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        distributor = self._retr(self.con.registerConsumer, lambda res: 'uuid' in res, 1, True, self.portal_login,
                                name=name, type={'id': '5', 'label': 'sam', 'manifest': True}, facts={'distributor_version': distributor_version})
        return distributor['uuid']

    def distributor_available_subscriptions(self, uuid):
        """ Get available/attached subscriptions """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        owners = self._retr(self.con.getOwnerList, lambda res: 'key' in res[0], 1, True, self.portal_login, self.login)
        subscriptions = []
        for own in owners:
            pools = self._retr(self.con.getPoolsList, lambda res: res is not None, 1, True, self.portal_login, owner=own['key'])
            for pool in pools:
                count = pool['quantity'] - pool['consumed']
                if 'subscriptionSubKey' in pool and pool['subscriptionSubKey'] == 'derived':
                    # skip derived pools
                    continue
                if count > 0:
                    subscriptions.append({'id': pool['id'],
                                          'name': pool['productName'],
                                          'quantity': count,
                                          'date_start': pool['startDate'],
                                          'date_end': pool['endDate']})
        return subscriptions

    def distributor_attached_subscriptions(self, uuid):
        """ Get available/attached subscriptions """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        subscriptions = []
        ntry = 0
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
        if subscriptions is None or subscriptions == []:
            raise StagePortalException("Nothing to attach")
        for sub in subscriptions:
            bind = self._retr(self.con.bindByEntitlementPool, lambda res: res is not None, 1, True, self.portal_login, uuid, sub['id'], sub['quantity'])
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
             raise StagePortalException("Can't detach subs: %s" % diff)
        self.con.ping()
        for serial in detach_serials:
            self._retr(self.con.unbindBySerial, lambda res: True, 1, True, self.portal_login, uuid, serial)
        return "<Response [200]>"

    def distributor_download_manifest(self, uuid):
        """ Download manifest """
        req = self._retr(requests.get, lambda res: res.status_code == 200, 1, True, self.portal_login,
                        "https://%s%s/consumers/%s/export" % (self.con.host, self.con.handler, uuid), verify=False, auth=(self.login, self.password))
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tf.write(req.content)
        tf.close()
        return tf.name

    def _get_distributor_page(self, name):
        """ Get distributor uuid """
        session = self.portal_login()
        req1 = self._retr(session.get, lambda res: res.status_code == 200, 1, True, self.portal_login,
                         self.portal_url + "/management/distributors", verify=False, headers={'Accept-Language': 'en-US'})
        m = re.search("/distributors/([0-9,a-f,-]*)\">" + name + "<", req1.content, re.DOTALL)
        if m is not None:
            return m.group(1)
        else:
            return None

    def distributor_get_uuid(self, name):
        """ Get distributor uuid """
        uuid = self._retr(self._get_distributor_page, lambda res: res is not None, 1, True, None, name)
        return uuid

    def delete_distributor(self, uuid):
        """ Delete distributor """
        self._retr(self.con.ping, lambda res: res is not None, 1, True, self.portal_login)
        self._retr(self.con.unregisterConsumer, lambda res: True, 1, True, self.portal_login, uuid)
        return "<Response [200]>"

    def _register_hypervisor(self, org=None, sys_name=None):
        if sys_name is None:
            sys_name = 'TestHypervisor' + ''.join(random.choice('0123456789ABCDEF') for i in range(6))

        sys = self._retr(self.con.registerConsumer, lambda res: res is not None, 1, True, self.portal_login,
                        name=sys_name, type={'id': '6', 'label': 'hypervisor', 'manifest': True}, facts={}, owner=org)
        self.logger.info("Hypervisor %s created with uid %s" % (sys_name, sys['uuid']))
        return (sys_name, sys['uuid'])

    def _register_system(self, org=None, sys_name=None, cores=1, sockets=1, memory=2, arch='x86_64', dist_name='RHEL', dist_version='6.4', installed_products=[], is_guest=False, virt_uuid='', entitlement_dir=None):
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
                fd = open(entitlement_dir + '/%s.json' % sys_name, 'w')
                fd.write(json.dumps(sys))
                fd.close()
            except:
                self.logger.error("Failed to write system data to %s" % entitlement_dir)

        return (sys_name, sys['uuid'])

    def _get_suitable_pools(self, pools, productId, is_virtual):
        pool_ids = []
        for pool in pools:
            if pool['productId'] == productId and (pool['consumed'] < pool['quantity'] or pool['quantity'] == -1):
                if is_virtual in [True, 'true', 'True'] and pool['subscriptionSubKey'] != 'master':
                    pool_ids.insert(0, pool['id'])
                elif pool['subscriptionSubKey'] == 'master':
                    pool_ids.append(pool['id'])
                else:
                    # skip derived pools for non-virtual systems
                    pass
        return pool_ids

    def subscribe_systems(self, systems=None, csv_file=None, entitlement_dir=None, org=None, update=False):
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
                    pool_ids =  self._get_suitable_pools(pools, sub['productId'], sys['facts']['virt.is_guest'])
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
                for ent in self._retr(client_con.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, sys['uuid']):
                    if not ent['pool']['productId'] in processed_subs:
                        # unbinding everything else
                        serial = ent['certificates'][0]['serial']['serial']
                        req = self._retr(client_con.unbindBySerial, lambda res: res is not None, 1, True, self.portal_login, sys['uuid'], serial)
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

        data = csv.DictReader(open(csv_file))
        for row in data:
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
                            (sys_name, sys_uid) = self._register_system(org, name, cores, sockets, memory, arch, dist_name, dist_version, installed_products, is_guest, virt_uuid, entitlement_dir)
                        elif consumer_type in ['hypervisor', 'Hypervisor']:
                            (sys_name, sys_uid) = self._register_hypervisor(org, name)
                        else:
                            self.logger.error("Unknown consumer type %s for %s" % (consumer_type, name))
                        break
                    except:
                        time.sleep(1)
                        ntry += 1

                all_systems.append({'name': sys_name, 'uuid': sys_uid, 'subscriptions': subscriptions, 'facts':{'virt.is_guest': is_guest}})

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
            return self.subscribe_systems(systems=all_systems, csv_file=None, entitlement_dir=entitlement_dir, org=org, update=update)
        return all_systems

    def heal_entire_org(self, owner=None, wait=False, timeout=None):
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
        req = self._retr(requests.post, lambda res: res.status_code == 202, 1, True, self.portal_login, url, auth=(self.con.username, self.con.password), verify=False)
        if not wait:
            return req
        else:
            # tmp
            return req

    def get_pools(self, owner=None):
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
        return self._retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, self.portal_login, uuid)

    def get_owners(self):
        return self._retr(self.con.getOwnerList, lambda res: res is not None, 1, True, self.portal_login, self.con.username)

    def get_owner_info(self, owner=None):
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
        return self._retr(self.con.checkin, lambda res: res is not None, 1, True, self.portal_login, uuid)


if __name__ == '__main__':
    FORMAT = '%(asctime)s %(levelname)s %(message)s'
    logging.basicConfig(format=FORMAT)
    logging.getLogger("python-stageportal").setLevel(logging.INFO)

    PWLESS_ACTIONS = ['user_get',
                      'sku_add']
    DIST_ACTIONS = ['distributor_create',
                    'distributor_available_subscriptions',
                    'distributor_attached_subscriptions',
                    'distributor_add_subscriptions',
                    'distributor_detach_subscriptions',
                    'distributor_delete',
                    'distributor_get_manifest']
    ALL_ACTIONS = ['user_create'] + PWLESS_ACTIONS + DIST_ACTIONS + ['systems_register', 'subscriptions_check', 'heal_org']

    argparser = argparse.ArgumentParser(description='Stage portal tool', epilog='vkuznets@redhat.com')

    argparser.add_argument('--action', required=True,
                           help='Requested action', choices=ALL_ACTIONS)
    argparser.add_argument('--login', required=True, help='User login')
    argparser.add_argument('--verbose', default=False, action='store_true', help="Verbose bode")

    [args, ignored_args] = argparser.parse_known_args()

    if args.verbose:
        logging.getLogger("python-stageportal").setLevel(logging.INFO)

    portal_required = False
    if args.action in ['distributor_get_manifest']:
        portal_required = True

    argparser.add_argument('--portal', required=portal_required, help='The URL to the stage portal.')

    if args.action in ['user_create', 'user_get', 'sku_add']:
        argparser.add_argument('--api', required=True, help='The URL to the stage portal\'s API.')
        if args.action == 'sku_add':
            argparser.add_argument('--sku-id', required=False, help='SKU id to add')
            argparser.add_argument('--sku-quantity', required=False, help='SKU quantity to add')
            argparser.add_argument('--sku-start-date', required=False, help='SKU start date')
            argparser.add_argument('--csv', required=False, help='CSV file with SKUs.')
    if args.action in DIST_ACTIONS:
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        if args.action == 'distributor_create':
            argparser.add_argument('--distributor-name', required=True, help='Distributor name')
        else:
            argparser.add_argument('--distributor-name', required=False, help='Distributor name')
            argparser.add_argument('--distributor-uuid', required=False, help='Distributor uuid')

        if args.action == 'distributor_add_subscriptions':
            argparser.add_argument('--all', required=False, action='store_true', default=False, help='attach all available subscriptions')
            argparser.add_argument('--sub-id', required=False, help='sub id to attach to distributor')
            argparser.add_argument('--sub-quantity', required=False, help='sub quantity to attach to distributor')

        if args.action == 'distributor_detach_subscriptions':
            argparser.add_argument('--sub-ids', required=True, nargs='+', help='sub ids to detach from distributor (space separated list)')
    if args.action == 'heal_org':
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        argparser.add_argument('--org', required=False, help='Org to heal (standalone candlepin).')
    if args.action == 'systems_register':
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        argparser.add_argument('--csv', required=True, help='CSV file with systems definition.')
        argparser.add_argument('--entitlement-dir', required=False, help='Save entitlement data to dir.')
        argparser.add_argument('--org', required=False, help='Create systems within org (standalone candlepin).')
    if args.action == 'subscriptions_check':
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        argparser.add_argument('--sub-ids', required=True, nargs='+', help='sub ids to check (space separated list)')

    if not args.action in PWLESS_ACTIONS:
        password_required = True
    else:
        password_required = False
    argparser.add_argument('--password', required=password_required, help='User password')

    [args, ignored_args] = argparser.parse_known_args()

    if args.action == 'distributor_add_subscriptions' and args.all is False and (args.sub_id is None or args.sub_quantity is None):
        sys.stderr.write('You should specify --sub-id and --sub-quantity to attach specified subscription or use --all to attach all available subscriptions\n')
        sys.exit(1)

    if args.action == 'sku_add' and args.csv is None and (args.sku_id is None or args.sku_quantity is None or args.sku_start_date is None):
        sys.stderr.write('You should specify --csv or --sku-id, --sku-quantity and --sku-start-date\n')
        sys.exit(1)

    if 'api' in args:
        api = args.api
    else:
        api = None

    if 'candlepin' in args:
        candlepin = args.candlepin.replace("https://", "")
    else:
        candlepin = None

    if 'portal' in args:
        portal = args.portal
    else:
        portal = None

    sp = StagePortal(api_url=api, candlepin_url=candlepin, portal_url=portal, login=args.login, password=args.password)

    if args.action == 'user_create':
        res = sp.create_user()
    elif args.action == 'user_get':
        res = sp.get_user()
    elif args.action == 'sku_add':
        if args.csv is None:
            res = [sp.hock_sku(args.sku_id, args.sku_quantity, args.sku_start_date)]
        else:
            res = sp.add_skus_csv(args.csv)
        if portal is not None and args.password is not None and not (None in res):
            # Checking if subs appeared in candlepin
            res_check = sp.check_subscriptions(res)
            if res_check is None:
                res = None
    elif args.action in DIST_ACTIONS:
        res = None
        if args.action == 'distributor_create':
            res = sp.create_distributor(args.distributor_name)
        else:
            if args.distributor_name is None and args.distributor_uuid is None:
                sys.stderr.write('You should specify --distributor-name or --distributor-uuid\n')
                sys.exit(1)
            if args.distributor_uuid is None:
                distributor_uuid = sp.distributor_get_uuid(args.distributor_name)
            else:
                distributor_uuid = args.distributor_uuid
        if res is None and distributor_uuid is None:
            pass
        elif args.action == 'distributor_available_subscriptions':
            subs = sp.distributor_available_subscriptions(distributor_uuid)
            res = pprint.pformat(subs)
        elif args.action == 'distributor_attached_subscriptions':
            subs = sp.distributor_attached_subscriptions(distributor_uuid)
            res = pprint.pformat(subs)
        elif args.action == 'distributor_add_subscriptions':
            if args.all:
                res = sp.distributor_attach_everything(distributor_uuid)
            else:
                res = sp.distributor_attach_subscriptions(distributor_uuid, subscriptions=[{'id': args.sub_id, 'quantity': args.sub_quantity}])
        elif args.action == 'distributor_detach_subscriptions':
            res = sp.distributor_detach_subscriptions(distributor_uuid, subscriptions=args.sub_ids)
        elif args.action == 'distributor_delete':
            res = sp.delete_distributor(distributor_uuid)
        elif args.action == 'distributor_get_manifest':
            res = sp.distributor_download_manifest(distributor_uuid)
    elif args.action == 'systems_register':
        # protect against 'you need to accept terms'
        res = sp.create_systems(args.csv, args.entitlement_dir, args.org)
        if res is not None:
            res = "<Response [200]>"
    elif args.action == 'subscriptions_check':
        res = sp.check_subscriptions(args.sub_ids)
    elif args.action == 'heal_org':
        res = sp.heal_entire_org()
    else:
        sys.stderr.write('Unknown action: %s\n' % args.action)
        sys.exit(1)
    sys.stdout.write('%s\n' % res)
    if res in [[], None]:
        sys.exit(1)
