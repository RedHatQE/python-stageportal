#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import requests
import json
import re
import tempfile
import argparse
import sys
import time
import pprint
import logging
import csv
import datetime
from rhsm import connection

FORMAT = '%(asctime)s %(levelname)s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("python-stageportal")
logger.setLevel(logging.INFO)


class StagePortal(object):
    api_url = "http://example.com/svcrest"
    candlepin_url = "https://subs.example.com"
    portal_url = "https://access.example.com"
    maxtries = 20

    def __init__(self, api_url=None, candlepin_url=None, portal_url=None, login='admin', password='admin', maxtries=20, insecure=None):
        self.api_url = api_url
        self.candlepin_url = candlepin_url
        self.portal_url = portal_url
        self.maxtries = maxtries
        self.insecure = insecure
        self.login = login
        self.password = password
        self.con = connection.UEPConnection(self.candlepin_url, username=self.login, password=self.password)

    def get_user(self):
        """ Get portal user """

        url = "%s/user/v3/login=%s" % (self.api_url, self.login)

        user = requests.get(url).json()
        if len(user) > 0:
            return user[0]['customer']['id']
        else:
            return None

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
        ntry = 0
        id = None
        while True:
            req = requests.post(url, headers={"Content-Type": 'application/json'}, data=json.dumps(newuser)).content
            try:
                id = int(req)
                break
            except ValueError:
                sys.stderr.write(req + "\n")
                pass
            ntry += 1
            if ntry > self.maxtries:
                break
        return id

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
        return requests.post(url,
                             headers={"Content-Type": 'application/json'},
                             data=json.dumps(data)).json()['id']

    def hock_sku(self, SKU, quantity, start_date):
        """ Place an order """
        url = "%s/regnum/v5/hock/order" % self.api_url

        data = {"regnumType": "entitlement",
                "satelliteVersion": "",
                "login": self.login,
                "vendor": "REDHAT",
                "sendMail": False,
                "notifyVendor": False,
                "header": {"companyName": "",
                           "customerNumber": 1234567890,
                           "customerContactName": "Hockeye",
                           "customerContactEmail": "dev-null@redhat.com",
                           "customerRhLoginId": "qa@redhat.com",
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

        order = requests.put(url, headers={"Content-Type": 'application/json'}, data=json.dumps(data)).json()
        regNumber = order['regNumbers'][0][0]['regNumber']
        return self.activate(regNumber, start_date)

    def add_skus_csv(self, csv_file):
        """
         CSV:
         Id, Quantity, Start Date
        """
        sku_list = []
        data = csv.DictReader(open(csv_file))
        for row in data:
            start_date = (datetime.datetime.now() + datetime.timedelta(int(row['Start Date']))).strftime("%Y-%m-%d")
            if row['Id'][0] != '#':
                # skipping comments
                sku_list.append(self.hock_sku(row['Id'], row['Quantity'], start_date))
        return sku_list

    def portal_login(self):
        """ Perform portal login, accept terms if needed """
        url = self.portal_url

        if url.startswith("https://access."):
            url = "https://www." + url[15:]
        url += '/wapps/sso/login.html'

        ntry = 0
        while ntry < self.maxtries:
            ntry += 1
            s = requests.session()
            s.verify = False

            req1 = s.post(url,
                          data={'_flowId': 'legacy-login-flow', 'failureRedirect': url,
                                'username': self.login, 'password': self.password},
                          headers={'Accept-Language': 'en-US'})
            if req1.status_code != 200:
                continue
            if req1.content.find('Welcome&nbsp;' + self.login) == -1:
                # Accepting terms
                req2 = s.post(url, params={'_flowId': 'legacy-login-flow', '_flowExecutionKey': 'e1s1'},
                              data={'accepted': 'true', '_accepted': 'on', 'optionalTerms_28': 'accept', '_eventId_submit': 'Continue', '_flowExecutionKey': 'e1s1', 'redirect': ''})
                if req2.status_code != 200:
                    continue
                if req2.content.find('Open Source Assurance Agreement Acceptance Confirmation') != -1 or req2.content.find('Welcome&nbsp;' + self.login) == -1:
                    continue
            req3 = s.get(self.portal_url + "/management/" , verify=False, headers={'Accept-Language': 'en-US'})
            if req3.status_code == 200:
                break

        assert ntry < self.maxtries, "Failed to login to portal after %s tries" % self.maxtries
        return s

    def check_subscriptions(self, uid_list):
        """ Check subscription status """
        uid_set = set([str(uid) for uid in uid_list])
        self.con.ping()
        ntry = 0
        while True:
            try:
                owners = self.con.getOwnerList(self.login)
                logger.debug("Owners: %s" % owners)
                subscriptions = []
                for own in owners:
                    pools = self.con.getPoolsList(owner=own['key'])
                    for pool in pools:
                        subscriptions.append(pool['subscriptionId'])
                    logger.debug("Subscriptions: %s" % subscriptions)
                sub_set = set(subscriptions)
                if uid_set <= sub_set:
                    return "<Response [200]>"
                else:
                    logger.info("Can't find %s in subscriptions" % list(uid_set - sub_set))
            except Exception, e:
                # Let's try after login to the portal
                logger.debug("Error trying to check subs: %s" % e)
                if self.portal_url is not None:
                    session = self.portal_login()
                else:
                    pass
            ntry += 1
            if ntry > self.maxtries:
                return None

    def create_distributor(self, name, distributor_version='sam-1.3'):
        """ Create new distributor on portal"""
        self.con.ping()
        try:
            distributor = self.con.registerConsumer(name=name, type={'id': '5', 'label': 'sam', 'manifest': True}, facts={'distributor_version': distributor_version})
        except:
                # Let's try after login to the portal
                if self.portal_url is not None:
                    session = self.portal_login()
                    distributor = self.con.registerConsumer(name=name, type={'id': '5', 'label': 'sam', 'manifest': True}, facts={'distributor_version': distributor_version})
                else:
                    return None
        return distributor['uuid']

    def distributor_available_subscriptions(self, uuid, expected_subs_count=None):
        """ Get available/attached subscriptions """
        self.con.ping()
        ntry = 0
        while True:
            try:
                owners = self.con.getOwnerList(self.login)
                subscriptions = []
                for own in owners:
                    pools = self.con.getPoolsList(owner=own['key'])
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
                if expected_subs_count is None or len(subscriptions) >= expected_subs_count:
                    return subscriptions
            except:
                # Let's try login to the portal
                if self.portal_url is not None:
                    self.portal_login()
                else:
                    pass
            if ntry >= self.maxtries:
                return None
            ntry += 1

    def distributor_attached_subscriptions(self, uuid):
        """ Get available/attached subscriptions """
        self.con.ping()
        subscriptions = []
        ntry = 0
        entitlements = self.con.getEntitlementList(consumerId=uuid)
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

    def distributor_attach_everything(self, uuid, subs_count=1):
        """ Attach all available subscriptions to distributor """
        return self.distributor_attach_subscriptions(uuid, subs_count=subs_count, subscriptions=None)

    def distributor_attach_subscriptions(self, uuid, subs_count=1, subscriptions=None):
        """ Attach subscriptions to distributor """
        self.con.ping()
        if subscriptions is None:
            subscriptions = self.distributor_available_subscriptions(uuid, subs_count)
        assert subscriptions is not None and subscriptions != [], "Nothing to attach"
        assert len(subscriptions) >= subs_count, "Can't attach %s subscriptions" % subs_count
        for sub in subscriptions:
            try:
                bind = self.con.bindByEntitlementPool(uuid, sub['id'], sub['quantity'])
            except:
                # Let's try binding after login to the portal
                if self.portal_url is not None:
                    session = self.portal_login()
                    bind = self.con.bindByEntitlementPool(uuid, sub['id'], sub['quantity'])
                else:
                    bind = None
            assert bind is not None, "Failed to bind %s" % sub
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
        assert len(diff) == 0, "Can't detach subs: %s" % diff
        self.con.ping()
        for serial in detach_serials:
            self.con.unbindBySerial(uuid, serial)
        return "<Response [200]>"

    def distributor_download_manifest(self, uuid):
        """ Download manifest """
        session = self.portal_login()
        ntry = 0
        while ntry < self.maxtries:
            req1 = session.get(self.portal_url + "/management/distributors/%s/certificate/manifestdownload?" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
            if req1.status_code == 200:
                break
            ntry += 1
        assert req1.status_code == 200
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tf.write(req1.content)
        tf.close()
        return tf.name

    def distributor_get_uuid(self, name):
        """ Get distributor uuid """
        session = self.portal_login()
        req1 = session.get(self.portal_url + "/management/distributors", verify=False, headers={'Accept-Language': 'en-US'})
        assert req1.status_code == 200
        m = re.search("/distributors/([0-9,a-f,-]*)\">" + name + "<", req1.content, re.DOTALL)
        if m is not None:
            return m.group(1)
        else:
            return None

    def delete_distributor(self, uuid):
        """ Delete distributor """
        self.con.ping()
        try:
            self.con.unregisterConsumer(uuid)
        except:
            self.portal_login()
            self.con.unregisterConsumer(uuid)
        return "<Response [200]>"

    @staticmethod
    def _namify(name, row):
        try:
            return name % row
        except TypeError:
            return name

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

        try:
            sys = self.con.registerConsumer(name=sys_name, facts=facts, installed_products=installed_products, owner=org)
        except:
            # Let's try binding after login to the portal
            if self.portal_url is not None:
                session = self.portal_login()
                sys = self.con.registerConsumer(name=sys_name, facts=facts, installed_products=installed_products, owner=org)
            else:
                sys = None

        assert sys is not None, 'Failed to register systems %s' % sys_name

        logger.info("Sys %s created with uid %s" % (sys_name, sys['uuid']))
        if entitlement_dir is not None:
            try:
                fd = open(entitlement_dir + '/%s.json' % sys_name, 'w')
                fd.write(json.dumps(sys))
                fd.close()
            except:
                logger.error("Failed to write system data to %s" % entitlement_dir)

        return (sys_name, sys['uuid'])

    def _get_best_pool(self, pools, productId, is_virtual):
        if is_virtual:
            # searching for derived pool
            for pool in pools:
                if pool['productId'] == productId and (pool['consumed'] < pool['quantity'] or pool['quantity'] == -1) and pool['subscriptionSubKey'] == 'derived':
                    return pool['id']
        # searching for normal pool
        for pool in pools:
            if pool['productId'] == productId and (pool['consumed'] < pool['quantity'] or pool['quantity'] == -1):
                return pool['id']
        return None

    def create_systems(self, csv_file, entitlement_dir=None, org=None, subscribe=True, update=False):
        """
        Register a bunch of systems from CSV file

        # CSV: Name,Count,Org Label,Environment Label,Groups,Virtual,Host,OS,Arch,Sockets,RAM,Cores,SLA,Products,Subscriptions
        """
        all_systems = []
        host_systems = {}

        self.con.ping()

        data = csv.DictReader(open(csv_file))
        for row in data:
            num = 0
            total = int(row['Count'])
            while num < total:
                num += 1
                name = self._namify(row['Name'], num)
                cores = row['Cores']
                sockets = row['Sockets']
                memory = row['RAM']
                arch = row['Arch']
                if row['Virtual'] in ['Yes', 'Y', 'y']:
                    is_guest = True
                    virt_uuid = name
                else:
                    is_guest = False
                    virt_uuid = ''
                if row['OS'].find(' ') != -1:
                    dist_name, dist_version = row['OS'].split(' ')
                else:
                    dist_name, dist_version = ('RHEL', row['OS'])

                installed_products = []
                if row['Products']:
                    for product in row['Products'].split(','):
                        [product_number, product_name] = product.split('|')
                        installed_products.append({'productId': int(product_number), 'productName': product_name})

                subscriptions = []
                if row['Subscriptions']:
                    for sub in row['Subscriptions'].split(';'):
                        [sub_id, sub_name] = sub.split('|')
                        subscriptions.append({'productId': sub_id, 'productName': sub_name})

                (sys_name, sys_uid) = self._register_system(org, name, cores, sockets, memory, arch, dist_name, dist_version, installed_products, is_guest, virt_uuid, entitlement_dir)

                all_systems.append({'name': sys_name, 'uuid': sys_uid, 'subscriptions': subscriptions, 'is_guest': is_guest})

                if row['Host'] is not None:
                    host_name = self._namify(row['Host'], num)
                    if not host_name in host_systems:
                        for sys in all_systems:
                            if sys['name'] == host_name:
                                host_systems[host_name] = [sys['uuid']]
                    if host_name in host_systems:
                        host_systems[host_name].append(name)

        for host in host_systems:
            # setting host/guest allocation
            host_detail = host_systems[host]
            if len(host_detail) > 1:
                logger.debug("Setting host/guest allocation for %s, VMs: %s" % (host_detail[0], host_detail[1::]))
                self.con.updateConsumer(host_detail[0], guest_uuids=host_detail[1::])

        if subscribe:
            pools = []
            owners = self.con.getOwnerList(self.login)
            logger.debug("Owners: %s" % owners)
            for own in owners:
                own_pools = self.con.getPoolsList(owner=own['key'])
                pools += own_pools
            for sys in all_systems:
                existing_subs = []
                if update:
                    for ent in self.con.getEntitlementList(sys['uuid']):
                        existing_subs.append(ent['pool']['productId'])

                pools_for_sys = self.con.getPoolsList(consumer=sys['uuid'])
                if pools_for_sys == []:
                    # will try to use owner-wide pools
                    pools_for_sys = pools
                processed_subs = []
                for sub in sys['subscriptions']:
                    processed_subs.append(sub['productId'])
                    if not sub['productId'] in existing_subs:
                        # we need to attach sub
                        pool_id =  self._get_best_pool(pools_for_sys, sub['productId'], sys['is_guest'])
                        if pool_id is not None:
                            req = self.con.bindByEntitlementPool(sys['uuid'], pool_id)
                            if req is None:
                                logger.error('Failed to bind pool %s to system %s:%s' % (pool_id, sys['name'], sys['uuid']))
                            else:
                                logger.info('Successfully subscribed system %s:%s to pool %s' % (sys['name'], sys['uuid'], pool_id))
                        else:
                            logger.error('Failed to find appropriate pool for system %s:%s' % (sys['name'], sys['uuid']))
                if update:
                    for ent in self.con.getEntitlementList(sys['uuid']):
                        if not ent['pool']['productId'] in processed_subs:
                            # unbinding everything else
                            serial = ent['certificates'][0]['serial']['serial']
                            req = self.con.unbindBySerial(sys['uuid'], serial)

        return "<Response [200]>"


if __name__ == '__main__':

    PWLESS_ACTIONS = ['user_get',
                      'sku_add']
    DIST_ACTIONS = ['distributor_create',
                    'distributor_available_subscriptions',
                    'distributor_attached_subscriptions',
                    'distributor_add_subscriptions',
                    'distributor_detach_subscriptions',
                    'distributor_delete',
                    'distributor_get_manifest']
    ALL_ACTIONS = ['user_create'] + PWLESS_ACTIONS + DIST_ACTIONS + ['systems_register', 'subscriptions_check']

    argparser = argparse.ArgumentParser(description='Stage portal tool', epilog='vkuznets@redhat.com')

    argparser.add_argument('--action', required=True,
                           help='Requested action', choices=ALL_ACTIONS)
    argparser.add_argument('--login', required=True, help='User login')

    [args, ignored_args] = argparser.parse_known_args()

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
    if args.action == 'systems_register':
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        argparser.add_argument('--csv', required=True, help='CSV file with systems definition.')
        argparser.add_argument('--entitlement-dir', required=False, help='Save entitlement data to dir.')
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
        if portal is not None and args.password is not None:
            # Checking if subs appeared in candlepin
            res_check = sp.check_subscriptions(res)
            if res_check is None:
                res = None
    elif args.action in DIST_ACTIONS:
        # protect against 'you need to accept terms'
        if portal is not None:
            session = sp.portal_login()
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
        if portal is not None:
            session = sp.portal_login()
        res = sp.create_systems(args.csv, args.entitlement_dir)
    elif args.action == 'subscriptions_check':
        res = sp.check_subscriptions(args.sub_ids)
    else:
        sys.stderr.write('Unknown action: %s\n' % args.action)
        sys.exit(1)
    sys.stdout.write('%s\n' % res)
