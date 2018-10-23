# from objectqueue import ObjectQueue
# from statushandler import StatusHandler


# class Scheduler(ObjectQueue):
#     def schedule_tasks(
#         self,
#         object_id,
#         model,
#         method,
#         init_status,
#         transition_status=None,
#         status_rollback=False,
#         status_rollback_on_fail=True,
#         retry_count=1,
#     ):
#         """ Schedule task

#             :param spaceId: OVC object id
#             :param init_state: expected state of the object
#             :param transition_status: transition state of the object during the action, 
#                     @transition_status set to None for actions that should be hidden, f.e. migration
#             :param status_rollback: if set to True rollback status to the initial status after the action is succeeded.
#                     used for actions that return the object to the same state, for example attaching/detaching disks from machine.
#             :param status_rollback_on_fail: if True status will roll back in case if action fails.
#                     @status_rollback_on_fail is set to False for migration, as migration does not change status and does not require status rollback.
#         """
#         if transition_status:
#             StatusHandler(model, object_id, init_status).update_status(transition_status)
#         else:
#             StatusHandler(model, object_id, init_status).validate_status()
#             status_rollback = False

#         if not isinstance(method, list):
#             methods = [method]
#         else:
#             methods = method

#         queue = self.get_instance().get_queue(model.cat, object_id)
    
#         for method in methods:
#             action = queue.chain(
#                 model.cat, object_id, retry_count, method
#             )
#         try:
#             result = action.get_result()
#         except:
#             if status_rollback_on_fail:
#                 StatusHandler(model, object_id, transition_status).rollback_status(
#                     init_status
#                 )

#         if status_rollback:
#             StatusHandler(model, object_id, transition_status).rollback_status(
#                 init_status
#             )

#         return result

#             # if real_status_getter:
#             #     real_status_getter(self.id)
#             # raise