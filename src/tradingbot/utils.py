import sys
import logging


class Monitoring:

    def __init__(self, logdir:str, debug:int=None):

        self.loglevel = "DEBUG" if debug else "INFO"
        self.logdir = logdir

    def get_logger(self, logname:str):

        logger = logging.getLogger(logname)
        fh = logging.FileHandler(f'{self.logdir}/{logname}.log')

        stdout = logging.StreamHandler(sys.stdout)

        if self.loglevel == "DEBUG":
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s %(levelname)-3s %(message)s')
        fh.setFormatter(formatter)
        logger.setLevel(logging.DEBUG)
        # Do not log to console.
        logger.propagate = True
        logger.addHandler(fh)
        logger.addHandler(stdout)
        return logger