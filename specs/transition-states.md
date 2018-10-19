# Transition states for OpenvCloud objects

## Purpose

For all OVC objects like **Machines**, **Cloudspaces**, **Accounts**, **Disks**, **Images**, and **Nodes** ensure that only one action is executed at a time. This is necessary to avoid race conditions caused by running actions simultaneously.

**Static** state is a state of an OVC object, which does not change unless requested, or forced.
**Transition** state is a state of an OVC object that occurs while transitioning between static states. Each transition state represents an action that is being executed. One or several chained transitions can be necessary to reach from one static state to another.
Prior to running any action on an OVC object we ensure that transition from the current state to the target state is allowed.

## List of transition states of OVC objects

* DESTROYED - object is permanently deleted.
* DELETED - object moved to the recycle bin and will be permanently deleted after retention period.

### Virtual Machine states

|Initial State|Transition State| Desired State|
|---|---|---|
|VIRTUAL*|DEPLOYING* |RUNNING|
| RUNNING | PAUSING* | PAUSED |
| PAUSED | RESUMING* | RUNNING |
|RUNNING/PAUSED| STOPPING| HALTED |
|RUNNING/PAUSED| DELETING| DELETED |
|RUNNING/PAUSED| DESTROYING| DESTROYED  |
|HALTED| DELETING| DELETED |
|HALTED| DESTROYING| DESTROYED |
|RUNNING| REBOOTING | RUNNING|
|PAUSED| REBOOTING | RUNNING|
|RUNNING| RESETTING | RUNNING|
|RUNNING| ADDING_DISK / ATTACHING_DISK / DETACHING_DISK | RUNNING|
|PAUSED| ADDING_DISK / ATTACHING_DISK / DETACHING_DISK | PAUSED|
|HALTED| ADDING_DISK / ATTACHING_DISK / DETACHING_DISK | HALTED|

\* new state

### Cloudspace states

|Initial State|Transition States| Desired State|
|---|---|---|
|VIRTUAL|DEPLOYING|DEPLOYED|
|DEPLOYED| DISABLING*| DISABLED|
|DISABLED| ENABLING* | DEPLOYED|
|DEPLOYED / DISABLED|DELETING|DELETED|
|DELETED| DESTROYING| DESTROYED|
|DELETED| RESTORING | DEPLOYED|
|DEPLOYED| PAUSING***| PAUSED*** |
|PAUSED**| RESUMING** | DEPLOYED|
|DEPLOYED| RESETTING** | DEPLOYED|


** State PAUSED is reached by stopping Virtual Firewall (VFW) from cloudbroker. Pausing is an administrative action that cannot be recreated by the user, brining cloudspace back to the state DEPLOYED can be done by starting or resetting VFW by administrator.


\* new states

### Account states

|Initial State|Transition States| Desired State|
|---|---|---|
|CONFIRMED| DISABLING*| DISABLED|
|DISABLED| ENABLING*| CONFIRMED|
|CONFIRMED / DISABLED| DESTROYING | DESTROYED |
|CONFIRMED / DISABLED| DELETING | DELETED |

\* new states

### Disk states

|Initial State|Transition States| Desired State|
|---|---|---|
|MODELED|CREATING|CREATED|
|MODELED|ASSIGNING*| ASSIGNED|
|CREATED| ATTACHING*| ASSIGNED|
|ASSIGNED| DETACHING* | CREATED|
|CREATED| DELETING | DELETED |
|CREATED| DESTROYING | DESTROYED |
|ASSIGNED| DELETING* | TOBEDELETED |
|ASSIGNED| DESTROYING | DESTROYED |

\* new states

* CREATED - disk detached from any VM.
* ASSIGNED - disk attached to a VM.
* DELETED - detached disk in recycle bin
* TOBEDELETED - attached disk in recycle bin (was deleted together with VM)

### Image states

|Initial State|Transition States| Desired State|
|---|---|---|
|VIRTUAL*|CREATING|CREATED|
|CREATED| DISABLING*| DISABLED|
|DISABLED|DISABLING|CREATED|
|CREATED / DISABLED| DELETING* |  DELETED* |
|CREATED / DISABLED| DESTROYING* | DESTROYED |

\* new states

### Node states

|Initial State|Transition States| Desired State|
|---|---|---|
|ENABLED| PUTTING_IN_MAINTENANCE* |MAINTENANCE|
|MAINTENANCE| ENABLING* | ENABLED |
|ENABLED/MAINTENANCE| DECOMMISSIONING* | DECOMMISSIONED|

## Implementation steps

- [ ] define missing transition states among the resource statuses, group transition states in a list TRANSITION_STATES, all the rest of states are assumed to be static.
- [ ] define method `validate_transition(object_type, init_state, desired_state)`. If transition is allowed return `True`, otherwise `False`.
- [ ] implement a **queuer** to manage queues of tasks for each OVC object like VM, cloudspace, image, and physical node. The queuer loops over all queues and execute tasks in order of arrival.
  Logic of the **queuer**:
  * ones an action is requested on an OVC object for the first time, a new queue gets created.
  * for every action requested on an OVC object the corresponding method is pushed to the queue, if this action is allowed.
  * actions on a disk are scheduled in the queue where the disk is attached to.

  The **queuer** implements:
  * `queue()` - create queue for given OVC object if doesn't exist.
  * `stop()` - graceful termination of a single queue, waits for all queued actions to be executed and then deletes the queue.
  * `terminate()` - graceful termination for all OVC objects, for every object waits for all queued actions to be executed and then deletes the queue.

- [ ] Add state checks prior to pushing action to the queue of any OVC object:
  * If an object is in static state - push action to the object's queue.
  * If in transition state: return error `Cannot execute action at this time`.
- [ ] Before a new method is triggered on a OVC object, the status has to be changed to the corresponding transition state (see tables above), unless this is method `migrate()`, then previous status remains. Migration should be hidden from the user and does not appear in the model.

- [ ] change of states in db should be only done in unified way that guarantees **atomic state change**:
  * ensure that initial state matches the expected, otherwise return error: `409 Conflict: Other action currently happening on vm`.
  * lock collection and set state to the target state.

    ``` py
    def update_status(model, object_id, status, new_status):
      # update status of an object in db
      # example call: update_status(model=self.models.vmachine, object_id=vmid, status='RUNNING', new_status='PAUSING')
      with model.lock():
        result = model.updateSearch({'id': object_id, 'status': status}, {'$set': {'status': new_status}})
          if result['nModified'] == 0:
            raise BadRequest('Other action currently happening on {} ID: {}'.format(model.cat, object_id))
          if result['nModified'] > 1:
            raise BadRequest('More than one object was updated')
    ```

## Examples of scenarios potentially leading to the race condition

### Scenario 1. Virtual Machine Migration

When handling requests we rely on the concept that a user should never trigger more that one action at the same time. Therefore, if user is trying to run an action on an object in a transition state, API will respond with error: `409 Conflict`.

When being migrated, OVC objects are also not accessible to perform any actions on them. However, migration process is triggered due to putting CPU nodes in maintenance or automated load balancing and should be hidden from the user. Therefore, requests coming from the user during the migration should be accepted and executed after the migration is completed. Only one request at a time can be accepted from the user during the migration.

Scenario shown in the diagram bellow illustrates the following:
* Ones VM migration is triggered, method `migrate()` is added to the queue. This does not affect VM status.
* Request to destroy VM received during the migration pushes method `destroy()` to the queue, VM status is set to DESTROYING. At this time action is waiting until the VM has migrated.
* Ones migration is finished, the queuer proceeds to the next method `destroy_vm()`.
* Method `destroy_vm()` is composed of three methods that need to be execute on the VM sequentially: `stop()`, `delete()`, `destroy()`.
* Ones and object is destroyed the queue should be terminated.
* After `destroy_vm()` is completed, state of the VM is switched to the state DESTROYED.

![Figure](
https://docs.google.com/drawings/d/e/2PACX-1vQnjR2IHHqanJEVGuGp_N2NS0qHNK-J8hy9-ZBKcLRx5qDZCf9cbGDnvMuhEclPfv2SCY8aj0bSEl0k/pub?w=855&h=943)

## Notes
* Additionally a selfhealing script should be implemented and periodicaly scheduled to perform the following tasks:
  1. Ensure no OVC objects are stuck in transition states (to base it on timeout, every OVC object should store time of last changes in its model).
  2. Report objects that are stuck in transition and recover their state to the previous state.