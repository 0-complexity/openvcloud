from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    params.result = page = args.page
    ccl = j.clients.osis.getNamespace('cloudbroker')
    locations = list()
    for location in ccl.location.search({})[1:]:
        locations.append((location['name'], location['locationCode']))

    # Placeholder that -1 means no limits are set on the cloud unit
    culimitplaceholder = 'set to -1 if no limits should be set'
    popup = Popup(id='createaccount', header='Create Account', submit_url='/restmachine/cloudbroker/account/create')
    popup.addText('Name', 'name', required=True, placeholder='Account Name')
    popup.addText('Username', 'username', required=True,
                  placeholder='Owner of account, will be created if does not exist')
    popup.addText('Email Address', 'emailaddress', required=False,
                  placeholder='User email, only required if username does not exist')
    popup.addDropdown('Choose Location', 'location', locations)
    popup.addText('Max Memory Capacity (GB)', 'maxMemoryCapacity', placeholder=culimitplaceholder, type='float')
    popup.addText('Max VDisk Capacity (GB)', 'maxVDiskCapacity', placeholder=culimitplaceholder, type='number')
    popup.addText('Max Number of CPU Cores', 'maxCPUCapacity', placeholder=culimitplaceholder, type='number')
    popup.addText('Max Primary Storage(NAS) Capacity (TB)', 'maxNASCapacity', placeholder=culimitplaceholder, type='number')
    popup.addText('Max Secondary Storage(Archive) Capacity (TB)', 'maxArchiveCapacity', placeholder=culimitplaceholder, type='number')
    popup.addText('Max Network Transfer In Operator (GB)', 'maxNetworkOptTransfer', placeholder=culimitplaceholder, type='number')
    popup.addText('Max Network Transfer Peering (GB)', 'maxNetworkPeerTransfer', placeholder=culimitplaceholder, type='number')
    popup.addText('Max Number of Public IP Addresses', 'maxNumPublicIP', placeholder=culimitplaceholder, type='number')
    popup.write_html(page)
    return params


def match(j, args, params, tags, tasklet):
    return True
