import os.path as osp
from tensorboardX import SummaryWriter
import os
from six.moves import shlex_quote
from rlf.rl import utils
import sys
import pipes
import time
import numpy as np
import random
import datetime
import string
import copy
from rlf.exp_mgr import config_mgr
from rlf.rl.loggers.base_logger import BaseLogger

from collections import deque, defaultdict



class TbLogger(Logger):
    def __init__(self, tb_log_dir=None):
        super().__init__()
        self.tb_log_dir = tb_log_dir

    def init(self, args):
        super().init(args)
        if tb_log_dir is None:
            self.tb_log_dir = args.log_dir
        self.writer = self._create_writer(args, self.tb_log_dir)

    def _create_writer(self, args, log_dir):
        log_dir = osp.join(self.tb_log_dir, args.env_name, args.prefix)
        writer = SummaryWriter(log_dir)

        return writer

    def log_vals(self, key_vals, step_count):
        for k, v in key_vals.items():
            self.writer.add_scalar('data/' + k, v, step_count)

    def close(self):
        self.writer.close()
