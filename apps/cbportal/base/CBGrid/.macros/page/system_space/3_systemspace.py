from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    params.result = page = args.page
    gid = int(args.getTag("gid"))
    actors = j.apps.cloudapi

    images = actors.images.list(accountId=None, cloudspaceId=None)
    dropimages = list()

    def imageSorter(image):
        return image["type"] + image["name"]

    for image in sorted(images, key=imageSorter):
        dropimages.append(("%(type)s: %(name)s" % image, image["id"]))

    popup = Popup(
        id="createsystemspace",
        header="Create system space on the grid",
        submit_url="/restmachine/cloudbroker/grid/createSystemSpace",
    )
    popup.addText("Resource Name", "name", required=True)
    popup.addDropdown("Choose Image", "imageId", dropimages)
    popup.addNumber("Boot Disk Size in GiB", "bootsize")
    popup.addNumber("Choose data Disk Size in GiB", "dataDiskSize")
    popup.addNumber("Number of VCPUS", "vcpus")
    popup.addNumber("Amount of memory in MiB", "memory")
    popup.addTextArea("User data for cloud-init", "userdata", required=False, rows=5)
    popup.addHiddenField("id", gid)
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
