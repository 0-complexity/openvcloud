try:
    import ujson as json
except Exception:
    import json
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import resourcestatus


def generateUsersList(sclient, objdict, accessUserType, users):
    """
    Generate the list of users that have ACEs on the account

    :param sclient: osis client for system model
    :param objdict: dict with the object data
    :param accessUserType: specifies whether object is account, vmachine or cloudspace
    :return: list of users have access to vmachine
    """
    for acl in objdict["acl"]:
        if acl["userGroupId"] in [user["id"] for user in users]:
            if accessUserType == "vm":
                users = filter(lambda user: user["id"] != acl["userGroupId"], users)
            else:
                continue
        if acl["type"] == "U":
            eusers = sclient.user.simpleSearch({"id": acl["userGroupId"]})
            if eusers:
                user = eusers[0]
                user["userstatus"] = acl["status"]
            elif acl["status"] == "INVITED":
                user = dict()
                user["id"] = acl["userGroupId"]
                user["emails"] = [acl["userGroupId"]]
                user["userstatus"] = acl["status"]
            else:
                user = dict()
                user["id"] = acl["userGroupId"]
                user["emails"] = ["N/A"]
                user["userstatus"] = "N/A"
            user["acl"] = acl["right"]
            user["accessUserType"] = accessUserType
            users.append(user)
    return users


def main(j, args, params, tags, tasklet):
    import gevent

    params.result = (args.doc, args.doc)
    id = args.requestContext.params.get("id")
    try:
        id = int(id)
    except:
        pass
    if not isinstance(id, int):
        args.doc.applyTemplate({})
        return params

    osiscl = j.clients.osis.getByInstance("main")
    cbosis = j.clients.osis.getNamespace("cloudbroker", osiscl)
    sosis = j.clients.osis.getNamespace("system")
    data = {
        "stats_image": "N/A",
        "stats_parent_image": "N/A",
        "stats_disk_size": "-1",
        "stats_ping": "N/A",
        "stats_hdtest": "N/A",
        "stats_epoch": "N/A",
        "snapshots": [],
        "stats_state": "N/A",
        "refreshed": False,
    }

    try:
        obj = cbosis.vmachine.get(id)
    except:
        args.doc.applyTemplate({})
        return params

    if obj.status not in resourcestatus.Machine.INVALID_STATES:
        with gevent.Timeout(15, False):
            # refresh from reality + get snapshots
            try:
                data["snapshots"] = j.apps.cloudbroker.machine.listSnapshots(id)
                data["refreshed"] = True
            except exceptions.BaseError:
                data["refreshed"] = False
    else:
        data["refreshed"] = True

    obj = cbosis.vmachine.get(id)

    try:
        cl = j.clients.redis.getByInstance("system")
    except:
        cl = None

    stats = dict()
    if cl and cl.hexists("vmachines.status", id):
        vm = cl.hget("vmachines.status", id)
        stats = json.loads(vm)

    data.update(obj.dump())
    try:
        stack = cbosis.stack.get(obj.stackId).dump()
    except Exception:
        stack = {"name": "N/A", "referenceId": "N/A", "type": "UNKNOWN"}
    try:
        image = cbosis.image.get(obj.imageId).dump()
    except Exception:
        image = {"name": "N/A", "referenceId": ""}
    try:
        space = cbosis.cloudspace.get(obj.cloudspaceId).dump()
        data["accountId"] = space["accountId"]
    except Exception:
        data["accountId"] = 0
        space = {"name": "N/A"}
    data["accountName"] = "N/A"
    if data["accountId"]:
        try:
            account = cbosis.account.get(space["accountId"]).dump()
            data["accountName"] = account["name"]
        except:
            pass

    fields = (
        "name",
        "id",
        "descr",
        "imageId",
        "stackId",
        "status",
        "hostName",
        "hypervisorType",
        "cloudspaceId",
        "tags",
    )
    for field in fields:
        data[field] = getattr(obj, field, "N/A")

    try:
        data["nics"] = []
        if [nic for nic in obj.nics if nic.ipAddress == "Undefined"]:
            # reload machine details
            j.apps.cloudapi.machines.get(obj.id)
            obj = cbosis.vmachine.get(obj.id)

        for nic in obj.nics:
            action = ""
            tagObj = j.core.tags.getObject(nic.params or "")
            gateway = tagObj.tags.get("gateway", "N/A")
            if "externalnetworkId" in tagObj.tags:
                externalNetworkId = int(tagObj.tags["externalnetworkId"])
                action = (
                    "{{action id:'action-DetachFromExternalNetwork' deleterow:true class:'glyphicon glyphicon-remove' data-externalNetworkId:'%s'}}"
                    % externalNetworkId
                )
                nic.ipAddress = "[%s|External Network?networkid=%s]" % (
                    nic.ipAddress,
                    tagObj.tags["externalnetworkId"],
                )
            nic.gateway = gateway
            nic.action = action
            data["nics"].append(nic)
    except Exception as e:
        data["nics"] = "NIC information is not available %s" % e

    data["disks"] = cbosis.disk.search({"id": {"$in": obj.disks}})[1:]
    diskstats = stats.get("diskinfo", [])
    disktypemap = {"D": "Data", "B": "Boot", "T": "Temp", "M": "Meta"}
    for disk in data["disks"]:
        disk["type"] = disktypemap.get(disk["type"], disk["type"])
        for diskinfo in diskstats:
            if disk["referenceId"].endswith(diskinfo["devicename"]):
                disk.update(diskinfo)
                disk["footprint"] = "%.2f" % j.tools.units.bytes.toSize(
                    disk["footprint"], output="G"
                )
                break

    data["image"] = image
    data["stackname"] = stack["name"]
    data["spacename"] = space["name"]
    data["stackrefid"] = stack["referenceId"] or "N/A"
    data["hypervisortype"] = stack["type"]

    try:
        data["portforwards"] = j.apps.cloudbroker.machine.listPortForwards(id)
    except:
        data["portforwards"] = []

    for k, v in stats.iteritems():
        if k == "epoch":
            v = j.base.time.epoch2HRDateTime(stats["epoch"])
        if k == "disk_size":
            if isinstance(stats["disk_size"], basestring):
                v = stats["disk_size"]
            else:
                size, unit = j.tools.units.bytes.converToBestUnit(
                    stats["disk_size"], "K"
                )
                v = "%.2f %siB" % (size, unit)
        data["stats_%s" % k] = v
    users = list()
    users = generateUsersList(sosis, account, "acc", users)
    users = generateUsersList(sosis, space, "cl", users)
    data["users"] = generateUsersList(sosis, data, "vm", users)

    data["referenceId"] = data["referenceId"].replace("-", "%2d")
    args.doc.applyTemplate(data, False)
    return params


def match(j, args, params, tags, tasklet):
    return True
