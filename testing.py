__author__ = 'cmantas'

import logging
import logging.handlers
import sys

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.name = "test"

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(levelname)s] - %(name)s: %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
ch = logging.handlers.RotatingFileHandler('files/logs/test.log', maxBytes=2 * 1024 * 1024, backupCount=5)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(name)s: %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.error("helloo")

class test:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return  self.name


all= [test("christos"), test("giannis"), test("aristos"), test("xavier")]


for a in all: print a