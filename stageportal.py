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
from BeautifulSoup import BeautifulSoup

def get_user(login, api_url):
    """ Get portal user """

    url = "%s/user/v3/login=%s" % (api_url, login)

    user = requests.get(url).json()
    if len(user)>0:
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
            sys.stderr.write(req+"\n")
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
            "systemName":"genie"
            }
    return requests.post(
            url,
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
                    "addtEmails":"dev-null@redhat.com"
                    }
                },
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
                    "reason": {"id":"14"},
                    "subject": "",
                    "comments": "",
                    "completed": False,
                    "renew": False,
                    "entitlementStartDate": start_date,
                    "satelliteVersion": "",
                    "poNumber":"",
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
                    "replicatorAcctNumber":""
                    }
                }
                ]
            }

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
    assert ntry < maxtries
    return s

def check_subscription(uid, login, password, url, maxtries=20):
    """ Check subscription status """
    session = portal_login(login, password, url)
    assert session is not None
    ntry = 0
    while True:
        req1 = session.get(url + "/wapps/support/protected/details.html", params={'subscriptionId': uid}, verify=False, headers={'Accept-Language': 'en-US'})
        bs = BeautifulSoup(req1.content)
        try:
            if len(bs.findAll("table")[0].findAll("td")) > 0:
                return req1
        except:
            pass
        ntry += 1
        if ntry > maxtries:
            return None

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
        uuid = req3.request.path_url.replace("/management/distributors/","")
        # hackaround candlepin
        req4 = requests.put(candlepin_url + "/subscription/consumers/%s" % uuid,
                            data='{"facts":{"system.certificate_version":"3.2"}}',
                            headers={'Content-Type': 'application/json'},
                            verify=False, auth=(login, password))
        if req4.status_code != 204:
            continue
        return uuid
    assert ntry < maxtries

def distributor_attach_everything(uuid, login, password, url, maxtries=20):
    """ Attach all available subscriptions to distributor """
    ntry = 0
    while True:
        session = portal_login(login, password, url)
        req1 = session.get(url + "/management/distributors/%s" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
        assert req1.status_code == 200
        auth_token = re.search(".*name=\"authenticity_token\" type=\"hidden\" value=\"(.*=)\"", req1.content).group(1)
        subscriptions = []
        bs = BeautifulSoup(req1.content)
        for tag in bs.findAll('select'):
            subscriptions += re.findall("quantity\[([0-9,a-f]+)\]\">.*<option value=\"([0-9]+)\" selected", str(tag), re.DOTALL)
        if subscriptions != [] or ntry > maxtries:
            break
        ntry += 1
    assert subscriptions != [], "Nothing to attach"

    data = {"authenticity_token": auth_token,
            "stype": "match",
            "checkall_avail": 0,
            "checkgroup[]": [],
            "commit": "Attach Selected"
            }
    for sub, quantity in subscriptions:
        data["checkgroup[]"].append(sub)
        data["quantity[%s]" % sub] = quantity
    req2 = session.post(url + "/management/distributors/%s/bind/selected" % uuid, verify=False, headers={'Accept-Language': 'en-US'}, data=data)
    assert req2.status_code == 200
    return req2

def distributor_download_manifest(uuid, login, password, url):
    """ Download manifest """
    session = portal_login(login, password, url)
    req1 = session.get(url + "/management/distributors/%s/certificate/manifestdownload?" % uuid, verify=False, headers={'Accept-Language': 'en-US'})
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

    ACTIONS = ['user_create', 'distributor_create', 'distributor_add_subscriptions', 'distributor_delete', 'distributor_get_manifest']

    argparser = argparse.ArgumentParser(description='Stage portal tool')

    argparser.add_argument('--action', required=True,
            help='Requested action [%s]' % ", ".join(act for act in ACTIONS))
    argparser.add_argument('--login', required=True,
            help='User login')
    argparser.add_argument('--password',
            help='User password')
    argparser.add_argument('--sku-id', required=False, help='SKU id to add')
    argparser.add_argument('--sku-quantity', required=False, help='SKU quantity to add')
    argparser.add_argument('--sku-start-date', required=False, help='SKU start date')
    argparser.add_argument('--distributor-name', required=False, help='Distributor name')
    argparser.add_argument('--distributor-uuid', required=False, help='Distributor uuid')
    argparser.add_argument('--api', required=True, help='The URL to the stage portal\'s API.')
    argparser.add_argument('--portal', required=True, help='The URL to the stage portal.')
    argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')

    args = argparser.parse_args()
    if args.password is None and args.action in ACTIONS:
        sys.stderr.write('You should specify --password\n')
        sys.exit(1)

    if args.action == 'user_create':
        res = create_user(args.login, args.password, args.api)
    elif args.action == 'user_get':
        res = get_user(args.login, args.api)
    elif args.action=='sku_add':
        if args.sku_id is None or args.sku_quantity is None or args.sku_start_date is None:
            sys.stderr.write('You should specify --sku-id, --sku-quantity and --sku-start-date\n')
            sys.exit(1)
        res = hock_sku(args.login, args.sku_id, args.sku_quantity, args.sku_start_date, args.api)
    elif args.action=='distributor_create':
        if args.distributor_name is None:
            sys.stderr.write("You should specify --distributor-name\n")
            sys.exit(1)
        res = create_distributor(args.distributor_name, args.login, args.password, args.portal, args.candlepin)
    elif args.action in ['distributor_add_subscriptions', 'distributor_delete', 'distributor_get_manifest']:
        if args.distributor_name is None and args.distributor_uuid is None:
            sys.stderr.write('You should specify --distributor-name or --distributor-uuid\n')
            sys.exit(1)
        if args.distributor_uuid is None:
            distributor_uuid = distributor_get_uuid(args.distributor_name, args.login, args.password, args.portal)
        else:
            distributor_uuid = args.distributor_uuid
        if distributor_uuid is None:
            res = None
        elif args.action == 'distributor_add_subscriptions':
            res = distributor_attach_everything(distributor_uuid, args.login, args.password, args.portal)
        elif args.action == 'distributor_delete':
            res = delete_distributor(distributor_uuid, args.login, args.password, args.portal)
        elif args.action == 'distributor_get_manifest':
            res = distributor_download_manifest(distributor_uuid, args.login, args.password, args.portal)
    else:
        sys.stderr.write('Unknown action: %s\n' % args.action)
        sys.exit(1)
    sys.stdout.write('%s\n' % res)
