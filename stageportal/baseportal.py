#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import logging
import csv
import requests
import json
import time
import datetime


class BasePortalException(Exception):
    pass


class BasePortal(object):
    api_url = "http://example.com/svcrest"

    def __init__(self, login='admin', password='admin', maxtries=40, insecure=None, api_url=None):
        self.logger = logging.getLogger("python-stageportal")
        self.maxtries = maxtries
        self.insecure = insecure
        self.login = login
        self.password = password
        if api_url is not None:
            self.api_url = api_url

    @staticmethod
    def _namify(name, row):
        try:
            return name % row
        except TypeError:
            return name

    def _retr(self, func, check, sleep, blow_up, heal_func, *args, **kwargs):
        res = None
        ntry = 0
        self.logger.debug("Performing %s with args: %s kwargs %s" % (func, args, kwargs))
        while ntry < self.maxtries:
            exc_message = None
            res = None
            try:
                res = func(*args, **kwargs)
            except Exception, e:
                exc_message = "Exception during %s execution: %s" % (func, e)
                self.logger.debug(exc_message)
            try:
                self.logger.debug("Checking %s after %s" % (res, func))
                if check(res):
                    self.logger.debug("Checking: passed")
                    break
                else:
                    self.logger.debug("Checking: failed")
            except Exception, e:
                exc_message = "Checking: exception: %s" % e
                self.logger.debug(exc_message)
            if heal_func is not None:
                self.logger.debug("Doing heal func %s" % heal_func)
                heal_func()
            ntry += 1
            time.sleep(sleep)
        if ntry >= self.maxtries:
            if res is not None:
                self.logger.error("%s (args: %s, kwargs %s) failed after %s tries, last result: %s" % (func, args, kwargs, self.maxtries, res))
            elif exc_message is not None:
                self.logger.error("%s (args: %s, kwargs %s) failed after %s tries, last exception: %s" % (func, args, kwargs, self.maxtries, exc_message))
            else:
                self.logger.error("%s (args: %s, kwargs %s) failed after %s tries" % (func, args, kwargs, self.maxtries))

            if blow_up is True:
                raise BasePortalException("%s failed after %s tries, last result: %s" % (func, self.maxtries, res))
            else:
                res = None
        return res

    def get_user(self):
        """ Get portal user """

        url = "%s/user/v3/login=%s" % (self.api_url, self.login)
        user = self._retr(requests.get, lambda res: res.json()[0]['customer']['id'] is not None, 1, True, None, url)
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
        return self._retr(requests.post, lambda res: int(res.content) is not None, 1, True, None, url, headers={"Content-Type": 'application/json'}, data=json.dumps(newuser)).content

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
        req = self._retr(requests.post, lambda res: res.json()['id'] is not None, 1, True, None, url, headers={"Content-Type": 'application/json'}, data=json.dumps(data))
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

        order = self._retr(requests.put, lambda res: 'regNumbers' in res.json(), 1, True, None, url, headers={"Content-Type": 'application/json'}, data=json.dumps(data))
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
