from objectqueue import ObjectQueue
from statushandler import StatusHandler


class Scheduler(ObjectQueue):
    # def __init__(self, model, objectId, status=None, retry_count=1):
    #     self.id = objectId
    #     self.model = model
    #     self.status = status if status else StatusHandler(model, objectId).status
    #     self.retry_count = retry_count

    def schedule_task(
        self,
        object_id,
        model,
        method,
        init_status,
        transition_status,
        status_rollback=False,
        retry_count=1,
        real_status_getter=None,
        **kwargs
    ):
        """ Schedule task

            :param spaceId: OVC object id
            :param init_state: expected state of the object
            :param transition_status: transition state of the object during the action 
            :param status_rollback: if set to True rollback status to the initial status after the action is succeeded.
                    used for actions that return the object to the same state, for example attaching/detaching disks from machine.
            :param real_status_getter: method that sets object to its real status, currently can be set for machines.
        """
        StatusHandler(model, object_id, init_status).update_status(transition_status)
        action = self.get_instance().queue(
            model.cat, object_id, retry_count, method, object_id, **kwargs
        )
        try:
            result = action.get_result()
        except:
            StatusHandler(model, object_id, transition_status).rollback_status(
                init_status
            )
            if real_status_getter:
                real_status_getter(self.id)
            raise

        if status_rollback:
            StatusHandler(model, object_id, transition_status).rollback_status(
                init_status
            )

        return result
