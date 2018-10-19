import time
from cloudbrokerlib import resourcestatus
from JumpScale.portal.portal import exceptions

NAME_MAP = {
    "vmachine": "Machine",
    "cloudspace": "Cloudspace",
    "account": "Account",
    "image": "Image",
    "node": "Node",
    "disk": "Disk"
}

class StatusHandler(object):
    def __init__(self, model, object_id, status=None):
        """ :param model: collection, example cb.models.vmachine
            :param object_id: id on the object in the collection @model
        """
        self.id = object_id
        self.model = model
        self.category = NAME_MAP[model.cat]
        self.object_class = getattr(resourcestatus, self.category)
        self.status = status if status else self.get_status()

    def get_status(self):
        query = {"id": self.id}
        obj = self.model.searchOne({"$query": query, "$fields": ["status"]})
        if not obj:
            raise exceptions.BadRequest(
                "Exactly one {} with id {} is expected".format(
                    self.category, self.id
                )
            )
        return obj["status"]

    def update_status(self,  target_status):
        """ update status of an object in db
            
            :param object_id: id of the object
            :param target_status: update status
        """
        self.validate_transition(target_status)
        self._update_status(target_status)

    def rollback_status(self, previous_status):
        """ roll back status of an object in db
            
            :param object_id: id of the object
            :param previous_status: status to roll back too
        """
        self.validate_rollback(previous_status)
        self._update_status(previous_status)

    def _update_status(self, target_status):
        result = self.model.updateSearch(
            {"id": self.id, "status": self.status},
            {"$set": {
                "updateTime": int(time.time()),
                "status": target_status}},
        )

        if not result["nModified"]:
            raise exceptions.BadRequest(
                "Failed to update status of item ID {} in collection {} from {} to {}, status was set incorrectly or modified by another process".format(
                    self.id, self.category, self.status, target_status,
                )
            )
        if result["nModified"] > 1:
            raise exceptions.BadRequest("More than one object was updated")

    def validate_transition(self, target_status):
        if target_status not in self.object_class.ALLOWED_TRANSITIONS[self.status]:
            raise exceptions.BadRequest(
                '{} {} in state {} cannot update to state {}'.format(
                    self.category, self.id, self.status, target_status
                )
            )
        return True

    def validate_rollback(self, previous_status):
        """
            Roll back is allowed from a transition status to a previous static status

            :param status: current transition state
            :param previous_status: previous static state to roll back to
        """
        if self.status not in self.object_class.TRANSITION_STATES:
            raise exceptions.BadRequest("{} in state {} cannot roll back to {}".format(
                self.category, self.status, previous_status)
            )
        for status_lookup in self.object_class.ALLOWED_TRANSITIONS:
            if status_lookup == previous_status and self.status in self.object_class.ALLOWED_TRANSITIONS[status_lookup]:
                return True
        raise exceptions.BadRequest(
            '{} {} in state {} cannot roll back to state {}'.format(
                self.category, self.id, self.status, previous_status
            )
        )

