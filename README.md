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

	# Creating distributor
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_create --distributor-name sam1
	c2f87b08-69da-4ed4-9995-b7c5b225d453
	
	# Listing subscriptions available for attaching to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --candlepin $CANDLEPIN --portal $PORTAL --action distributor_available_subscriptions --distributor-name sam1
	 [{'date_end': u'07/04/2014',
           'date_start': u'07/04/2013',
           'id': '8a99f9833fcdf2d0013ff1630d9255c3',
           'name': u'Red Hat Enterprise Linux Server, Standard (1-2 sockets) (Up to 1 guest)',
           'quantity': '40'}]

	# Attaching subscription to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --candlepin $CANDLEPIN --portal $PORTAL --action distributor_add_subscriptions --distributor-name sam1 --sub-id 8a99f9833fcdf2d0013ff1630d9255c3 --sub-quantity 10
	<Response [200]>

	OR

	# Attaching all available subscriptions to distributor
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --candlepin $CANDLEPIN --portal $PORTAL --action distributor_add_subscriptions --distributor-name sam1 --all
	<Response [200]>

	# Downloading manifest
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_get_manifest --distributor-name sam1       
	/tmp/tmpPivvXu.zip
	
	# Removing distributor
	$python stageportal.py --login samplecustomer01 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_delete --distributor-name sam1
	<Response [200]>

Contact
-------
vkuznets at redhat.com
