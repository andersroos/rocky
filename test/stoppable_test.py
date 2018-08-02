import os
import unittest
from signal import SIGINT
from time import sleep

from multiprocessing import Process

from rocky.process import stoppable


def nice_process():
    with stoppable() as s:
        while s.check_stop():
            sleep(0.01)


def nasty_process():
    with stoppable() as s:
        while True:
            sleep(1)


class Test(unittest.TestCase):

    def test_nice_process_is_stopped_after_one_signal(self):
        p = Process(target=nice_process)
        try:
            p.start()
            sleep(0.01)

            os.kill(p.pid, SIGINT)

            p.join(1)
            self.assertFalse(p.is_alive())
        finally:
            p.terminate()

    def test_nasty_process_is_killed_on_fifth_signals(self):
        p = Process(target=nasty_process)
        try:
            p.start()
            for _ in range(4):
                sleep(0.01)
                os.kill(p.pid, SIGINT)

            self.assertTrue(p.is_alive())

            os.kill(p.pid, SIGINT)

            p.join(2)
            self.assertFalse(p.is_alive())
        finally:
            p.terminate()

