from JumpScale import j

descr = """
This script executes installer commands on mangement pod
"""

category = "cloudbroker"
organization = "greenitglobe"
license = "bsd"
version = "1.0"
roles = ["controller"]
async = True

def action(cmd):
    mgt = j.remote.cuisine.connect("management", 2205)
    response = mgt.run("installer {}".format(cmd), warn_only=True)
    return dict(
        return_code=response.return_code, stdout=response.stdout, stderr=response
    )
