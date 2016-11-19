from argparse import ArgumentTypeError
from datetime import datetime, timezone
from logging import INFO, getLogger

logger = getLogger('rocky')


def date(arg):
    """ Date argument in iso format. """
    try:
        return datetime.strptime(arg, '%Y-%m-%d').date()
    except BaseException as e:
        raise ArgumentTypeError("Illegal date %s" % arg) from e


def utcdatetime(arg):
    """ Datetime in utc argument. """
    try:
        return datetime.strptime(arg, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except BaseException as e:
        raise ArgumentTypeError("illegal datetime %r" % arg) from e


def log_args(args, level=INFO):
    """ Log all arg values. """
    for arg, value in sorted(vars(args).items()):
        logger.log(level, "arg %s = %r", arg, value)
