import inspect
from collections import namedtuple

from gevent import spawn, spawn_later
from gevent.queue import Queue
from JumpScale import j
from statushandler import StatusHandler


class ObjectQueue(object):
    """
    The ObjectQueue class implements a singleton that can be used to serialize method calls for specific objects.

    Eg queue a method for a vm object with id 4, retry 3 times before failing, and do not block
    oq = ObjectQueue() # Can also use the ObjectQueue.get_instance() method.
    oq.queue("vm", 4, 3, my_method, my_method_arg, my_method_kwarg="moehaha")

    Eg queue a method for a vm object with id 4, retry 3 times before failing, and block to get the result
    future = oq.queue("vm", 4, 3, my_method, my_method_arg, my_method_kwarg="moehaha")
    future.get_result() # This method raises if an exception would be thrown in my_method

    Eg queue a method for a vm object with id 4, retry 3 times before failing, and chain another method, then get the final result
    future = oq.queue("vm", 4, 3, my_method, my_method_arg, my_method_kwarg="moehaha")
    future2 = future.chain("vm", 4, 3, my_other_method, my_method_arg, my_method_kwarg="moehaha")
    future2.get_result() # This method raises if an exception would be thrown in my_method or my_other_method

    Eg stop the queue for a specific object, because it was deleted
    oq.stop("vm", 4)

    Eg terminate the queue, to gracefully execute all queued methods.
    oq.terminate()
    while not oq.is_empty():
        time.sleep(1)
    """

    __instance = None
    _valid_object_types = ("vmachine", "cloudspace", "disk", "image", "node")

    def __new__(cls):
        if ObjectQueue.__instance is None:
            ObjectQueue.__instance = object.__new__(cls)
        return ObjectQueue.__instance

    @classmethod
    def get_instance(cls):
        return cls.__instance or cls()

    def __init__(self):
        self.queues = dict()
        self.terminating = False
        def cleanup():
            for queue_name, queue in self.queues.iteritems():
                if queue.empty():
                    del self.queues[queue_name]
                    self._stop_queue(queue, queue_name)
            spawn_later(3600, cleanup)
        spawn_later(3600, cleanup)

    class _Future(object):

        _Result = namedtuple('Result', ['success', 'value'])
        _Details = namedtuple('FutureDetails', ['parent_future', 'object_type', 'object_id', 'method', 'args', 'kwargs'])

        def __init__(self, parent_future, object_type, object_id, retry_count, method):
            if not isinstance(retry_count, int):
                raise ValueError("retry_count argument should be an integer")
            if retry_count <= 0:
                raise ValueError("retry_count can not be less or equal to zero")
            if not callable(method):
                raise ValueError("method should be a method or function reference")
            self._listeners = list()
            self._result = None
            self.details = ObjectQueue._Future._Details(parent_future, object_type, object_id, method["callable"], method["args"], method["kwargs"])
            def run():
                def shackle():
                    def notify():
                        for listener in self._listeners:
                            listener.put("ping")
                    if self.details.parent_future:
                        result = self.details.parent_future.get_result_tuple()
                        if not result.success:
                            self._result = result
                            notify()
                            return
                    for _ in xrange(retry_count):
                        try:
                            _, _, varkw, _ = inspect.getargspec(method)
                            if varkw:
                                method["kwargs"]['_future_context'] = self
                            self._result = ObjectQueue._Future._Result(True, method(*method["args"], **method["kwargs"]))
                            break
                        except BaseException as e:
                            j.errorconditionhandler.processPythonExceptionObject(
                                e, message="Queued action failed."
                            )

                    else:
                        onerror = method.get("onerror")
                        if onerror:
                            try:
                                onerror["callable"](*onerror.get("args"), **onerror.get("kwargs"))
                            except BaseException as ee:
                                j.errorconditionhandler.processPythonExceptionObject(
                                ee, message="Cleanup action failed"
                            )
                        self._result = ObjectQueue._Future._Result(False, e)
                    notify()
                ObjectQueue.get_instance()._queue(object_type, object_id, shackle)
            run()

        def chain(self, object_type, object_id, retry_count, method):
            return ObjectQueue._Future(self, object_type, object_id, retry_count, method)

        def get_result_tuple(self):
            if self._result:
                return self._result
            listener = Queue()
            self._listeners.append(listener)
            listener.get()
            return self.get_result_tuple()

        def get_result(self):
            result = self.get_result_tuple()
            if result.success:
                return result.value
            else:
                raise result.value

    def queue(self, object_type, object_id, retry_count, method):
        future = ObjectQueue._Future(None, object_type, object_id, retry_count, method)
        return future

    def _queue(self, object_type, object_id, shackle):
        if self.terminating:
            raise RuntimeError(
                "The object queue is terminating. No additional requests can be queued"
            )
        queue = self.get_queue(object_type, object_id)
        queue.put(shackle)
    
    def get_queue(self, object_type, object_id):
        self._validate_object_type(object_type)
        queue_name = self._get_queue_name(object_type, object_id)
        if not queue_name in self.queues:
            def runner(queue):
                for shackle in queue:
                    shackle()
            queue = Queue()
            self.queues[queue_name] = queue
            spawn(runner, queue)
            return queue
        return self.queues[queue_name]

    def stop(self, object_type, object_id):
        self._validate_object_type(object_type)
        queue_name = self._get_queue_name(object_type, object_id)
        queue = self.queues[queue_name]
        self._stop_queue(queue, queue_name)

    def terminate(self):
        self.terminating = True
        for queue_name, queue in self.queues.iteritems():
            self._stop_queue(queue, queue_name)

    def is_empty(self):
        return len(self.queues) == 0

    def _stop_queue(self, queue, queue_name):
        queue.put((None, 1, self._stopper, queue_name))
        queue.put(StopIteration)

    def _stopper(self, queue_name):
        if queue_name in self.queues:
            del self.queues[queue_name]

    def _validate_object_type(self, object_type):
        if object_type not in ObjectQueue._valid_object_types:
            raise ValueError(
                "%s is not a valid object_type. Valid object types are: %s"
                % (object_type, ObjectQueue._valid_object_types)
            )

    def _get_queue_name(self, object_type, object_id):
        return "%s-%s" % (object_type, object_id)

    def schedule_tasks(
        self,
        object_id,
        model,
        method,
        init_status,
        transition_status=None,
        status_rollback=False,
        status_rollback_on_fail=True,
        retry_count=1,
    ):
        """ Schedule task

            :param spaceId: OVC object id
            :param init_state: expected state of the object
            :param transition_status: transition state of the object during the action, 
                    @transition_status set to None for actions that should be hidden, f.e. migration
            :param status_rollback: if set to True rollback status to the initial status after the action is succeeded.
                    used for actions that return the object to the same state, for example attaching/detaching disks from machine.
            :param status_rollback_on_fail: if True status will roll back in case if action fails.
                    @status_rollback_on_fail is set to False for migration, as migration does not change status and does not require status rollback.
        """
        if transition_status:
            StatusHandler(model, object_id, init_status).update_status(transition_status)
        else:
            StatusHandler(model, object_id, init_status).validate_status()
            status_rollback = False

        if not isinstance(method, list):
            methods = [method]
        else:
            methods = method

        queue = self.get_instance().get_queue(model.cat, object_id)
    
        for method in methods:
            action = queue.chain(
                model.cat, object_id, retry_count, method
            )
        try:
            result = action.get_result()
        except:
            if status_rollback_on_fail:
                StatusHandler(model, object_id, transition_status).rollback_status(
                    init_status
                )

        if status_rollback:
            StatusHandler(model, object_id, transition_status).rollback_status(
                init_status
            )

        return result