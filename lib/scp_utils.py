__author__ = 'cmantas'

#python ssh lib
import paramiko
import string
import sys
from socket import error as socketError
sys.path.append('lib/scp.py')
from lib.scp import SCPClient
from datetime import datetime, timedelta
from lib.persistance_module import env_vars, home
from time import time
import sys, traceback

ssh_timeout = 10

def reindent(s, numSpaces, prefix=''):
    s = string.split(s, '\n')
    s = [(numSpaces * ' ') +prefix+ string.lstrip(line) for line in s]
    s = string.join(s, '\n')
    return s


def run_ssh_command(host, user, command, indent=1, prefix="$: ", logger=None):
    """
    runs a command via ssh to the specified host
    :param host:
    :param user:
    :param command:
    :return:
    """
    ssh_giveup_timeout = env_vars['ssh_giveup_timeout']
    key_path = home + env_vars["priv_key_path"]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    private_key = paramiko.RSAKey.from_private_key_file(key_path)
    if not logger is None:
        logger.debug("Connecting to SSH")
    timer = Timer.get_timer()
    try:
        ssh.connect(host, username=user, timeout=ssh_timeout, pkey=private_key, allow_agent=False, look_for_keys=False)
        if logger:
            logger.debug("connected in %d sec. now Running SSH command" % timer.stop())
            timer.start()
        ### EXECUTE THE COMMAND ###
        stdin, stdout, stderr = ssh.exec_command(command)
        ret = ''
        for line in stdout:
            ret += line
        for line in stderr:
            ret += line
        # close the ssh connection
        ssh.close()
        if not logger is None:
            logger.debug("SSH command took %d sec" % timer.stop())
        return reindent(ret, indent, prefix=prefix)
    except:
        if not logger is None:
            logger.debug("Could not connect to "+ str(host))
        # traceback.print_exc()


def put_file_scp (host, user, files, remote_path='.', recursive=False):
    """
    puts the specified file to the specified host
    :param host:
    :param user:
    :param files:
    :param remote_path:
    :param recursive:
    :return:
    """
    ssh_giveup_timeout = env_vars['ssh_giveup_timeout']
    private_key = paramiko.RSAKey.from_private_key_file(env_vars["priv_key_path"])
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, timeout=ssh_giveup_timeout, pkey=private_key)
    scpc=SCPClient(ssh.get_transport())
    scpc.put(files, remote_path, recursive)
    ssh.close()


def test_ssh(host, user, logger=None):
    try:
        rv = run_ssh_command(host, user, 'echo success', logger=logger)
        return rv
    except:
        #print "error in connecting ssh:", sys.exc_info()[0]
        return False


class Timer():
    """
    Helper class that gives the ability to measure time between events
    """
    def __init__(self):
        self.started = False
        self.start_time = 0

    def start(self):
        if  self.started is True:
            raise Exception("timer already started")


        self.started = True
        self.start_time = int(round(time() * 1000))

    def stop(self):
        end_time = int(round(time() * 1000))
        if self.started is False:
            print " Timer had not been started"
            return 0.0
        start_time = self.start_time
        self.start_time = 0
        self.started = False
        return float(end_time - start_time)/1000

    @staticmethod
    def get_timer():
        timer = Timer()
        timer.start()
        return timer
