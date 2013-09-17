#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: ts=4 sw=4 expandtab ai

import requests
import json
import re
import tempfile
import argparse
import sys
import time
import pprint
from BeautifulSoup import BeautifulSoup


def get_user(login, api_url):
    """ Get portal user """

    url = "%s/user/v3/login=%s" % (api_url, login)

    user = requests.get(url).json()
    if len(user) > 0:
        return user[0]['customer']['id']
    else:
        return None


def create_user(login, password, api_url, maxtries=20):
    """ Create portal user """

    url = "%s/user/v3/create" % api_url

    newuser = {"login": login,
               "loginUppercase": login.upper(),
               "password": password,
               "system": "WEB",
               "userType": "P",
               "personalInfo": {"phoneNumber": "1234567890",
                                "email": "dev-null@redhat.com",
                                "firstName": login,
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
        if ntry > maxtries:
            break
    return id


def activate(regNumber, start_date, login, api_url):
    """ Activate regNumber """

    url = "%s/activation/v2/activate" % api_url

    webCustomerId = get_user(login, api_url)
    data = {"activationKey": regNumber,
            "vendor": "REDHAT",
            "startDate": start_date,
            "userName": login,
            "webCustomerId": webCustomerId,
            "systemName": "genie"
            }
    return requests.post(url,
                         headers={"Content-Type": 'application/json'},
                         data=json.dumps(data)).json()['id']


def hock_sku(login, SKU, quantity, start_date, api_url):
    """ Place an order """
    url = "%s/regnum/v5/hock/order" % api_url

    data = {"regnumType": "entitlement",
            "satelliteVersion": "",
            "login": login,
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
    return activate(regNumber, start_date, login, api_url)


def portal_login(login, password, url, maxtries=20):
    """ Perform portal login, accept terms if needed """

    if url.startswith("https://access."):
        url = "https://www." + url[15:]
    url += '/wapps/sso/login.html'

    ntry = 0
    while ntry < maxtries:
        ntry += 1
        s = requests.session()
        s.verify = False

        req1 = s.post(url,
                      data={'_flowId': 'legacy-login-flow', 'failureRedirect': url,
                            'username': login, 'password': password},
                      headers={'Accept-Language': 'en-US'})
        if req1.status_code != 200:
            continue
        if req1.content.find('Welcome&nbsp;' + login) == -1:
            # Accepting terms
            req2 = s.post(url, params={'_flowId': 'legacy-login-flow', '_flowExecutionKey': 'e1s1'},
                          data={'accepted': 'true', '_accepted': 'on', 'optionalTerms_28': 'accept', '_eventId_submit': 'Continue', '_flowExecutionKey': 'e1s1', 'redirect': ''})
            if req2.status_code != 200:
                continue
            if req2.content.find('Open Source Assurance Agreement Acceptance Confirmation') != -1 or req2.content.find('Welcome&nbsp;' + login) != -1:
                ntry = 0
                break
        else:
            break

    assert ntry < maxtries
    return s


def check_subscriptions(uid_list, login, password, url, maxtries=20):
    """ Check subscription status """
    session = portal_login(login, password, url)
    assert session is not None
    ntry = 0
    for uid in uid_list:
        while True:
            req1 = session.get(url + "/wapps/support/protected/details.html", params={'subscriptionId': uid}, verify=False, headers={'Accept-Language': 'en-US'})
            bs = BeautifulSoup(req1.content)
            try:
                if len(bs.findAll("table")[0].findAll("td")) > 0:
                    # subscription is present
                    break
            except:
                pass
            ntry += 1
            if ntry > maxtries:
                return None
    return True


def create_distributor(name, login, password, url, candlepin_url, maxtries=20):
    """ Create new distributor on portal"""
    ntry = 0
    while ntry < maxtries:
        ntry += 1
        session = portal_login(login, password, url)
        req1 = session.get(url + "/management/distributors/", verify=False, headers={'Accept-Language': 'en-US'})
        if req1.status_code != 200:
            continue
        req2 = session.get(url + "/management/distributor/distributors/create/sam", verify=False, headers={'Accept-Language': 'en-US'})
        if req2.status_code != 200:
            continue
        auth_token_search = re.search(".*name=\"authenticity_token\" type=\"hidden\" value=\"(.*=)\"", req2.content)
        if auth_token_search is not None:
            auth_token = auth_token_search.group(1)
        else:
            time.sleep(5)
            continue
        data = {"authenticity_token": auth_token,
                "distributor[consumer_type]": "sam", "distributor[name]": name,
                "commit": "Register",
                "asp_charset": "iso-8859-1"}
        req3 = session.post(url + "/management/distributor/distributors/create/sam", verify=False, headers={'Accept-Language': 'en-US'}, data=data)
        if req3.status_code != 200:
            continue
        # returning UUID
        uuid = req3.request.path_url.replace("/management/distributors/", "")
        # hackaround candlepin
        #req4 = requests.put(candlepin_url + "/subscription/consumers/%s" % uuid,
        #                    data='{"facts":{"system.certificate_version":"3.2"}}',
        #                    headers={'Content-Type': 'application/json'},
        #                    verify=False, auth=(login, password))
        #if req4.status_code != 204:
        #    continue
        req4 = requests.put(candlepin_url + "/subscription/consumers/%s" % uuid,
                            data='{"facts":{"distributor_version":"sam-1.3"}}',
                            headers={'Content-Type': 'application/json'},
                            verify=False, auth=(login, password))
        if req4.status_code != 204:
            continue
        #req5 = requests.put(candlepin_url + "/subscription/consumers/%s" % uuid,
        #                    data='{"capabilities":[{"name":"cores"},{"name":"ram"},{"name":"instance_multiplier"},{"name":"cert_v3"}]}',
        #                    headers={'Content-Type': 'application/json'},
        #                    verify=False, auth=(login, password))
        #if req5.status_code != 204:
        #    continue
        return uuid
    assert ntry < maxtries


def _distributor_auth_token(uuid, login, password, url):
    """ Get 'distributor' page content and auth token """
    session = portal_login(login, password, url)
    req = session.get(url + "/management/distributors/%s" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
    if req.status_code != 200:
        return None, None, None
    search = re.search(".*name=\"authenticity_token\" type=\"hidden\" value=\"(.*=)\"", req.content)
    if search is None:
        return None, None, None
    return session, req.content, search.group(1)


def distributor_available_subscriptions(uuid, login, password, url, maxtries=20, expected_subs_count=None):
    """ Get all attachable subs for distributor """
    ntry = 0
    subscriptions = []
    while True:
        if ntry > maxtries:
            # no more tries left
            break
        (_, content, auth_token) = _distributor_auth_token(uuid, login, password, url)
        if auth_token is None:
            ntry += 1
            continue
        subscriptions = []
        bs = BeautifulSoup(content)
        for tag in bs.findAll('tr'):
            if tag.findAll('select') != []:
                try:
                    (_id, quantity) = re.findall("quantity\[([0-9,a-f]+)\]\">.*<option value=\"([0-9]+)\" selected", str(tag.findAll('select')), re.DOTALL)[0]
                except IndexError:
                    continue
                name = None
                date1 = None
                date2 = None
                for td in tag.findAll('td'):
                    if str(td).find('"subscription"') != -1:
                        name = td.text
                    if str(td).find('"date"') != -1:
                        if date1 is None:
                            date1 = td.text
                        else:
                            date2 = td.text
                subscriptions.append({'id': _id,
                                      'name': name,
                                      'quantity': quantity,
                                      'date_start': date1, 'date_end': date2})
        if expected_subs_count is None or len(subscriptions) >= expected_subs_count:
            # all required subscriptions are found
            break
        ntry += 1
    return subscriptions


def distributor_attached_subscriptions(uuid, login, password, url, maxtries=20):
    """ Get all already attached subs for distributor """
    ntry = 0
    subscriptions = []
    while True:
        if ntry > maxtries:
            # no more tries left
            break
        (_, content, auth_token) = _distributor_auth_token(uuid, login, password, url)
        if auth_token is None:
            ntry += 1
            continue
        subscriptions = []
        bs = BeautifulSoup(content)
        for tag in bs.findAll('tr'):
            if tag.findAll('td', {'class': 'subscription'}) != [] and tag.findAll('option') == []:
                name = tag.findAll('td', {'class': 'subscription'})[0].getText()
                quantity = tag.findAll('td', {'class': 'quantity'})[1].getText()
                date = tag.findAll('td', {'class': 'date'})[0].getText()
                _id = re.findall('value="([0-9,a-f]*)"', str(tag.findAll('td', {'class': 'select'})[0]))[0]
                subscriptions.append({'id': _id,
                                      'name': name,
                                      'quantity': quantity,
                                      'date_end': date})
        break
    return subscriptions


def distributor_attach_everything(uuid, login, password, url, maxtries=20, subs_count=1):
    """ Attach all available subscriptions to distributor """
    return distributor_attach_subscriptions(uuid, login, password, url, maxtries=20, subs_count=subs_count, subscriptions=None)


def distributor_attach_subscriptions(uuid, login, password, url, maxtries=20, subs_count=1, subscriptions=None):
    """ Attach subscriptions to distributor """
    if subscriptions is None:
        subscriptions = distributor_available_subscriptions(uuid, login, password, url, maxtries, subs_count)
    assert subscriptions != [], "Nothing to attach"
    assert len(subscriptions) >= subs_count, "Can't attach %s subscriptions" % subs_count

    ntry = 0
    req = None
    while ntry < maxtries:
        if ntry > maxtries:
            # no more tries left
            break

        (session, _, auth_token) = _distributor_auth_token(uuid, login, password, url)
        if auth_token is None:
            ntry += 1
            continue

        data = {"authenticity_token": auth_token,
                "stype": "match",
                "checkall_avail": 0,
                "checkgroup[]": [],
                "commit": "Attach Selected"}
        for sub in subscriptions:
            data["checkgroup[]"].append(sub['id'])
            data["quantity[%s]" % sub['id']] = sub['quantity']
        req = session.post(url + "/management/distributors/%s/bind/selected" % uuid, verify=False, headers={'Accept-Language': 'en-US'}, data=data)
        if req.status_code != 200:
            ntry += 1
            continue
        else:
            break
    return req


def distributor_detach_subscriptions(uuid, login, password, url, maxtries=20, subscriptions=None):
    """ Detach subscriptions from distributor """
    ntry = 0
    req = None
    while ntry < maxtries:
        if ntry > maxtries:
            # no more tries left
            break

        (session, _, auth_token) = _distributor_auth_token(uuid, login, password, url)
        if auth_token is None:
            ntry += 1
            continue

        data = {"authenticity_token": auth_token,
                "stype": "match",
                "checkgroup[]": [],
                "commit": "Attach Selected"}
        for sub in subscriptions:
            data["checkgroup[]"].append(sub)
        req = session.post(url + "/management/distributors/%s/unbind/selected" % uuid, verify=False, headers={'Accept-Language': 'en-US'}, data=data)
        if req.status_code != 200:
            ntry += 1
            continue
        else:
            break
    return req


def distributor_download_manifest(uuid, login, password, url, maxtries=20):
    """ Download manifest """
    session = portal_login(login, password, url)
    ntry = 0
    while ntry < maxtries:
        req1 = session.get(url + "/management/distributors/%s/certificate/manifestdownload?" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
        if req1.status_code == 200:
            break
        ntry += 1
    assert req1.status_code == 200
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tf.write(req1.content)
    tf.close()
    return tf.name


def distributor_get_uuid(name, login, password, url):
    """ Get distributor uuid """
    session = portal_login(login, password, url)
    req1 = session.get(url + "/management/distributors", verify=False, headers={'Accept-Language': 'en-US'})
    assert req1.status_code == 200
    m = re.search("/distributors/([0-9,a-f,-]*)\">" + name + "<", req1.content, re.DOTALL)
    if m is not None:
        return m.group(1)
    else:
        return None


def delete_distributor(uuid, login, password, url):
    """ Delete distributor """
    session = portal_login(login, password, url)
    req1 = session.get(url + "/management/distributors/%s" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
    assert req1.status_code == 200
    auth_token = re.search(".*name=\"authenticity_token\" type=\"hidden\" value=\"(.*=)\"", req1.content).group(1)
    data = {"authenticity_token": auth_token,
            "_method": "delete"}
    req2 = session.post(url + "/management/distributors/%s/delete" % uuid, verify=False, headers={'Accept-Language': 'en-US'}, data=data)
    assert req2.status_code == 200
    return req2

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
    ALL_ACTIONS = ['user_create'] + PWLESS_ACTIONS + DIST_ACTIONS

    argparser = argparse.ArgumentParser(description='Stage portal tool', epilog='vkuznets@redhat.com')

    argparser.add_argument('--action', required=True,
                           help='Requested action', choices=ALL_ACTIONS)
    argparser.add_argument('--api', required=True, help='The URL to the stage portal\'s API.')
    argparser.add_argument('--portal', required=True, help='The URL to the stage portal.')
    argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')

    [args, ignored_args] = argparser.parse_known_args()

    argparser.add_argument('--login', required=True, help='User login')

    if not args.action in PWLESS_ACTIONS:
        argparser.add_argument('--password', required=True, help='User password')

    if args.action == 'sku_add':
        argparser.add_argument('--sku-id', required=True, help='SKU id to add')
        argparser.add_argument('--sku-quantity', required=True, help='SKU quantity to add')
        argparser.add_argument('--sku-start-date', required=True, help='SKU start date')

    if args.action == 'distributor_create':
        argparser.add_argument('--distributor-name', required=True, help='Distributor name')
    elif args.action in DIST_ACTIONS:
        argparser.add_argument('--distributor-name', required=False, help='Distributor name')
        argparser.add_argument('--distributor-uuid', required=False, help='Distributor uuid')

    if args.action == 'distributor_add_subscriptions':
        argparser.add_argument('--all', required=False, action='store_true', default=False, help='attach all available subscriptions')
        argparser.add_argument('--sub-id', required=False, help='sub id to attach to distributor')
        argparser.add_argument('--sub-quantity', required=False, help='sub quantity to attach to distributor')

    if args.action == 'distributor_detach_subscriptions':
        argparser.add_argument('--sub-ids', required=True, nargs='+', help='sub ids to detach from distributor (space separated list)')

    [args, ignored_args] = argparser.parse_known_args()

    if args.action == 'distributor_add_subscriptions' and args.all is False and (args.sub_id is None or args.sub_quantity is None):
        sys.stderr.write('You should specify --sub-id and --sub-quantity to attach specified subscription or use --all to attach all available subscriptions\n')
        sys.exit(1)

    if args.action == 'user_create':
        res = create_user(args.login, args.password, args.api)
    elif args.action == 'user_get':
        res = get_user(args.login, args.api)
    elif args.action == 'sku_add':
        res = hock_sku(args.login, args.sku_id, args.sku_quantity, args.sku_start_date, args.api)
    elif args.action == 'distributor_create':
        res = create_distributor(args.distributor_name, args.login, args.password, args.portal, args.candlepin)
    elif args.action in DIST_ACTIONS:
        if args.distributor_name is None and args.distributor_uuid is None:
            sys.stderr.write('You should specify --distributor-name or --distributor-uuid\n')
            sys.exit(1)
        if args.distributor_uuid is None:
            distributor_uuid = distributor_get_uuid(args.distributor_name, args.login, args.password, args.portal)
        else:
            distributor_uuid = args.distributor_uuid
        if distributor_uuid is None:
            res = None
        elif args.action == 'distributor_available_subscriptions':
            subs = distributor_available_subscriptions(distributor_uuid, args.login, args.password, args.portal)
            res = pprint.pformat(subs)
        elif args.action == 'distributor_attached_subscriptions':
            subs = distributor_attached_subscriptions(distributor_uuid, args.login, args.password, args.portal)
            res = pprint.pformat(subs)
        elif args.action == 'distributor_add_subscriptions':
            if args.all:
                res = distributor_attach_everything(distributor_uuid, args.login, args.password, args.portal)
            else:
                res = distributor_attach_subscriptions(distributor_uuid, args.login, args.password, args.portal, subscriptions=[{'id': args.sub_id, 'quantity': args.sub_quantity}])
        elif args.action == 'distributor_detach_subscriptions':
            res = distributor_detach_subscriptions(distributor_uuid, args.login, args.password, args.portal, subscriptions=args.sub_ids)
        elif args.action == 'distributor_delete':
            res = delete_distributor(distributor_uuid, args.login, args.password, args.portal)
        elif args.action == 'distributor_get_manifest':
            res = distributor_download_manifest(distributor_uuid, args.login, args.password, args.portal)
    else:
        sys.stderr.write('Unknown action: %s\n' % args.action)
        sys.exit(1)
    sys.stdout.write('%s\n' % res)
