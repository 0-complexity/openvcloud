from unittest import TestCase, main

import gevent

from objectqueue import ObjectQueue


class TestObjectQueue(TestCase):

    def test_simple(self):
        def sum(*args):
            result = 0
            for arg in args:
                result += arg
            return result
        future = ObjectQueue.get_instance().queue("vmachine", "1", 3, sum, 1, 2)
        result = future.get_result()
        self.assertEqual(result, 3)
    
    def test_chain_simple(self):
        def sum(val1, val2, **kwargs):
            result = val1 + val2
            _future_context = kwargs["_future_context"]
            if _future_context.details.parent_future:
                result += _future_context.details.parent_future.get_result()
            return result
        future = ObjectQueue.get_instance().queue("vmachine", "1", 3, sum, 1, 2)
        future = future.chain("vmachine", "1", 3, sum, 4, 5)
        future = future.chain("vmachine", "1", 3, sum, 4, 5)
        result = future.get_result()
        self.assertEqual(result, 21)

    def test_chain_complex(self):
        def sum(val1, val2, **kwargs):
            result = val1 + val2
            _future_context = kwargs["_future_context"]
            if _future_context.details.parent_future:
                result += _future_context.details.parent_future.get_result()
            return result
        stap1 = ObjectQueue.get_instance().queue("vmachine", "1", 3, sum, 1, 2)
        stap2 = stap1.chain("vmachine", "1", 3, sum, 4, 5)
        stap2b = stap1.chain("vmachine", "1", 3, sum, 4, 5)
        stap2b2 = stap2b.chain("vmachine", "1", 3, sum, 4, 5)
        stap3 = stap2.chain("vmachine", "1", 3, sum, 4, 5)
        result = stap3.get_result()
        self.assertEqual(result, 21)
        self.assertEqual(stap1.get_result(), 3)
        self.assertEqual(stap2.get_result(), 12)
        self.assertEqual(stap2b.get_result(), 12)
        self.assertEqual(stap2b2.get_result(), 21)
        self.assertEqual(stap3.get_result(), 21)
    
    def test_simple_fail(self):
        def fail():
            raise ValueError()
        future = ObjectQueue.get_instance().queue("vmachine", "1", 1, fail)
        self.assertRaises(ValueError, future.get_result)

    def test_double_fail(self):
        def fail():
            raise ValueError()
        def go():
            pass
        future = ObjectQueue.get_instance().queue("vmachine", "1", 1, fail)
        future = future.chain("vmachine", "1", 3, go)
        import ipdb; ipdb.set_trace()
        self.assertRaises(ValueError, future.get_result)

if __name__ == '__main__':
    main()
