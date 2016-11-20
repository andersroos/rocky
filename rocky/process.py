from contextlib import ContextDecorator

import sys
from logging import getLogger
from signal import signal, SIG_DFL, SIGINT

from rocky import Stop

logger = getLogger("rocky")


class log_exception(ContextDecorator):
    """
    Context manager for logging exceptions and (optionally) exit with status.
    """

    def __init__(self, ignore=(Stop,), message="Command '%s' failed, exiting: " % sys.argv[0], status=None):
        """
        On exceptions log exception and optionally sys.exit.

        ignore -- exceptions classes to ignore
        message -- log message on exception
        status -- exit status on non ignored exception, None to prevent exit
        """
        self.ignore = ignore
        self.message = message
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            return
        if any(isinstance(exc_val, i) for i in self.ignore):
            return True
        logger.exception(self.message)
        if self.status:
            sys.exit(self.status)


class handle_signals(ContextDecorator):
    """
    Contect manager for setting and unetting signal handler. Signal handler can be arg to constructor or by
    subclassing and implement on_signal.

    """

    def __init__(self, signums=(), handler=None):
        """
        signums -- iterable on signals to handle
        handler -- signal handler taking signum and frame
        """
        self.existing_handlers = {}
        self.signums = signums
        self.handler = handler or self.on_signal

    def __enter__(self):
        for signo in self.signums:
            self.existing_handlers[signo] = signal(signo, self.handler)
        return self

    def on_signal(self, signum, frame):
        """ Called on singals unless handler was set in constructor. """
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        for signum, handler in self.existing_handlers.items():
            signal(signum, handler or SIG_DFL)


class stoppable(handle_signals):
    """
    Context manager for gracefully handle stopping. The first few times the signal is recieved it will log and change
    its internal state to stop so that the program can periodically check stop and stop gracefully. After a
    configurable number of signals the process will do sys.exit.
    """

    def __init__(self, signums=(SIGINT,), count=4):
        """
        signums -- iterable on signals to handle
        count -- signals received before sys.exit
        """
        super().__init__(signums=signums)
        self._stop = False
        self._count = count

    def on_signal(self, signum, frame):
        self._count -= 1
        if self._count < 0:
            sys.exit(1)
        logger.info("got signal %d, breaking as soon as possible, %d left before kill" % (signum, self._count))
        self.stop()

    def check_stop(self, throw=True):
        """ Check if stop flag is set. If throw is True (default) Stop will be raised, if not it returns False if
        program should stop. """
        if not throw:
            return not self._stop

        if self._stop:
            raise Stop()

    def stop(self):
        """ Set stop to true explicitly. """
        self._stop = True
