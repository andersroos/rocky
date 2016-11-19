import os
from contextlib import ContextDecorator
from logging import WARNING, INFO, getLogger

import sys

import errno

import psutil
import time

from rocky import Stop


logger = getLogger("rocky")

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
       
    If Stop is raised, it will exit gracefully, else the exception is propagated.
    
    Pid file will be locked when reading and writing.
    """
    
    def __init__(self,
                 filename=None,
                 dirname='/var/run',
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
        self.basename = self.progname + '.pid'
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

        Default behaviour is to info log and raise Stop.

        pid -- pid of existing process
        age -- age of the other process
        """
        if self.existing_callback:
            return self.existing_callback(pid, age)

        logger.info("other %s with pid %d still running, stopping" % (self.progname, pid))

        raise Stop()

    def on_max_age(self, pid, age):
        """
        Called when the process in the pid file is alive but was created more than max_age seconds ago. Return true
        if pid cretion should be retried (this requires killing the other process, or it will be a loop). Return
        false to continue without a pid file.

        Default behaviour is to log a warning and raise Stop.

        pid -- pid of existing process
        age -- age of the other process
        """

        if self.max_age_callback:
            return self.max_age_callback(pid, age)

        logger.warning("age of other process with pid %d exceeds max age, %ds > %ds, pid file '%s', stopping" %
                       (pid, age, self.max_age, self.filename))
        raise Stop()

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
