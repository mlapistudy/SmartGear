import os
import sys
import time
import sys
import psutil
import hashlib
import logging
import functools
import multiprocessing as mp
import struct
# for python3.8
mp.set_start_method("fork")

# from . import corpus, tracer
from . import tracer

logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger().setLevel(logging.DEBUG)

SAMPLING_WINDOW = 5 # IN SECONDS

try:
    lru_cache = functools.lru_cache
except:
    import functools32
    lru_cache = functools32.lru_cache


def worker(target, child_conn, close_fd_mask):
    # Silence the fuzzee's noise
    class DummyFile:
        """No-op to trash stdout away."""
        def write(self, x):
            pass
    logging.captureWarnings(True)
    logging.getLogger().setLevel(logging.CRITICAL)
    if close_fd_mask & 1:
        sys.stdout = DummyFile()
    if close_fd_mask & 2:
        sys.stderr = DummyFile()

    sys.settrace(tracer.trace)
    while True:
        buf = child_conn.recv_bytes()
        try:
            target(buf)
        except Exception as e:
            print("Exception: %r\n" % (e,))
            logging.exception(e)
            child_conn.send(e)
            break
        else:
            loc_lines = bytes(tracer.get_lines(LOC_FILE), 'ascii')
            child_conn.send_bytes(struct.pack('>iii'+str(len(loc_lines))+'s', tracer.get_coverage(), tracer.get_cov_of_file(LOC_FILE), tracer.get_loc(LOC_FILE), loc_lines) )



class Fuzzer(object):
    def __init__(self,
                 target,
                 dirs=None,
                 exact_artifact_path=None,
                 rss_limit_mb=2048,
                 timeout=120,
                 regression=False,
                 max_input_size=4096,
                 close_fd_mask=0,
                 runs=-1,
                 mutators_filter=None,
                 dict_path=None,
                 loc_file=None):
        self._target = target
        self._dirs = [] if dirs is None else dirs
        self._exact_artifact_path = exact_artifact_path
        self._rss_limit_mb = rss_limit_mb
        self._timeout = timeout
        self._regression = regression
        self._close_fd_mask = close_fd_mask
        self._total_executions = 0
        self._executions_in_sample = 0
        self._last_sample_time = time.time()
        self._total_coverage = 0
        self._cov_of_file = 0
        self._loc_count = 0
        self._loc_details = ""
        self._p = None
        self.runs = runs

        global LOC_FILE
        LOC_FILE = loc_file

    def log_stats(self, log_type):
        rss = (psutil.Process(self._p.pid).memory_info().rss + psutil.Process(os.getpid()).memory_info().rss) / 1024 / 1024

        endTime = time.time()
        execs_per_second = int(self._executions_in_sample / (endTime - self._last_sample_time))
        self._last_sample_time = time.time()
        self._executions_in_sample = 0
        logging.info(' >> covered lines: '+ self._loc_details)
        return rss

    def write_sample(self, buf, prefix='crash-'):
        m = hashlib.sha256()
        m.update(buf)
        if self._exact_artifact_path:
            crash_path = self._exact_artifact_path
        else:
            crash_path = prefix + m.hexdigest()
        logging.info('sample written to {}'.format(crash_path))
        if len(buf) < 200:
            try:
                logging.info('sample = {}'.format(buf.hex()))
            except AttributeError:
                logging.info('sample = {!r}'.format(buf))
        with open(crash_path, 'wb') as f:
            f.write(buf)

    def start(self):
        parent_conn, child_conn = mp.Pipe()
        self._p = mp.Process(target=worker, args=(self._target, child_conn, self._close_fd_mask))
        self._p.start()

        # while True:
        for _ in range(1):
            if self.runs != -1 and self._total_executions >= self.runs:
                self._p.terminate()
                break

            buf = bytearray(0)
            parent_conn.send_bytes(bytes(buf))
            if not parent_conn.poll(self._timeout):
                self._p.terminate()
                logging.info("=================================================================")
                logging.info("timeout reached. testcase took: {}".format(self._timeout))
                self.write_sample(buf, prefix='timeout-')
                break

            try:
                values = parent_conn.recv_bytes()
                loc_details = values[12:].decode("ascii") 
                total_coverage, cov_of_file, loc_count = struct.unpack('>iii', values[:12])
            except ValueError:
                self.write_sample(buf)
                break

            self._total_executions += 1
            self._executions_in_sample += 1
            self._cov_of_file = cov_of_file
            self._loc_count = loc_count
            self._loc_details = loc_details
            rss = 0
            if total_coverage > self._total_coverage:
                self._total_coverage = total_coverage
                rss = self.log_stats("NEW")
            else:
                if (time.time() - self._last_sample_time) > SAMPLING_WINDOW:
                    rss = self.log_stats('PULSE')

            if rss > self._rss_limit_mb:
                logging.info('MEMORY OOM: exceeded {} MB. Killing worker'.format(self._rss_limit_mb))
                self.write_sample(buf)
                self._p.kill()
                break
        # self._p.join()
        try:
            self._p.kill()
        except:
            self._p.join()
