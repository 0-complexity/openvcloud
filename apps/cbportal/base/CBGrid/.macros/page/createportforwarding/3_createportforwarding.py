from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    params.result = page = args.page
    cloudspaceId = int(args.getTag("cloudspaceId"))
    vmachines = db.cloudbroker.vmachine.search(
        {
            "cloudspaceId": cloudspaceId,
            "status": {"$nin": ["ERROR", "DESTROYED", "DELETED"]},
        }
    )[1:]
    dropvmachines = list()

    for vmachine in sorted(vmachines, key=lambda vm: vm["name"]):
        dropvmachines.append((vmachine["name"], vmachine["id"]))

    popup = Popup(
        id="createportforwarding",
        header="Create Port Forwarding",
        submit_url="/restmachine/cloudbroker/machine/createPortForward",
    )
    popup.addDropdown("Choose Machine", "machineId", dropvmachines)
    popup.addNumber("Public Port", "destPort", required=True)
    popup.addNumber("VM Port", "localPort", required=True)
    popup.addDropdown("Protocol", "proto", [("TCP", "tcp"), ("UDP", "udp")])
    popup.addHiddenField("reason", "")

    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
