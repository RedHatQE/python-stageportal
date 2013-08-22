Python library and cli to work with stage portal
================================================

CLI usage example
-----------------
	$API=http://api.example.com:8080/svcrest
	$CANDLEPIN=https://candlepin.example.com
	$PORTAL=https://portal.example.com
	
	$python stageportal.py --login vkuztestent29 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action user_create
	6391408

	$python stageportal.py --login vkuztestent29 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action sku_add --sku-id SKUXXXX --sku-quantity 2 --sku-start-date 2012-08-01
	2687709

	$python stageportal.py --login vkuztestent29 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_create --distributor-name sam1
	c2f87b08-69da-4ed4-9995-b7c5b225d453
	
	$python stageportal.py --login vkuztestent29 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_add_subscriptions --distributor-name sam1
	<Response [200]>
	
	$python stageportal.py --login vkuztestent29 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_get_manifest --distributor-name sam1       
	/tmp/tmpPivvXu.zip
	
	$python stageportal.py --login vkuztestent29 --password changeme --api $API --portal $PORTAL --candlepin $CANDLEPIN --action distributor_delete --distributor-name sam1
	<Response [200]>

Contact
-------
vkuznets at redhat.com
