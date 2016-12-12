import os
import traceback
import errno
from tempfile import gettempdir

import psutil
import sys
import time

from contextlib import ContextDecorator
from logging import getLogger
from signal import signal, SIG_DFL, SIGINT, SIGUSR1

logger = getLogger("rocky")


class log_exception(ContextDecorator):
    """
    Context manager for logging exceptions and (optionally) exit with status.
    """

    def __init__(self, ignore=(SystemExit,), message="Command '%s' failed, exiting: " % sys.argv[0], status=None):
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
        """ Check if stop flag is set. If throw is True (default) SystemExit will be raised, if not it returns False if
        program should stop. """
        if not throw:
            return not self._stop

        if self._stop:
            raise SystemExit()

    def stop(self):
        """ Set stop to true explicitly. """
        self._stop = True


class pstack(handle_signals):
    """ Dump python stack in log on signal (default SIGUSR1). """
    
    def __init__(self, signums=(SIGUSR1,)):
        """
        signums -- iterable on signals to dump stack for
        """
        super().__init__(signums=signums)

    def on_signal(self, signum, frame):
        logger.info("stack:\n" + "".join(traceback.format_stack(frame)))


DEFAULT_PID_DIR = gettempdir()


class pid_file(ContextDecorator):
    """
    Context manager for handling a pid file. The class have a number of lifecycle events, these can be replaced
    either by:
     
    1, Inherit the class and override the method for the event.
    2, Provide a callback to the constructor.

    The lifecycle has the following events, see the method descriptions for info on the default action. Each callback
    will get the same argumenst as the method.

    1, If pid file already exists
       a, If process is dead => dead_process event
       b, If process is alive => existing event
       c, If process is older than max age => max_age event
    2, Create pid file, if pid file existed and an exception was not raised during 1, the file will be
       overwritten here.
       
    If SystemExit is raised it will exit gracefully and remove the pid file, else the exception is propagated
    without removing it.
    
    Pid file will be locked when reading and writing.
    """
    
    def __init__(self,
                 filename=None,
                 dirname=DEFAULT_PID_DIR,
                 basename=None,
                 max_age=None,
                 max_age_callback=None,
                 existing_callback=None,
                 dead_callback=None):

        """
        filename -- pid file, will be dirname / basename if not set (available as property)
        dirname -- the directory to put pid file in of filename is not set
        basename -- default based on sys.argv[0]
        max_age -- max age seconds of existing process before max age event (available as property), forever if None
        max_age_callback -- se class description
        existing_callback -- se class description
        dead_callback -- se class description
        """
        self.progname = os.path.basename(sys.argv[0])
        self.dirname = dirname
        self.basename = basename or (self.progname + '.pid')
        self.filename = filename or os.path.join(self.dirname, self.basename)
        self.max_age = max_age
        self.max_age_callback = max_age_callback
        self.existing_callback = existing_callback
        self.dead_callback = dead_callback
        self.created = False

    def on_existing(self, pid, age):
        """
        Called when the process in the pid file is alive but was created less than. Return true if pid cretion should
        be retried (this requires killing the other process, or it will be a loop). Return
        false to continue without a pid file.

        Default behaviour is to info log and raise SystemExit.

        pid -- pid of existing process
        age -- age of the other process
        """
        if self.existing_callback:
            return self.existing_callback(pid, age)

        logger.info("other %s with pid %d still running, stopping" % (self.progname, pid))

        raise SystemExit()

    def on_max_age(self, pid, age):
        """
        Called when the process in the pid file is alive but was created more than max_age seconds ago. Return true
        if pid cretion should be retried (this requires killing the other process, or it will be a loop). Return
        false to continue without a pid file.

        Default behaviour is to log a warning and raise SystemExit.

        pid -- pid of existing process
        age -- age of the other process
        """

        if self.max_age_callback:
            return self.max_age_callback(pid, age)

        logger.warning("age of other process with pid %d exceeds max age, %ds > %ds, pid file '%s', stopping" %
                       (pid, age, self.max_age, self.filename))
        raise SystemExit()

    def on_dead(self, pid):
        """
        Called when the process in the pid file is dead. Return true if pid cretion should be retried (this requires
        removing the pid file).Return
        false to continue without a pid file.

        Default behaviour is to log a warning a warning then remove file and retry).

        pid -- pid of existing process
        """
        if self.dead_callback:
            return self.dead_callback(pid)

        logger.warning("process %d from pid file '%s' does not exist but pid file do, last run of %s failed fatally"
                       % (pid, self.filename, self.progname))
        os.remove(self.filename)
        return True

    def __enter__(self):
        try:
            pid = os.getpid()
            with open(self.filename, 'x') as f:
                f.write("%d\n" % pid)
            self.created = True
            logger.info("created pid file '%s' for %s with pid %s, process_max_age is %s" %
                        (self.filename, self.progname, pid, self.max_age))
            return self
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise OSError("could not write pid to pid file '%s'" % self.filename) from e

        try:
            with open(self.filename, 'r') as f:
                pid = int(f.readline().strip())
        except OSError as e:
            # Could be removed at this point, but unlikely, treat as error to be safe.
            raise OSError("could not read pid from pid file '%s'" % self.filename) from e

        try:
            process = psutil.Process(pid)
            age = time.time() - process.create_time()
            if self.max_age is not None and age > self.max_age:
                if self.on_max_age(pid, age):
                    return self.__enter__()
                return self

            else:
                if self.on_existing(pid, age):
                    return self.__enter__()
                return self

        except psutil.NoSuchProcess:
            # File but no process, log error remove and try again.
            if self.on_dead(pid):
                return self.__enter__()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.created:
            return False

        try:
            logger.info("removing pid file '%s' for %s with pid %s" % (self.filename, self.progname, os.getpid()))
            os.remove(self.filename)
        except OSError:
            logger.exception("could not remove pid file '%s'" % self.filename)

        return False
