import os
import string
import unittest
from os.path import join
from random import choice
from signal import SIGINT
from tempfile import gettempdir
from time import sleep
from multiprocessing import Process
from rocky.process import pid_file, stoppable


def normal_run(pf):
    with pid_file(filename=pf) as p, stoppable() as s:
        while s.check_stop(throw=False):
            sleep(0.01)


class Test(unittest.TestCase):

    def setUp(self):
        self.pf = join(gettempdir(), ''.join(choice(string.ascii_letters + string.digits + "_-") for _ in range(10)))
        if os.path.exists(self.pf): os.remove(self.pf)
        
    def test_normal_run_creates_and_removes_pid_file(self):
        p = Process(target=normal_run, args=(self.pf,))
        try:
            p.start()
            sleep(0.01)
            self.assertTrue(os.path.exists(self.pf))

            with open(self.pf, 'r') as f:
                self.assertEqual(p.pid, int(f.read().strip()))

            os.kill(p.pid, SIGINT)
            p.join(4)
            self.assertFalse(os.path.exists(self.pf))
        finally:
            p.terminate()

    def test_exits_on_existing_pid_file_with_pid_of_running_process(self):
        with open(self.pf, 'w') as f:
            f.write(str(os.getpid()))
        
        p = Process(target=normal_run, args=(self.pf,))
        try:
            p.start()
            p.join(4)
            for _ in range(40):
                if not p.is_alive():
                    break
                sleep(0.1)
            self.assertFalse(p.is_alive())
        finally:
            p.terminate()



