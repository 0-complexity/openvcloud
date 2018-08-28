#!/usr/local/bin/jspython

from JumpScale import j
import ConfigParser
import time
from argparse import ArgumentParser
import re
import sys


parser = ArgumentParser()
parser.add_argument(
    "-u",
    "--users",
    dest="users_list",
    action="store",
    default=[],
    help="Provide the list of users you don't want to delete. Example: --users gig admin",
    nargs="+",
)
parser.add_argument(
    "-a",
    "--accounts",
    dest="accounts_list",
    action="store",
    default=[],
    help="Provide the list of accountss you don't want to delete. Example: --accounts gig test_deployment",
    nargs="+",
)
parser.add_argument(
    "-c",
    "--clean",
    dest="clean",
    action="store_true",
    help="clean all the environment",
    default=False,
)
options = parser.parse_args()

ccl = j.clients.osis.getNamespace("cloudbroker")
pcl = j.clients.portal.getByInstance("main")
scl = j.clients.osis.getNamespace("system")


def delete_accounts(accounts, options):
    for account in accounts:
        if account["name"] not in options.accounts_list:
            if account["name"] not in ["test_deployment", "gig"]:
                print("   |--Deleting account: %s" % account["name"])
                pcl.actors.cloudbroker.account.delete(account["id"], reason="testing")
                for _ in xrange(600):
                    if account["status"] == "DESTROYED":
                        break
                    account = ccl.account.search(
                        {"name": "%s" % account["name"], "id": account["id"]}
                    )[1]
                    time.sleep(1)


def clean_destroyed_resources(resource):
    destroyed_res = resource.search({"status": "DESTROYED"})
    for res in destroyed_res:
        if type(res) == int:
            continue
        else:
            resource.delete(res["id"])


users_list = []
if options.clean:
    clean_destroyed_resources(ccl.account)
    clean_destroyed_resources(ccl.cloudspace)
    clean_destroyed_resources(ccl.vmachine)

    # if accounts with no users have been found make sure to delete them
    Nouser_accounts = ccl.account.search(
        {"status": "CONFIRMED", "acl.userGroupId": ""}
    )[1:]
    if Nouser_accounts:
        delete_accounts(Nouser_accounts, options)
    hanging_accounts = ccl.account.search({"status": "DESTROYING"})[1:]
    if hanging_accounts:
        delete_accounts(hanging_accounts, options)
    list = scl.user.list()
    for user in list:
        match = re.search("_([\S]+)", user)
        users_list.append(match.group(1))
elif len(sys.argv) == 2 and sys.argv[1] != "--clean":
    USERNAME = sys.argv[1]
    users_list.append(USERNAME)
else:
    config = ConfigParser.ConfigParser()
    config.read("Perf_parameters.cfg")
    USERNAME = config.get("perf_parameters", "username")
    users_list.append(USERNAME)
print("Start tearing Down...")

for user in users_list:
    match = re.search(r"\S*DELETE\S*", user)
    user_accounts = ccl.account.search(
        {"status": "CONFIRMED", "acl.userGroupId": user}
    )[1:]
    if user_accounts:
        print("  Deleting accounts for user: %s" % user)
        delete_accounts(user_accounts, options)
    if user not in options.users_list:
        if user not in ["gig", "admin"]:
            if not match:
                print("  Deleting user: %s" % user)
                scl.user.delete(user)

print("Tearing Down is done")
