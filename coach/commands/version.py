import sys

from coach import __version__
from coach.commands import command


@command("version", help="Print the coach package and Python versions")
def version(args, ctx):
    return {"version": __version__, "python": ".".join(str(part) for part in sys.version_info[:3])}
