class Machine(object):
    """
    Define possible machine model status
    """

    VIRTUAL = "VIRTUAL"
    DEPLOYING = "DEPLOYING"
    STOPPING = "STOPPING"
    STARTING = "STARTING"
    HALTED = "HALTED"

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESTORING = "RESTORING"
    DELETED = "DELETED"
    DESTROYED = "DESTROYED"
    ERROR = "ERROR"

    PAUSING = "PAUSING"
    RESUMING = "RESUMING"
    REBOOTING = "REBOOTING"
    RESETING = "RESETING"
    DELETING = "DELETING"
    DESTROYING = "DESTROYING"
    ADDING_DISK = "ADDING_DISK"
    ATTACHING_DISK = "ATTACHING_DISK"
    DETACHING_DISK = "DETACHING_DISK"
    CLONING = "CLONING"

    INVALID_STATES = [DESTROYED, DELETED, ERROR, DESTROYING]
    NON_CONSUMING_STATES = [DESTROYED, DELETED, ERROR, HALTED]
    VALID_STATES = [PAUSED, HALTED, RUNNING]
    UP_STATES = [RUNNING, PAUSED]
    TRANSITION_STATES = [DEPLOYING, STOPPING, STARTING, REBOOTING, RESETING, PAUSING, RESUMING, 
                         DELETING, RESTORING, DESTROYING, ADDING_DISK, ATTACHING_DISK, DETACHING_DISK,
                         CLONING]

    ALLOWED_TRANSITIONS = {
        VIRTUAL: [DEPLOYING, DELETING, DESTROYING],
        RUNNING: [PAUSING, STOPPING, DELETING, RESETING, REBOOTING, ADDING_DISK, ATTACHING_DISK, DETACHING_DISK, DESTROYING],
        PAUSED: [RESUMING, STOPPING, DELETING, RESETING, REBOOTING, ADDING_DISK, ATTACHING_DISK, DETACHING_DISK, DESTROYING],
        HALTED: [STARTING, DELETING, DESTROYING, ADDING_DISK, ATTACHING_DISK, DETACHING_DISK, DESTROYING, CLONING],
        DELETED: [RESTORING, DESTROYING],
        DESTROYED: [],
        DEPLOYING: [RUNNING],
        PAUSING: [PAUSED],
        RESUMING: [RUNNING],
        STOPPING: [HALTED],
        STARTING: [RUNNING],
        REBOOTING: [RUNNING],
        RESETING: [RUNNING],
        DELETING: [DELETED],
        RESTORING: [HALTED],
        DESTROYING: [DESTROYED],
        CLONING: [HALTED]

    }


class Cloudspace(object):
    # static states
    VIRTUAL = "VIRTUAL"
    DEPLOYED = "DEPLOYED"
    DESTROYED = "DESTROYED"
    DISABLED = "DISABLED"
    DELETED = "DELETED"
    PAUSED = "PAUSED"

    # transition states
    DEPLOYING = "DEPLOYING"
    DISABLING = "DISABLING"
    ENABLING = "ENABLING"
    DELETING = "DELETING"
    DESTROYING = "DESTROYING"
    RESTORING = "RESTORING"
    PAUSING = "PAUSING"
    RESUMING = "RESUMING"
    RESETING = "RESETING"

    TRANSITION_STATES = [DEPLOYING, DISABLING, ENABLING, DELETING, DESTROYING, RESTORING, PAUSING, RESUMING, RESETING]
    INVALID_STATES = [DESTROYED, DELETED, DESTROYING, DELETING]
    ALLOWED_TRANSITIONS = {
        VIRTUAL: [DEPLOYING, DELETING, DESTROYING],
        DEPLOYED: [DISABLING, DELETING, DESTROYING, PAUSING, RESETING, RESUMING],
        PAUSED: [RESUMING, RESETING, DELETING, DESTROYING],
        DISABLED: [ENABLING, DELETING, DESTROYING],
        DELETED: [DESTROYING, RESTORING],
        DESTROYED: [],
        DEPLOYING: [DEPLOYED],
        DISABLING: [DISABLED],
        ENABLING: [DEPLOYED],
        DELETING: [DELETED],
        RESTORING: [DEPLOYED],
        DESTROYING: [DESTROYED],
        PAUSING: [PAUSED],
        RESUMING: [DEPLOYED],
        RESETING: [DEPLOYED],
    }

class Account(object):
    DESTROYED = "DESTROYED"
    DESTROYING = "DESTROYING"
    CONFIRMED = "CONFIRMED"
    DISABLED = "DISABLED"
    DELETED = "DELETED"
    INVALID_STATES = [DESTROYED, DESTROYING, DELETED]


class Disk(object):
    MODELED = "MODELED"
    ASSIGNED = "ASSIGNED"
    CREATING = "CREATING"
    CREATED = "CREATED"
    DESTROYED = "DESTROYED"
    DELETED = "DELETED"
    TOBEDELETED = "TOBEDELETED"
    
    DESTROYING = "DESTROYING"
    CREATING = "CREATING"
    ASSIGNING = "ASSIGNING"
    DELETING_ATTACHED_DISK = "DELETING_ATTACHED_DISK"
    DESTROYING_ATTACHED_DISK = "DESTROYING_ATTACHED_DISK"
    DELETING_DETACHED_DISK = "DELETING_DETACHED_DISK"
    DESTROYING_DETACHED_DISK = "DESTROYING_DETACHED_DISK"
    RESTORING_ATTACHED_DISK = "RESTORING_ATTACHED_DISK"
    RESTORING_DETACHED_DISK = "RESTORING_DETACHED_DISK"
    
    INVALID_STATES = [DESTROYED, TOBEDELETED, DELETED]
    TRANSITION_STATES = [CREATING, DELETING_ATTACHED_DISK, DESTROYING_ATTACHED_DISK, DELETING_DETACHED_DISK, DESTROYING_DETACHED_DISK,
                    RESTORING_ATTACHED_DISK, RESTORING_DETACHED_DISK]

    ALLOWED_TRANSITIONS = {
        MODELED: [CREATING, ASSIGNING],
        CREATED: [DELETING_DETACHED_DISK, DESTROYING_DETACHED_DISK],
        ASSIGNED: [DELETING_ATTACHED_DISK, DESTROYING_ATTACHED_DISK],
        DELETED: [DESTROYING_ATTACHED_DISK, RESTORING_ATTACHED_DISK],
        TOBEDELETED: [DESTROYING_DETACHED_DISK, RESTORING_DETACHED_DISK],
        DESTROYED:[],
        CREATING: [CREATED],
        ASSIGNING: [ASSIGNED],
        DELETING_DETACHED_DISK: [TOBEDELETED],
        DELETING_ATTACHED_DISK: [DELETED],
        DESTROYING_ATTACHED_DISK: [DESTROYED],
        DESTROYING_DETACHED_DISK: [DESTROYED],
        RESTORING_ATTACHED_DISK: [ASSIGNED],
        RESTORING_DETACHED_DISK: [CREATED],
    }


class Image(object):
    CREATED = "CREATED"
    CREATING = "CREATING"
    DESTROYED = "DESTROYED"
    DELETED = "DELETED"
    DISABLED = "DISABLED"
    INVALID_STATES = [DESTROYED, DELETED]

