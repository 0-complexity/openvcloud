
from JumpScale import j
from JumpScale import grid

import whmcsusers
import whmcsorders
from settings import CLOUDSPACE_PRODUCT_ID

def add_cloudspace(userId, cloudspace):
    print "Adding cloudspace: %s" % cloudspace
    whmcsorders.add_order(userId, CLOUDSPACE_PRODUCT_ID, cloudspace['name'], cloudspace['id'])

def main():
    cb = j.core.osis.getClientForNamespace('cloudbroker')
    system = j.core.osis.getClientForNamespace('system')
    
    accounts = cb.account.list()
    users = whmcsusers.list_users()
    
    for i in accounts:
        acc = cb.account.get(i)
        linked_users = system.user.simpleSearch({'id':acc.name})
        if len(linked_users) != 1:
            continue
        linked_user = linked_users[0]
        linked_groups = system.group.simpleSearch({'id':acc.name})
        if len(linked_groups) != 1:
            continue
        print linked_user
        password = ''
        if 'passwd' in linked_user:
            password =linked_user['passwd']
        if not acc.name in users.keys():
            continue
        
        cloudspaces = cb.cloudspace.simpleSearch({'accountId':acc.id})
        for cloudspace in cloudspaces:
            add_cloudspace(users[acc.name]['id'], cloudspace)


if __name__ == "__main__":
    main()
    