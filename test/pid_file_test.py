import os
import unittest
from signal import SIGINT
from time import sleep
from multiprocessing import Process
from rocky.process import pid_file, stoppable


def pid_creation_and_removal(pf):
    with pid_file(filename=pf) as p, stoppable() as s:
        while s.check_stop(throw=False):
            sleep(0.01)


class Test(unittest.TestCase):

    def test_normal_run_creates_and_removes_pid_file(self):
        pf = '/tmp/pid_creation_and_removal'
        if os.path.exists(pf): os.remove(pf)
        p = Process(target=pid_creation_and_removal, args=(pf,))
        try:
            p.start()
            sleep(0.01)
            self.assertTrue(os.path.exists(pf))

            with open(pf, 'r') as f:
                self.assertEqual(p.pid, int(f.read().strip()))

            os.kill(p.pid, SIGINT)
            p.join(1)
            self.assertFalse(os.path.exists(pf))
        finally:
            p.terminate()


