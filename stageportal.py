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


class StagePortalException(Exception):
    pass


class StagePortal(object):
    api_url = "http://example.com/svcrest"
    candlepin_url = "https://subs.example.com"
    portal_url = "https://access.example.com"

    def __init__(self, api_url=None, candlepin_url=None, portal_url=None, login='admin', password='admin', maxtries=40, insecure=None):
        self.logger = logging.getLogger("python-stageportal")
        self.api_url = api_url
        self.candlepin_url = candlepin_url
        self.portal_url = portal_url
        self.maxtries = maxtries
        self.insecure = insecure
        self.login = login
        self.password = password
        self.con = connection.UEPConnection(self.candlepin_url, username=self.login, password=self.password, insecure=insecure)

    def retr(self, func, check, sleep, blow_up, do_login, *args, **kwargs):
        res = None
        ntry = 0
        self.logger.debug("Performing %s with args: %s kwargs %s" % (func, args, kwargs))
        while ntry < self.maxtries:
            try:
                res = func(*args, **kwargs)
            except Exception, e:
                self.logger.debug("Exception during %s execution: %s" % (func, e))
                if do_login:
                    self.portal_login()
            try:
                self.logger.debug("Checking %s after %s" % (res, func))
                if check(res):
                    self.logger.debug("Checking: passed")
                    break
                else:
                    self.logger.debug("Checking: failed")
            except Exception, e:
                self.logger.debug("Checking: exception: %s" % e)
                if do_login:
                    self.portal_login()
            ntry += 1
            time.sleep(sleep)
        if ntry >= self.maxtries:
            self.logger.error("%s failed after %s tries, last result: %s" % (func, self.maxtries, res))
            if blow_up is True:
                raise StagePortalException("%s failed after %s tries, last result: %s" % (func, self.maxtries, res))
            else:
                res = None
        return res

    def get_user(self):
        """ Get portal user """

        url = "%s/user/v3/login=%s" % (self.api_url, self.login)
        user = self.retr(requests.get, lambda res: res.json()[0]['customer']['id'] is not None, 1, True, False, url)
        return user.json()[0]['customer']['id']

    def create_user(self):
        """ Create portal user """

        url = "%s/user/v3/create" % self.api_url

        newuser = {"login": self.login,
                   "loginUppercase": self.login.upper(),
                   "password": self.password,
                   "system": "WEB",
                   "userType": "P",
                   "personalInfo": {"phoneNumber": "1234567890",
                                    "email": "dev-null@redhat.com",
                                    "firstName": self.login,
                                    "lastName": "User",
                                    "greeting": "Mr."},
                   "personalSite": {"siteType": "MARKETING",
                                    "address": {"address1": "1801 Varsity Dr.",
                                                "city": "Raleigh",
                                                "state": "NC",
                                                "county": "Wake",
                                                "countryCode": "US",
                                                "postalCode": "27606"}}}
        return self.retr(requests.post, lambda res: int(res.content) is not None, 1, True, False, url, headers={"Content-Type": 'application/json'}, data=json.dumps(newuser)).content

    def activate(self, regNumber, start_date):
        """ Activate regNumber """

        url = "%s/activation/v2/activate" % self.api_url

        webCustomerId = self.get_user()
        data = {"activationKey": regNumber,
                "vendor": "REDHAT",
                "startDate": start_date,
                "userName": self.login,
                "webCustomerId": webCustomerId,
                "systemName": "genie"
                }
        req = self.retr(requests.post, lambda res: res.json()['id'] is not None, 1, True, False, url, headers={"Content-Type": 'application/json'}, data=json.dumps(data))
        return req.json()['id']

    def hock_sku(self, SKU, quantity, start_date):
        """ Place an order """
        url = "%s/regnum/v5/hock/order" % self.api_url

        webCustomerId = self.get_user()
        data = {"regnumType": "entitlement",
                "satelliteVersion": "",
                "login": self.login,
                "vendor": "REDHAT",
                "sendMail": False,
                "notifyVendor": False,
                "header": {"companyName": "",
                           "customerNumber": webCustomerId,
                           "customerContactName": "Hockeye",
                           "customerContactEmail": "dev-null@redhat.com",
                           "customerRhLoginId": self.login,
                           "opportunityNumber": 0,
                           "emailType": "ENGLISH",
                           "industry": "Software",
                           "salesRepName": "Salesguy",
                           "salesRepEmail": "dev-null@redhat.com",
                           "rhPartnerDevMgrName": "DevManager",
                           "rhPartnerDevMgrEmail": "dev-null@redhat.com",
                           "partnerClassification": "",
                           "classificationOther": "",
                           "promocode": "",
                           "revPublication": "",
                           "rhManagerName": "Manager",
                           "rhManagerEmail": "dev-null@redhat.com",
                           "yourHockerName": "Genie",
                           "yourHockerEmail": "dev-null@redhat.com",
                           "publicationTitle": "",
                           "publisher": "",
                           "expectedPublicationDate": "",
                           "program": {"id": 1,
                                       "shortName": "PRODUCTION",
                                       "name": "Production Hock",
                                       "description": "Product Code Creation for Subscription Operations",
                                       "active": True,
                                       "quota": 100,
                                       "group": "staff:pm:hock",
                                       "bccEmails": "dev-null@redhat.com",
                                       "addtEmails": "dev-null@redhat.com"}},
                "lines": [{"productSKU": SKU,
                           "serviceTagHashed": False,
                           "additionalEmails": [],
                           "ccList": [],
                           "bccList": [],
                           "numSuperRegnums": 1,
                           "lineItem": {"sku": SKU,
                                        "opUnit": "",
                                        "quantity": quantity,
                                        "zuper": True,
                                        "replicator": {"replicatorId": 30},
                                        "reason": {"id": "14"},
                                        "subject": "",
                                        "comments": "",
                                        "completed": False,
                                        "renew": False,
                                        "entitlementStartDate": start_date,
                                        "satelliteVersion": "",
                                        "poNumber": "",
                                        "salesOrderNumber": "",
                                        "emailCc": "",
                                        "emailBcc": "",
                                        "emailType": "ENDUSER",
                                        "recipient": "",
                                        "webContactId": "",
                                        "groupIdentifier": "",
                                        "duration": "1 year",
                                        "opUnitId": 103,
                                        "userAcctNumber": "",
                                        "partnerAcctNumber": "",
                                        "replicatorAcctNumber": ""}}]}

        order = self.retr(requests.put, lambda res: 'regNumbers' in res.json(), 1, True, False, url, headers={"Content-Type": 'application/json'}, data=json.dumps(data))
        regNumber = order.json()['regNumbers'][0][0]['regNumber']
        return self.activate(regNumber, start_date)

    def add_skus(self, skus):
        """
        Create SKUs
        """
        sku_added_list = []
        for sku in skus:
            sku_added_list.append(self.hock_sku(sku['Id'], sku['Quantity'], sku['Start Date']))
        return sku_added_list

    def add_skus_csv(self, csv_file):
        """
         CSV:
         Id, Quantity[, Start Date]
        """
        sku_list = []
        data = csv.DictReader(open(csv_file))
        for row in data:
            if row['Id'][0] == '#':
                # skipping comments
                continue
            if 'Start Date' in row:
                try:
                    start_date = (datetime.datetime.now() + datetime.timedelta(int(row['Start Date']))).strftime("%Y-%m-%d")
                except:
                    start_date = row['Start Date']
            else:
                 start_date = datetime.datetime.now().strftime("%Y-%m-%d")
            sku_list.append({'Id': row['Id'], 'Quantity': row['Quantity'], 'Start Date': start_date})
        return self.add_skus(sku_list)

    def portal_login(self):
        """ Perform portal login, accept terms if needed """
        url = self.portal_url

        if url.startswith("https://access."):
            url = "https://www." + url[15:]
        url += '/wapps/sso/login.html'

        s = requests.session()
        s.verify = False

        req1 = self.retr(s.post, lambda res: res.status_code == 200, 1, True, False, url,
                         data={'_flowId': 'legacy-login-flow', 'failureRedirect': url,
                               'username': self.login, 'password': self.password},
                         headers={'Accept-Language': 'en-US'})
        if req1.content.find('Welcome&nbsp;') == -1:
            # Accepting terms
            req_checker = lambda res: res.status_code == 200 and (res.content.find('Open Source Assurance Agreement Acceptance Confirmation') != -1 or res.content.find('Welcome&nbsp;') == -1)
            req2 = self.retr(s.post, req_checker, 1, True, False, url, params={'_flowId': 'legacy-login-flow', '_flowExecutionKey': 'e1s1'},
                             data={'accepted': 'true', '_accepted': 'on', 'optionalTerms_28': 'accept', '_eventId_submit': 'Continue', '_flowExecutionKey': 'e1s1', 'redirect': ''})
        req3 = self.retr(s.get, lambda res: res.status_code == 200, 1, True, False, self.portal_url + "/management/" , verify=False, headers={'Accept-Language': 'en-US'})
        return s

    def _get_subscriptions(self):
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
        owners = self.retr(self.con.getOwnerList, lambda res: res is not None, 1, True, True, self.login)
        self.logger.debug("Owners: %s" % owners)
        subscriptions = []
        for own in owners:
            pools = self.retr(self.con.getPoolsList, lambda res: res is not None, 1, True, True, owner=own['key'])
            for pool in pools:
                subscriptions.append(pool['subscriptionId'])
            self.logger.debug("Subscriptions: %s" % subscriptions)
        return set(subscriptions)

    def check_subscriptions(self, uid_list):
        """ Check subscription status """
        ntry = 0
        uid_set = set([str(uid) for uid in uid_list])
        sub_set = self.retr(self._get_subscriptions, lambda res: uid_set <= res, 30, False, True)
        if sub_set is not None:
            return "<Response [200]>"
        else:
            self.logger.error("Can't find subscriptions")
            return None

    def create_distributor(self, name, distributor_version='sam-1.3'):
        """ Create new distributor on portal"""
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
        distributor = self.retr(self.con.registerConsumer, lambda res: 'uuid' in res, 1, True, True,
                                name=name, type={'id': '5', 'label': 'sam', 'manifest': True}, facts={'distributor_version': distributor_version})
        return distributor['uuid']

    def distributor_available_subscriptions(self, uuid):
        """ Get available/attached subscriptions """
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
        owners = self.retr(self.con.getOwnerList, lambda res: 'key' in res[0], 1, True, True, self.login)
        subscriptions = []
        for own in owners:
            pools = self.retr(self.con.getPoolsList, lambda res: res is not None, 1, True, True, owner=own['key'])
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
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
        subscriptions = []
        ntry = 0
        entitlements = self.retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, True, consumerId=uuid)
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
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
        if subscriptions is None:
            subscriptions = self.distributor_available_subscriptions(uuid)
        if subscriptions is None or subscriptions == []:
            raise StagePortalException("Nothing to attach")
        for sub in subscriptions:
            bind = self.retr(self.con.bindByEntitlementPool, lambda res: res is not None, 1, True, True, uuid, sub['id'], sub['quantity'])
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
            self.retr(self.con.unbindBySerial, lambda res: True, 1, True, True, uuid, serial)
        return "<Response [200]>"

    def distributor_download_manifest(self, uuid):
        """ Download manifest """
        req = self.retr(requests.get, lambda res: res.status_code == 200, 1, True, True,
                        "https://%s%s/consumers/%s/export" % (self.con.host, self.con.handler, uuid), verify=False, auth=(self.login, self.password))
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tf.write(req.content)
        tf.close()
        return tf.name

    def _get_distributor_page(self, name):
        """ Get distributor uuid """
        session = self.portal_login()
        req1 = self.retr(session.get, lambda res: res.status_code == 200, 1, True, True,
                         self.portal_url + "/management/distributors", verify=False, headers={'Accept-Language': 'en-US'})
        m = re.search("/distributors/([0-9,a-f,-]*)\">" + name + "<", req1.content, re.DOTALL)
        if m is not None:
            return m.group(1)
        else:
            return None

    def distributor_get_uuid(self, name):
        """ Get distributor uuid """
        uuid = self.retr(self._get_distributor_page, lambda res: res is not None, 1, True, False, name)
        return uuid

    def delete_distributor(self, uuid):
        """ Delete distributor """
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
        self.retr(self.con.unregisterConsumer, lambda res: True, 1, True, True, uuid)
        return "<Response [200]>"

    @staticmethod
    def _namify(name, row):
        try:
            return name % row
        except TypeError:
            return name

    def _register_hypervisor(self, org=None, sys_name=None):
        if sys_name is None:
            sys_name = 'TestHypervisor' + ''.join(random.choice('0123456789ABCDEF') for i in range(6))

        sys = self.retr(self.con.registerConsumer, lambda res: res is not None, 1, True, True,
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
        facts['cpu.core(s)_per_socket'] = str(cores)
        facts['cpu.cpu_socket(s)'] = str(sockets)
        facts['memory.memtotal'] = str(int(memory) * 1024 * 1024)
        facts['uname.machine'] = arch
        facts['system.certificate_version'] = '3.2'
        facts['distribution.name'], facts['distribution.version'] = (dist_name, dist_version)

        sys = self.retr(self.con.registerConsumer, lambda res: res is not None, 1, True, True,
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
        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)
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
            for consumer in self.retr(self.con.getConsumers, lambda res: res is not None, 1, True, True, owner=org):
                # put physical systems in front
                if not 'facts' in consumer:
                    # need to fetch additional data
                    consumer = self.retr(self.con.getConsumer, lambda res: res is not None, 1, True, True, consumer['uuid'])

                if consumer['facts']['virt.is_guest'] in [True, 'true', 'True']:
                    all_systems.append(consumer)
                else:
                    all_systems.insert(0, consumer)

        if org is None:
            owners = self.retr(self.con.getOwnerList, lambda res: res is not None, 1, True, True, self.login)
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
                    own_pools = self.retr(self.con.getPoolsList, lambda res: res is not None, 1, True, True, sys['uuid'], owner=own['key'])
                    pools += own_pools
            else:
                pools = self.retr(self.con.getPoolsList, lambda res: res is not None, 1, True, True, sys['uuid'], owner=org)

            existing_subs = []
            if update:
                for ent in self.retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, True, sys['uuid']):
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
                idcert = self.retr(self.con.getConsumer, lambda res: res is not None, 1, True, True, sys['uuid'])
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
                        req = self.retr(con_client.bindByEntitlementPool, lambda res: res is not None, 1, False, False, sys['uuid'], pool_id)
                        self.maxtries = maxtries_old
                        if req is not None:
                            attached = pool_id
                            break
                    if attached is not None:
                        self.logger.info('Successfully subscribed system %s:%s to pool %s' % (sys['name'], sys['uuid'], attached))
                    else:
                        self.logger.error('Failed to find appropriate pool for system %s:%s' % (sys['name'], sys['uuid']))
            if update:
                for ent in self.retr(client_con.getEntitlementList, lambda res: res is not None, 1, True, True, sys['uuid']):
                    if not ent['pool']['productId'] in processed_subs:
                        # unbinding everything else
                        serial = ent['certificates'][0]['serial']['serial']
                        req = self.retr(client_con.unbindBySerial, lambda res: res is not None, 1, True, True, sys['uuid'], serial)
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

        self.retr(self.con.ping, lambda res: res is not None, 1, True, True)

        data = csv.DictReader(open(csv_file))
        for row in data:
            num = 0
            total = int(row['Count'])
            cores = row['Cores']
            sockets = row['Sockets']
            memory = row['RAM']
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

                if row['Host'] is not None:
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
                self.retr(self.con.updateConsumer, lambda res: True, 1, True, True, host_detail[0], guest_uuids=host_detail[1::])

        if subscribe:
            return self.subscribe_systems(systems=all_systems, csv_file=None, entitlement_dir=entitlement_dir, org=org, update=update)
        return all_systems

    def heal_entire_org(self, owner=None, wait=False, timeout=None):
        if owner is None:
            owner_list = self.retr(self.con.getOwnerList, lambda res: res is not None, 1, True, True, self.con.username)
            if owner_list is None or owner_list == []:
                self.logger.error('Failed to get owner list')
                return None
            else:
                if len(owner_list) > 1:
                    self.logger.info('There are multiple owners available, will heal the first one: %s' % owner_list[0]['key'])
                owner = owner_list[0]['key']
        url = 'https://%s%s/owners/%s/entitlements' % (self.con.host, self.con.handler, owner)
        req = self.retr(requests.post, lambda res: res.status_code == 202, 1, True, True, url, auth=(self.con.username, self.con.password), verify=False)
        if not wait:
            return req
        else:
            # tmp
            return req

    def get_pools(self, owner=None):
        if owner is None:
            owner_list = self.retr(self.con.getOwnerList, lambda res: res is not None, 1, True, True, self.con.username)
            if owner_list is None or owner_list == []:
                self.logger.error('Failed to get owner list')
                return None
            else:
                if len(owner_list) > 1:
                    self.logger.info('There are multiple owners available, will heal the first one: %s' % owner_list[0]['key'])
                owner = owner_list[0]['key']
        return self.retr(self.con.getPoolsList, lambda res: res is not None, 1, True, True, owner=owner)

    def get_entitlements(self, uuid):
        return self.retr(self.con.getEntitlementList, lambda res: res is not None, 1, True, True, uuid)

    def get_owners(self):
        return self.retr(self.con.getOwnerList, lambda res: res is not None, 1, True, True, self.con.username)

    def get_owner_info(self, owner=None):
        if owner is None:
            owner_list = self.retr(self.con.getOwnerList, lambda res: res is not None, 1, True, True, self.con.username)
            if owner_list is None or owner_list == []:
                self.logger.error('Failed to get owner list')
                return None
            else:
                if len(owner_list) > 1:
                    self.logger.info('There are multiple owners available, will heal the first one: %s' % owner_list[0]['key'])
                owner = owner_list[0]['key']
        return self.retr(self.con.getOwnerInfo, lambda res: res is not None, 1, True, True, owner)


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
