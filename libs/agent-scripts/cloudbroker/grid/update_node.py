from JumpScale import j
from urlparse import urlparse

descr = """
This script updates nodes version
"""

category = "cloudbroker"
organization = "greenitglobe"
license = "bsd"
version = "1.0"
roles = []
async = True


def action(nodename):
    try:
        mgt = j.remote.cuisine.connect('management', 2205)
        mgt.run("installer node jsaction upgrade --name {}".format(nodename))
    except:
        j.errorconditionhandler.raiseOperationalWarning(
            "Can't update node {}".format(nodename)
        )
