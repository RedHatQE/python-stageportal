Python library and cli to work with stage portal
================================================

CLI usage example
-----------------

	$API=http://api.example.com:8080/svcrest
	$CANDLEPIN=https://candlepin.example.com
	$PORTAL=https://portal.example.com
	
	# Creating new customer
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action user_create
	6391408

	# Adding SKUs to customer account
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action sku_add --sku-id SKUXXXX --sku-quantity 2 --sku-start-date 2012-08-01
	2687709

	# Checking if SKUs were added (it takes some time to appear)
	$python stageportal.py --login samplecustomer01 --password changeme --portal $PORTAL --candlepin $CANDLEPIN --action subscriptions_check --sub-ids 2687709
	<Response [200]>

	# Creating SAM distributor
	$python stageportal.py --login samplecustomer01 --password changeme --portal $PORTAL --candlepin $CANDLEPIN --action distributor_create --distributor-name sam1
	c2f87b08-69da-4ed4-9995-b7c5b225d453

	# Creating Satellite5 (Spacewalk) distributor
	$python stageportal.py --login samplecustomer01 --password changeme --portal $PORTAL --candlepin $CANDLEPIN --action satellite_create --distributor-name sam1
	2947b137-f29a-4b9d-938a-03e01ca76f1f
	
	# Listing subscriptions available for attaching to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_available_subscriptions --distributor-name sam1
	 [{'date_end': u'07/04/2014',
           'date_start': u'07/04/2013',
           'id': '8a99f9833fcdf2d0013ff1630d9255c3',
           'name': u'Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Up to 1 guest)',
           'quantity': '40'}]

	# Attaching subscription to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_add_subscriptions --distributor-name sam1 --sub-id 8a99f9833fcdf2d0013ff1630d9255c3 --sub-quantity 10
	<Response [200]>

	OR

	# Attaching all available subscriptions to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_add_subscriptions --distributor-name sam1 --all
	<Response [200]>

	# Listing subscriptions already attached to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_attached_subscriptions --distributor-name sam1
	[{'date_end': u'07/26/2014',
          'id': '8a99f98340a67e350140bf6d81d17064',
          'name': u'Red Hat Directory Server (Replica)',
          'quantity': u'6'}]

	# Detaching subscriptions from distributor
	$python stageportal.py --login samplecustomer01 --password changeme --candlepin $CANDLEPIN --portal $PORTAL --action distributor_detach_subscriptions --distributor-name sam1 --sub-ids 8a99f98340a67e350140bf6d92e77066
	<Response [200]>

	# Downloading manifest (SAM distributor)
	$python stageportal.py --login samplecustomer01 --password changeme --portal $PORTAL --candlepin $CANDLEPIN --action distributor_get_manifest --distributor-name sam1
	/tmp/tmpPivvXu.zip

	# Downloading certificate (Satellite5 distributor)
	$python stageportal.py --login samplecustomer01 --password changeme --portal $PORTAL --candlepin $CANDLEPIN --action satellite_get_certificate --distributor-name sam1
	/tmp/tmpFkZGdj.xml
	
	# Removing distributor
	$python stageportal.py --login samplecustomer01 --password changeme ---portal $PORTAL --candlepin $CANDLEPIN --action distributor_delete --distributor-name sam1
	<Response [200]>

	# Registering systems
	$python stageportal.py --login samplecustomer01 --password changeme --portal $PORTAL --candlepin $CANDLEPIN --action systems_register --csv systems.csv --entitlement-dir /tmp/entitlements
	2013-09-30 15:57:40,108 INFO Sys one1 created with uid 9a921974-ded3-4839-8b6b-0fda3eb85b4e
        2013-09-30 15:57:43,099 INFO Sys one2 created with uid 6fd4cee5-8be7-44ef-89fa-6874ef659c7
	...
	<Response [200]>
	# CSV example:
	Name,Count,Org Label,Environment Label,Groups,Virtual,Host,OS,Arch,Sockets,RAM,Cores,SLA,Products,Subscriptions
	test_one%d,1,,,,N,,6Server,x86_64,1,4,,Standard,69|Red Hat Enterprise Linux Server,"RH0192098|Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Unlimited guests)"
	test_one1.vm%d,1,,,,Y,test_one1,6Server,x86_64,1,4,,Standard,69|Red Hat Enterprise Linux Server,"RH0192098|Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Unlimited guests)"

	#Heal entire org job
	$python stageportal.py --login samplecustomer01 --password changeme ---portal $PORTAL --candlepin $CANDLEPIN --action heal_org
	{u'finishTime': None, u'targetType': u'owner', u'updated': u'2013-10-22T09:16:25.791+0000', u'group': u'async group', u'created': u'2013-10-22T09:16:25.791+0000', u'statusPath': u'/jobs/heal_entire_org_1a259d55-067a-4b7e-b19a-ddc56cd8d6b9', u'targetId': u'target_id', u'principalName': u'samplecustomer01', u'state': u'CREATED', u'result': None, u'startTime': None, u'id': u'heal_entire_org_1a259d55-067a-4b7e-b19a-ddc56cd8d6b9'}

	# Registering systems to RHN Classic
	$XMLRPC=https://xmlrpc.server.example.com.com/XMLRPC
	$python stageportal.py --login samplecustomer01 --password changeme --xmlrpc $XMLRPC --action systems_register_classic --csv classic.csv
	# CSV example:
	Name,Count,Org Label,Virtual,Host,Release,Version,Arch,RAM,Cores,Base Channel,Child Channels
	one%d,1,,No,,redhat-release-server,6Server,x86_64,2,8,rhel-x86_64-server-6,
	one1.vm%d,1,,Yes,one1,redhat-release-server,6Server,x86_64,1,1,rhel-x86_64-server-6,rhel-x86_64-server-6-debuginfo

Contact
-------
vkuznets at redhat.com
