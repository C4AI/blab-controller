"""Template for settings used in a development environment.

Create a copy of this file and name it "dev.py".
"""

from .dev_base import *  # noqa: F401

CHAT_ENABLE_QUEUE = True
# Change this to False to make bots synchronous

CHAT_ENABLE_ROOMS = True
# Change this to False to disable rooms
