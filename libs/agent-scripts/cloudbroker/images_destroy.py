import time
from JumpScale import j


descr = """
Permanently removes deleted images that are not used by any machine if the configured period for this grid has passed since deletion. (Empties the trash can)
"""

category = "cloudbroker"
organization = "cloudscalers"
author = "ali.chaddad@gig.tech"
license = "bsd"
version = "1.0"
roles = ['master']
queue = "hypervisor"
async = True
log = True
enable = True
period = 3600
timeout = 900

def action():
    from CloudscalerLibcloud.utils.gridconfig import GridConfig
    ccl = j.clients.osis.getNamespace('cloudbroker')
    current_time = time.time()
    images = ccl.image.search({'status': 'DELETED'}, size=0)[1:]
    scl = j.clients.osis.getNamespace('system')
    pcl = j.clients.portal.getByInstance('main')
    for image in images:
        references = ccl.vmachine.count(
            {"imageId": image["id"], "status": {"$ne": "DESTROYED"}}
        )
        if references:
            return
        deletion_time = image['deletionTime']
        grid_id = image['gid']
        grid = scl.grid.get(grid_id)
        grid_config = GridConfig(grid)
        retention_period = grid_config.get('delete_retention_period')
        if current_time >= (deletion_time + retention_period):
            pcl.actors.cloudbroker.image.delete(image['id'], reason='Cleanup job', permanently=True)

if __name__ == '__main__':
    action()
