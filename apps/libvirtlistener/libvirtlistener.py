from JumpScale import j
import time
import libvirt

from cloudbrokerlib import resourcestatus


def main():
    
    ccl = j.clients.osis.getNamespace("cloudbroker")
    scl = j.clients.osis.getNamespace("system")
    pcl = j.clients.portal.getByInstance("main")

    libvirt.virEventRegisterDefaultImpl()
    rocon = libvirt.open()

    def get_vm_tags(vm):
        vm = ccl.vmachine.get(vm["id"])
        cloudspace = ccl.cloudspace.get(vm.cloudspaceId)
        return "machineId:{} cloudspaceId:{} accountId:{}".format(
            vm.id, cloudspace.id, cloudspace.accountId
        )

    def callback(con, domain, event, detail, opaque):
        name = domain.name()
        print("State change for {} {} {}".format(name, event, detail))
        vm = next(
            iter(ccl.vmachine.search({"referenceId": domain.UUIDString()})[1:]), None
        )
        tags = ""
        if vm:
            if event == libvirt.VIR_DOMAIN_EVENT_STOPPED and detail in [
                libvirt.VIR_DOMAIN_EVENT_STOPPED_FAILED,
                libvirt.VIR_DOMAIN_EVENT_STOPPED_CRASHED,
            ]:
                msg = ""
                if name.startswith("vm-"):
                    machineId = int(name.split("-")[-1])
                    msg = "VM {} has crashed".format(machineId)
                    tags = get_vm_tags(vm)
                    pcl.actors.cloudapi.machines.start(machineId)
                elif name.startswith("routeros_"):
                    networkid = int(name.split("_")[-1], 16)
                    cloudspaces = ccl.cloudspace.search({"networkId": networkid})[1:]
                    if not cloudspaces:
                        return  # orphan vm we dont care
                    tags = "cloudspaceId:{}".format(cloudspaces[0]["id"])
                    domain.create()

                print("VM {} crashed, starting it again".format(name))
                j.errorconditionhandler.raiseOperationalWarning(
                    msg, "selfhealing", tags=tags
                )
                return
            newstate = None
            if event == libvirt.VIR_DOMAIN_EVENT_STARTED:
                newstate = "RUNNING"
            elif event == libvirt.VIR_DOMAIN_EVENT_STOPPED:
                newstate = "HALTED"
            if newstate is not None:
                print("Updating state for vm {} to {}".format(name, newstate))
                # update the state if its not destroyed already
                update = ccl.vmachine.updateSearch(
                    {"id": vm["id"], "status": {"$nin": [resourcestatus.Machine.TRANSITION_STATES]}},
                    {"$set": {"status": newstate}},
                )
                if update["nModified"] == 1:
                    # no action lock and we change status we should create and audit for this case
                    audit = scl.audit.new()
                    audit.user = "Operation System Action"
                    audit.tags = get_vm_tags(vm)
                    audit.statuscode = 200
                    audit.call = "/restmachine/cloudapi/machines/stop"
                    audit.timestamp = time.time()
                    audit.responsetime = 0
                    audit.args = "null"
                    audit.kwargs = "null"
                    audit.result = "null"
                    scl.audit.set(audit)
                    cloudspace = ccl.cloudspace.get(vm["cloudspaceId"])
                    j.system.ovsnetconfig.cleanupIfUnused(cloudspace.networkId)
                else:
                    print("Filed to update state for vm {} due to ongoing transition".format(name))


    rocon.domainEventRegisterAny(
        None, libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE, callback, rocon
    )
    while True:
        libvirt.virEventRunDefaultImpl()


if __name__ == "__main__":
    main()
