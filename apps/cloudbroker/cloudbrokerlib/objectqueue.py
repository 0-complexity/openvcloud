from gevent import spawn, spawn_later
from gevent.queue import Queue


class ObjectQueue(object):
    """
    The ObjectQueue class implements a singleton that can be used to serialize method calls for specific objects.

    Eg queue a method for a vm object with id 4, retry 3 times before failing, and do not block
    oq = ObjectQueue() # Can also use the ObjectQueue.get_instance() method.
    oq.queue("vm", 4, 3, False, my_method, my_method_arg, my_method_kwarg="moehaha")

    Eg queue a method for a vm object with id 4, retry 3 times before failing, and block to get the result
    my_method_result =  oq.queue("vm", 4, 3, True, my_method, my_method_arg, my_method_kwarg="moehaha")

    Eg stop the queue for a specific object, because it was deleted
    oq.stop("vm", 4)

    Eg terminate the queue, to gracefully execute all queued methods.
    oq.terminate()
    while not oq.is_empty():
        time.sleep(1)
    """

    __instance = None
    _valid_object_types = ("vm", "cloudspace", "disk", "image", "node")

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

    def queue(
        self,
        object_type,
        object_id,
        retry_count,
        wait_for_result,
        method,
        *args,
        **kwargs
    ):
        if self.terminating:
            raise RuntimeError(
                "The object queue is terminating. No additional requests can be queued"
            )
        self._validate_object_type(object_type)
        queue_name = self._get_queue_name(object_type, object_id)
        if not queue_name in self.queues:

            def runner(queue):
                for result_queue, retry_count, method, args, kwargs in queue:
                    for _ in xrange(retry_count):
                        try:
                            result = method(*args, **kwargs)
                            if result_queue:
                                result_queue.put((True, result))
                            break
                        except BaseException as e:
                            # Need to file ECO here
                            pass
                    else:
                        if result_queue:
                            result_queue.put((False, e))

            queue = Queue()
            self.queues[queue_name] = queue
            spawn(runner, queue)
        result_queue = Queue() if wait_for_result else None
        self.queues[queue_name].put((result_queue, retry_count, method, args, kwargs))
        if wait_for_result:
            success, result = result_queue.get()
            if success:
                return result
            raise result

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
