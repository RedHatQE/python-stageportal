Python library and cli to work with stage portal
================================================

Config file
-----------

/etc/stageportal.cfg:

```
[main]
api = http://api.example.com:8080/svcrest
portal = https://portal.example.com

[subman]
candlepin = https://candlepin.example.com

[rhn]
xmlrpc = https://xmlrpc.server.example.com.com/XMLRPC
```

Common CLI options:
-------------------

```
$stageportal --help
...
Stage portal tool

optional arguments:
  -h, --help            show this help message and exit
  --action {user_get,sku_add,distributor_create,distributor_available_subscriptions,distributor_attached_subscriptions,distributor_add_subscriptions,distributor_detach_subscriptions,distributor_delete,distributor_get_manifest,satellite_create,satellite_get_certificate,user_create,system_register,system_subscribe,systems_register,subscriptions_check,heal_org,systems_register_classic,get_rhnclassic_channels,get_cdn_content,get_pools}
                        Requested action
  --login LOGIN         User login
  --verbose             Verbose bode
  --debug               Debug bode
  --maxtries MAXTRIES   Maximum retries count
  --portal PORTAL       Portal access URL
  --api API             API url (forcreating customers and adding subs
  --candlepin CANDLEPIN
                        Candlepin URL
  --config CONFIG       Config file (defaults to /etc/stageportal.cfg)
  --xmlrpc XMLRPC       XMLRPC URL (for RHN)
```

CLI usage example
-----------------

Getting existent customer:
```
stageportal --action user_get --login oldcustomer01
```

Creating new customer:
```
stageportal --login samplecustomer01 --password changeme --action user_create
6391408
```

Adding SKUs to customer account:
```
stageportal --login samplecustomer01 --password changeme --action sku_add --sku-id SKUXXXX --sku-quantity 2 --sku-start-date 2014-01-01
2687709
```

Checking if SKUs were added (it takes some time to appear):
```
stageportal --login samplecustomer01 --password changeme --action subscriptions_check --sub-ids 2687709
<Response [200]>
```

Getting existent pools:
```
stageportal --login samplecustomer01 --password changeme --action get_pools
[{'EngIDs': [],
  'consumed': 1,
  'endDate': '2014-03-20T03:59:59.000+0000',
  'id': '8a99f98344d30fe10144d5f3cae929ad',
  'productId': 'SKU0001',
  'quantity': 1,
  'sourceStackId': None,
  'startDate': '2013-03-20T04:00:00.000+0000'},
 {'EngIDs': [],
  'consumed': 0,
  'endDate': '2014-03-20T03:59:59.000+0000',
  'id': '8a99f98344d30fe10144d5f3cb0029be',
  'productId': 'SKU0002',
  'quantity': 0,
  'sourceStackId': None,
  'startDate': '2013-03-20T04:00:00.000+0000'}]
```

Creating SAM distributor:
```
stageportal --login samplecustomer01 --password changeme --action distributor_create --distributor-name sam1
c2f87b08-69da-4ed4-9995-b7c5b225d453
```

Creating Satellite5 (Spacewalk) distributor:
```
stageportal --login samplecustomer01 --password changeme --action satellite_create --distributor-name sat1
2947b137-f29a-4b9d-938a-03e01ca76f1f
```
	
Listing subscriptions available for attaching to distributor:
```
stageportal --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_available_subscriptions --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453
[{'date_end': u'07/04/2014',
  'date_start': u'07/04/2013',
  'id': '8a99f9833fcdf2d0013ff1630d9255c3',
  'name': u'Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Up to 1 guest)',
  'quantity': '40'}]
```

Attaching subscription to distributor:
```
stageportal --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_add_subscriptions --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453 --sub-id 8a99f9833fcdf2d0013ff1630d9255c3 --sub-quantity 10
<Response [200]>
```

Attaching all available subscriptions to distributor:
```
stageportal --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_add_subscriptions --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453 --all
<Response [200]>
```

Listing subscriptions already attached to distributor:
```
stageportal --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_attached_subscriptions --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453
[{'date_end': u'07/26/2014',
  'id': '8a99f98340a67e350140bf6d81d17064',
  'name': u'Red Hat Directory Server (Replica)',
  'quantity': u'6'}]
```

Detaching subscriptions from distributor:
```
stageportal --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_detach_subscriptions --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453 --sub-ids 8a99f98340a67e350140bf6d92e77066
<Response [200]>
```

Downloading manifest (SAM distributor):
```
stageportal --login samplecustomer01 --password changeme --action distributor_get_manifest --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453
/tmp/tmpPivvXu.zip
```

Downloading certificate (Satellite5 distributor):
```
stageportal --login samplecustomer01 --password changeme --action satellite_get_certificate --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453
/tmp/tmpFkZGdj.xml
```
	
Removing distributor (works for both SAM and Satellite5):
```
stageportal --login samplecustomer01 --password changeme ---action distributor_delete --distributor-uuid c2f87b08-69da-4ed4-9995-b7c5b225d453
<Response [200]>
```

Registering 'fake' system:
```
# Physical host:
stageportal --login samplecustomer01 --password changeme --action system_register --system-name tsystem1 --system-cores 4 --system-sockets 2 --system-memory 1 --system-arch x86_64 --system-dist-name RHEL --system-dist-version 6.5 --system-products '69|Red Hat Enterprise Linux Server'
2014-03-19 15:46:32,943 INFO Sys tsystem1 created with uid 8f8aacda-64f5-4695-9022-88bce0589a24
<Response [200]>

# Virtual host:
stageportal --login samplecustomer01 --password changeme --action system_register --system-name tguest1 --system-cores 4 --system-sockets 2 --system-memory 1 --system-arch x86_64 --system-dist-name RHEL --system-dist-version 6.5 --system-products '69|Red Hat Enterprise Linux Server' --system-is-guest --system-host-uuid 8f8aacda-64f5-4695-9022-88bce0589a24 
2014-03-19 15:49:46,425 INFO Sys tguest1 created with uid a9ca9021-593f-4d56-a0a3-5fee52a17da8
<Response [200]>
```

Subscribing 'fake' system:
```
# Selecting pool automatically:
stageportal --login samplecustomer01 --password changeme --action system_subscribe --uuid 8f8aacda-64f5-4695-9022-88bce0589a24
<Response [200]>

# Selecting pool manually:
stageportal --login samplecustomer01 --password changeme --action system_subscribe --uuid a9ca9021-593f-4d56-a0a3-5fee52a17da8 --pool-id 8a99f98344d30fe10144dacb7a135d86
<Response [200]>
```

Bulk systems registration (with CSV file):
```
stageportal --login samplecustomer01 --password changeme --action systems_register --csv systems.csv
2013-09-30 15:57:40,108 INFO Sys one1 created with uid 9a921974-ded3-4839-8b6b-0fda3eb85b4e
2013-09-30 15:57:43,099 INFO Sys one2 created with uid 6fd4cee5-8be7-44ef-89fa-6874ef659c7
...
<Response [200]>

# CSV example:
Name,Count,Org Label,Environment Label,Groups,Virtual,Host,OS,Arch,Sockets,RAM,Cores,SLA,Products,Subscriptions
test_one%d,1,,,,N,,6Server,x86_64,1,4,,Standard,69|Red Hat Enterprise Linux Server,"RH0192098|Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Unlimited guests)"
test_one1.vm%d,1,,,,Y,test_one1,6Server,x86_64,1,4,,Standard,69|Red Hat Enterprise Linux Server,"RH0192098|Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Unlimited guests)"
```

Testing CDN access:
```
# Test-only mode:
stageportal --login samplecustomer01 --password changeme --action get_cdn_content --uuid a9ca9021-593f-4d56-a0a3-5fee52a17da8  --url https://cdn.example.com/path/Packages/package-1.0.0.el6.x86_64.rpm
<Response [200]>

# Saving CDN content:
stageportal --login samplecustomer01 --password changeme --action get_cdn_content --uuid a9ca9021-593f-4d56-a0a3-5fee52a17da8  --url https://cdn.example.com/path/Packages/package-1.0.0.el6.x86_64.rpm --save /tmp
/tmp/package-1.0.0.el6.x86_64.rpm downloaded
<Response [200]>
```

'Heal entire org':
```
stageportal --login samplecustomer01 --password changeme --action heal_org
{u'finishTime': None, u'targetType': u'owner', u'updated': u'2013-10-22T09:16:25.791+0000', u'group': u'async group', u'created': u'2013-10-22T09:16:25.791+0000', u'statusPath': u'/jobs/heal_entire_org_1a259d55-067a-4b7e-b19a-ddc56cd8d6b9', u'targetId': u'target_id', u'principalName': u'samplecustomer01', u'state': u'CREATED', u'result': None, u'startTime': None, u'id': u'heal_entire_org_1a259d55-067a-4b7e-b19a-ddc56cd8d6b9'}
```

Bulk systems registration with RHN Classic tooling (with CSV file):
```
stageportal --login samplecustomer01 --password changeme --action systems_register_classic --csv classic.csv
<Response [200]>

# CSV example:
Name,Count,Org Label,Virtual,Host,Release,Version,Arch,RAM,Cores,Base Channel,Child Channels
one%d,1,,No,,redhat-release-server,6Server,x86_64,2,8,rhel-x86_64-server-6,
one1.vm%d,1,,Yes,one1,redhat-release-server,6Server,x86_64,1,1,rhel-x86_64-server-6,rhel-x86_64-server-6-debuginfo
```

Getting available RHN Classic channels:
```
stageportal --login samplecustomer01 --password changeme --action get_rhnclassic_channels
{u'RHEL FasTrack': {u'Available Flex Guest': 100,
                    u'Available Regular': 100,
                    u'Consumed Flex Guest': 0,
                    u'Consumed Regular': 0,
                    u'Systems Subscribed': 0},
 u'RHEL FasTrack Debuginfo (v. 5)': {u'Available Flex Guest': 100,
                    u'Available Regular': 100,
                    u'Consumed Flex Guest': 0,
                    u'Consumed Regular': 0,
                    u'Systems Subscribed': 0}
         ...
```

Contact
-------
vkuznets at redhat.com
