from JumpScale.portal.portal import exceptions

class Machine(object):
    """
    Define possible machine model status
    """

    VIRTUAL = "VIRTUAL"
    DEPLOYING = "DEPLOYING"
    STOPPING = "STOPPING"
    STARTING = "STARTING"
    HALTED = "HALTED"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    RUNNING = "RUNNING"
    DESTROYING = "DESTROYING"
    DELETING = "DELETING"
    DELETED = "DELETED"
    DESTROYED = "DESTROYED"
    ERROR = "ERROR"
    ADDING_DISK = "ADDING_DISK"
    ATTACHING_DISK = "ATTACHING_DISK"
    DETACHING_DISK = "DETACHING_DISK"

    INVALID_STATES = [DESTROYED, DELETED, ERROR, DESTROYING]
    NON_CONSUMING_STATES = [DESTROYED, DELETED, ERROR, HALTED]
    TRANSITION_STATES = [DEPLOYING, STOPPING, STARTING, DELETING, DESTROYING]
    VALID_STATES = [PAUSED, HALTED, RUNNING]
    UP_STATES = [RUNNING, PAUSED]
    ALLOWED_TRANSITIONS = {
        RUNNING: [PAUSED, HALTED, DELETED, DESTROYED],
        PAUSED: [RUNNING, DELETED, DESTROYED],
        HALTED: [RUNNING, DELETED, DESTROYED],
        DELETED: [HALTED, DESTROYED],
    }



class Cloudspace(object):
    VIRTUAL = "VIRTUAL"
    DEPLOYING = "DEPLOYING"
    DESTROYED = "DESTROYED"
    DEPLOYED = "DEPLOYED"
    DESTROYING = "DESTROYING"
    MIGRATING = "MIGRATING"
    DISABLED = "DISABLED"
    DELETED = "DELETED"
    INVALID_STATES = [DESTROYED, DELETED, DESTROYING]


class Account(object):
    DESTROYED = "DESTROYED"
    DESTROYING = "DESTROYING"
    CONFIRMED = "CONFIRMED"
    DISABLED = "DISABLED"
    DELETED = "DELETED"
    INVALID_STATES = [DESTROYED, DESTROYING, DELETED]


class Disk(object):
    ASSIGNED = "ASSIGNED"
    MODELED = "MODELED"
    CREATING = "CREATING"
    CREATED = "CREATED"
    DESTROYED = "DESTROYED"
    DELETED = "DELETED"
    TOBEDELETED = "TOBEDELETED"
    INVALID_STATES = [DESTROYED, TOBEDELETED, DELETED]


class Image(object):
    CREATED = "CREATED"
    CREATING = "CREATING"
    DESTROYED = "DESTROYED"
    DELETED = "DELETED"
    DISABLED = "DISABLED"
    INVALID_STATES = [DESTROYED, DELETED]


def updateStatus(model, object_id, status, new_status):
    """ update status of an object in db
        
        :param model: collection to lock
        :param object_id: id og the object
        :param status: status that is expected
        :param new_status: update status
    """
    with model.lock(object_id):
        result = model.updateSearch(
            {"id": object_id, "status": status}, {"$set": {"status": new_status}}
        )
        if result["nModified"] == 0:
            raise exceptions.BadRequest(
                "Other action currently happening on {} ID: {}".format(
                    model.cat, object_id
                )
            )
        if result["nModified"] > 1:
            raise exceptions.BadRequest("More than one object was updated")