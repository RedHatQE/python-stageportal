""" Stageportal CLI """

import argparse
import logging
import sys
import pprint


def main():
    ''' Main '''
    lformat = '%(asctime)s %(levelname)s %(message)s'
    logging.basicConfig(format=lformat)
    logging.getLogger("python-stageportal").setLevel(logging.INFO)

    pwless_actions = ['user_get',
                      'sku_add']
    dist_actions = ['distributor_create',
                    'distributor_available_subscriptions',
                    'distributor_attached_subscriptions',
                    'distributor_add_subscriptions',
                    'distributor_detach_subscriptions',
                    'distributor_delete',
                    'distributor_get_manifest',
                    'satellite_create',
                    'satellite_get_certificate']
    other_actions = ['user_create',
                     'systems_register',
                     'subscriptions_check',
                     'heal_org',
                     'systems_register_classic',
                     'get_rhnclassic_channels',
                     'get_cdn_content']

    all_actions = pwless_actions + dist_actions + other_actions

    argparser = argparse.ArgumentParser(description='Stage portal tool', epilog='vkuznets@redhat.com')

    argparser.add_argument('--action', required=True,
                           help='Requested action', choices=all_actions)
    argparser.add_argument('--login', required=True, help='User login')
    argparser.add_argument('--verbose', default=False, action='store_true', help="Verbose bode")
    argparser.add_argument('--maxtries', type=int, default=20, help="Maximum retries count")

    [args, _] = argparser.parse_known_args()

    if args.verbose:
        logging.getLogger("python-stageportal").setLevel(logging.DEBUG)

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
    if args.action in dist_actions:
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        if args.action in ['distributor_create', 'satellite_create']:
            argparser.add_argument('--distributor-name', required=True, help='Distributor name')
        else:
            argparser.add_argument('--distributor-uuid', required=True, help='Distributor uuid')

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
    if args.action == 'systems_register_classic':
        argparser.add_argument('--xmlrpc', required=True, help='XMLRPC URL')
        argparser.add_argument('--csv', required=True, help='CSV file with systems definition.')
        argparser.add_argument('--org', required=False, help='Create systems within org (standalone Satellite).')
    if args.action == 'get_rhnclassic_channels':
        argparser.add_argument('--xmlrpc', required=True, help='XMLRPC URL')
        argparser.add_argument('--with-labels', default=False, action='store_true', help="Include channel labels (slow)")
        argparser.add_argument('--satellite', default=False, action='store_true', help="We're connecting to Satellite, not RHN Hosted")
    if args.action == 'get_cdn_content':
        argparser.add_argument('--candlepin', required=True, help='The URL to the stage portal\'s Candlepin.')
        argparser.add_argument('--url', required=True, help='CDN url')
        argparser.add_argument('--uuid', required=True, help='Consumer UUID')
        argparser.add_argument('--save', required=False, help='Save file to specified location')

    if not args.action in pwless_actions:
        password_required = True
    else:
        password_required = False
    argparser.add_argument('--password', required=password_required, help='User password')

    [args, _] = argparser.parse_known_args()

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

    if 'xmlrpc' in args:
        xmlrpc = args.xmlrpc
    else:
        xmlrpc = None

    if args.action in ['systems_register_classic', 'get_rhnclassic_channels']:
        from rhnclassic import RhnClassicPortal
        portal = RhnClassicPortal(xmlrpc_url=xmlrpc, portal_url=portal, login=args.login, password=args.password, maxtries=args.maxtries)
    else:
        from smportal import SMPortal
        portal = SMPortal(api_url=api, candlepin_url=candlepin, portal_url=portal, login=args.login, password=args.password, maxtries=args.maxtries)

    if args.action == 'user_create':
        res = portal.create_user()
    elif args.action == 'user_get':
        res = portal.get_user()
    elif args.action == 'sku_add':
        if args.csv is None:
            res = [portal.hock_sku(args.sku_id, args.sku_quantity, args.sku_start_date)]
        else:
            res = portal.add_skus_csv(args.csv)
        if portal is not None and args.password is not None and not (None in res):
            # Checking if subs appeared in candlepin
            res_check = portal.check_subscriptions(res)
            if res_check is None:
                res = None
    elif args.action in dist_actions:
        res = None
        if args.action == 'distributor_create':
            res = portal.create_distributor(args.distributor_name)
        elif args.action == 'satellite_create':
            res = portal.create_satellite(args.distributor_name)
        else:
            distributor_uuid = args.distributor_uuid
        if res is None and distributor_uuid is None:
            pass
        elif args.action == 'distributor_available_subscriptions':
            subs = portal.distributor_available_subscriptions(distributor_uuid)
            res = pprint.pformat(subs)
        elif args.action == 'distributor_attached_subscriptions':
            subs = portal.distributor_attached_subscriptions(distributor_uuid)
            res = pprint.pformat(subs)
        elif args.action == 'distributor_add_subscriptions':
            if args.all:
                res = portal.distributor_attach_everything(distributor_uuid)
            else:
                res = portal.distributor_attach_subscriptions(distributor_uuid, subscriptions=[{'id': args.sub_id, 'quantity': args.sub_quantity}])
        elif args.action == 'distributor_detach_subscriptions':
            res = portal.distributor_detach_subscriptions(distributor_uuid, subscriptions=args.sub_ids)
        elif args.action == 'distributor_delete':
            res = portal.delete_distributor(distributor_uuid)
        elif args.action == 'distributor_get_manifest':
            res = portal.distributor_download_manifest(distributor_uuid)
        elif args.action == 'satellite_get_certificate':
            res = portal.satellite_download_cert(distributor_uuid)
    elif args.action == 'systems_register':
        res = portal.create_systems(args.csv, args.entitlement_dir, args.org)
        if res is not None:
            res = "<Response [200]>"
    elif args.action == 'systems_register_classic':
        res = portal.create_systems(args.csv, args.org)
        if res is not None:
            res = "<Response [200]>"
    elif args.action == 'get_rhnclassic_channels':
        res = portal.get_entitlements_list(hosted=(not args.satellite), get_labels=args.with_labels)
        res = pprint.pformat(res)
    elif args.action == 'subscriptions_check':
        res = portal.check_subscriptions(args.sub_ids)
    elif args.action == 'heal_org':
        res = portal.heal_entire_org()
    elif args.action == 'get_cdn_content':
        res = portal.cdn_get_file(args.uuid, args.url)
        if res is not None and res.status_code == 200 and args.save is not None:
            fname = args.save + '/' + args.url.split('/')[-1]
            with open(fname, 'w') as fd:
                fd.write(res.content)
                sys.stdout.write('%s downloaded\n' % fname)
    else:
        sys.stderr.write('Unknown action: %s\n' % args.action)
        sys.exit(1)
    sys.stdout.write('%s\n' % res)
    if res in [[], None]:
        sys.exit(1)

if __name__ == '__main__':
    main()
