import threading
import unittest
from app import execution

class ExecutionTests(unittest.TestCase):
    def test_stop_interrupts_wait_without_starting_followup(self):
        started=threading.Event(); release=threading.Event(); stopped=threading.Event()
        def slow():started.set();release.wait(2);return 'late result'
        def run():
            with execution.running('cancel-test','p'):
                try:execution.wait_for(slow)
                except execution.Stopped:stopped.set()
        worker=threading.Thread(target=run);worker.start()
        try:
            self.assertTrue(started.wait(1))
            state=execution.status('cancel-test','p')
            execution.stop(execution.Stop(thread_id='cancel-test',persona='p',run_id=state['run_id']))
            self.assertTrue(stopped.wait(1))
        finally:release.set();worker.join(2)
        self.assertFalse(execution.status('cancel-test','p')['running'])
