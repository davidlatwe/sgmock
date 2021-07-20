from pprint import pprint, pformat
import os
import uuid
from datetime import datetime

# import shotgun_api3

from sgmock import Shotgun, ShotgunError, Fault
from sgmock import Fixture
from sgmock import TestCase


def mini_uuid():
    return uuid.uuid4().hex[:8]

def timestamp():
    return datetime.now().strftime('%Y%m%d%H%M%S')

def minimal(entity):
    return dict(type=entity['type'], id=entity['id'])
