import logging
import os
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import OrderedDict

logger = logging.getLogger(__name__)


def add_boolean_arg(parser: ArgumentParser, name: str, desc: str, default: bool = False) -> None:
    """Adds a boolean arg to the arg parser allowing
    --arg and --no-arg for True and False respectively

    Parameters
    ----------
    parser : ArgumentParser
        Arg parser to add the argument to
    name : str
        Name of the argument
    desc : str
        Description of the arg to add
    default : bool, optional
        Default value of the boolean flag, by default False
    """
    dest = name.replace("-", "_")
    group = parser.add_argument_group(f"{name} options:", desc)
    me_group = group.add_mutually_exclusive_group(required=False)
    me_group.add_argument(f"--{name}", dest=dest, action="store_true", help="(default)" if default else "")
    me_group.add_argument(
        f"--no-{name}",
        dest=dest,
        action="store_false",
        help="(default)" if not default else "",
    )
    parser.set_defaults(**{dest: default})


@dataclass
class Args:
    """Data Class for storing CL args"""

    log_level: int = int(os.getenv("LOGGING_LEVEL", logging.DEBUG))
    console_log: bool = bool(os.getenv("STREAM_LOGS", True))


def parse_args() -> Args:
    """Parses CL args into a Args object
    Returns
    -------
    Args
        Args object containing all the
    """
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "-ll",
        "--log-level",
        default=logging.DEBUG,
        type=int,
        dest="log_level",
        help="The log level of logging",
    )
    arg_parser.add_argument(
        "-cl", "--console-log", dest="console_log", type=bool, default=True, help="Whether to stream logs to the console. "
    )
    return Args(**OrderedDict(vars(arg_parser.parse_args())))
