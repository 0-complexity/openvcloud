from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    params.result = page = args.page
    cloudspaceId = int(args.getTag("cloudspaceId"))
    actors = j.apps.cloudbroker.iaas.cb.actors.cloudapi

    cloudspace = db.cloudbroker.cloudspace.get(cloudspaceId)
    stacks = db.cloudbroker.stack.search({"gid": cloudspace.gid, "status": "ENABLED"})[1:]

    images = actors.images.list(
        accountId=cloudspace.accountId, cloudspaceId=cloudspace.id
    )
    dropimages = list()
    dropstacks = list()
    dropstacks.append(("Auto", 0))

    def imageSorter(image):
        return image["type"] + image["name"]

    def sortName(item):
        return item["name"]

    for image in sorted(images, key=imageSorter):
        dropimages.append(("%(type)s: %(name)s" % image, image["id"]))

    for stack in sorted(stacks, key=sortName):
        dropstacks.append((stack["name"], stack["id"]))

    popup = Popup(
        id="createmachine",
        header="Create Machine On CPU Node",
        submit_url="/restmachine/cloudbroker/machine/createOnStack",
    )
    popup.addText("Machine Name", "name", required=True)
    popup.addText("Machine Description", "description", required=True)
    popup.addDropdown("Choose CPU Node", "stackid", dropstacks)
    popup.addDropdown("Choose Image", "imageId", dropimages)
    popup.addNumber("Disk Size in GiB", "disksize")
    popup.addNumber("Number of VCPUS", "vcpus")
    popup.addNumber("Amount of memory in MiB", "memory")
    popup.addTextArea("User data for cloud-init", "userdata", required=False, rows=5)
    popup.addHiddenField("cloudspaceId", cloudspaceId)
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
