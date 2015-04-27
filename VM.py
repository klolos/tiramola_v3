__author__ = 'cmantas'
from sys import stderr
from os.path import exists
from os import mkdir, remove, makedirs
from time import time, sleep
import ntpath
import thread

from lib.scp_utils import *
from lib.persistance_module import env_vars, home
from lib.tiramola_logging import get_logger


#choose the IaaS provider
infrastructure = env_vars['iaas']
if infrastructure == 'okeanos':
    from lib import connector_okeanos as iaas
if infrastructure == 'openstack':
    from lib import connector_eucalyptus as iaas


LOGS_DIR = home+"files/VM_logs"
ATTEMPT_INTERVAL = 5


class VM (object):
    class Address:
        """
        Helper class that represents an IP address
        """
        def __init__(self, version, ip, in_type):
            self.version = version
            self.ip = ip
            self.type = in_type

        def __str__(self):
            rv = "%s IPv%d: %s" % (self.type, self.version, self.ip)
            return rv

    def __init__(self, name, flavor_id, image_id, create=False, wait=False, IPv4=False, log_path=LOGS_DIR):
        """
        VM class constructor
        """
        #set attributes
        self.created = False
        self.name = name
        self.flavor_id = flavor_id
        self.log_path = log_path
        self.image_id = image_id
        self.public_addresses = []
        self.addresses = []
        self.id = -1
        self.IPv4 = IPv4
        if not exists(LOGS_DIR):
            makedirs(LOGS_DIR)
        self.logfile = "%s/%s.log" % (LOGS_DIR, self.name)
        self.log = get_logger('[%s]' % self.name, 'INFO', logfile=self.logfile)
        if create:
            self.create(wait)

    def load_addresses(self):
        """
        loads the IP interfaces from the IaaS
        :return:
        """
        addr_list = iaas.get_addreses(self.id)
        for a in addr_list:
            addr = self.Address(a['version'], a['ip'], a['type'])
            self.addresses.append(addr)

    def from_dict(self, in_dict):
        """
        creates a VM from dictionary containing 'name' and 'id' reccords
        """
        self.name = in_dict['name']
        self.id = in_dict['id']

    def create(self, wait=False):
        if wait:
            self.log.info("creating (synchronously)")
            self.create_sync()
            self.wait_ready()
        else:
            self.log.info("creating (async)")
            thread.start_new_thread(self.create_sync, ())

    def create_sync(self):
        """
        Creates this VM in the underlying IaaS provider
        """
        #start the timer
        timer = Timer()
        timer.start()
        try:
            self.id = iaas.create_vm(self.name, self.flavor_id, self.image_id, self.IPv4, self.log)
        except Exception as e:
            self.log.error(e)
            exit(-1)
        new_status = iaas.get_vm_status(self.id)
        delta = timer.stop()
        if new_status == 'ERROR':
            self.log.error("IaaS creation FAILED")
            return
        self.log.info('IaaS status is now %s (took %d sec)' % (new_status, delta ) )
        self.created = True
        self.load_addresses()

    def shutdown(self):
        """
        Issues the 'shutdown' command to the IaaS provider
        """
        self.log.info('Shutting down (id: %s)' % self.id)
        return iaas.shutdown_vm(self.id)

    def startup(self):
        """
        boots up an existing VM instance in okeanos
        :return: true if VM exist false if not
        """
        if not self.created: return False;
        self.log.info('starting up (id: %s)' %  self.id)
        return iaas.startup_vm(self.id)

    def destroy(self):
        """Issues the 'destory' command to the IaaS provider  """
        self.log.info("Destroying ")
        iaas.destroy_vm(self.id)
        #delete the logfile
        try:
            remove(self.logfile)
        except: pass

    def __str__(self):
            text = ''
            text += '========== VM '+self.name+" ===========\n"
            text += "ID: "+str(self.id)+'\n'
            text += "Addresses (%s):" % len(self.addresses)
            for a in self.addresses:
                text += " [" + str(a) + "],"
            text += "\nCloud Status: %s\n" % self.get_cloud_status()
            return text

    @staticmethod
    def vm_from_dict(in_dict):
        """
        creates a VM instance from a synnefo "server" dict
        :param in_dict: "server" or "server details" dictionary from synnefo
        :return: a VM instance for an existing vm
        """
        vm_id, name, flavor_id, image_id = in_dict['id'], in_dict['name'].strip(), in_dict['flavor_id'], in_dict['image_id']
        rv = VM(name, flavor_id, image_id)
        rv.created = True
        rv.id = vm_id
        rv.load_addresses()
        return rv

    @staticmethod
    def from_id(vm_id):
        """ creates a VM instance from the VM id """
        vm_dict = iaas.get_vm_details(vm_id)
        return VM.vm_from_dict(vm_dict)

    def get_cloud_status(self):
        return iaas.get_vm_status(self.id)

    def run_command(self, command, user='root', indent=0, prefix="\t$:  ", silent=False):
        """
        runs a command to this VM if it actually exists
        :param command:
        :param user:
        :return:
        """
        if not self.created:
            stderr.write('this VM does not exist (yet),'
                         ' so you cannot run commands on it')
            return "ERROR"
        self.log.debug("running SSH command:\n\n%s\n\n" % reindent(command, 5))
        rv = run_ssh_command(self.get_private_addr(), user, command, indent, prefix, logger=self.log)
        if rv is not None:
            self.log.debug("command returned:\n\n %s\n\n" % rv)
        return rv

    def put_files(self, files, user='root', remote_path='.', recursive=False):
        """
        Puts a file or a list of files to this VM
        """
        put_file_scp(self.get_private_addr(), user, files, remote_path, recursive)

    def run_files(self, files):
        """
        puts a file in the VM and then runs it
        :param files:
        :return:
        """
        self.put_files(files)

        filename = ''
        remote_path = ''
        if not isinstance(files, (list, tuple)):
            head, tail = ntpath.split(files)
            filename = tail or ntpath.basename(head)
            remote_path = "~/scripts/" + filename
        else:
            for f in files:
                head, tail = ntpath.split(f)
                short_fname = (tail or ntpath.basename(head))
                filename += short_fname + ' '
                remote_path += "~/scripts/"+short_fname+"; "
        #generate the command that runs the desired scripts
        command = 'chmod +x %s; ' \
                  'mkdir -p scripts;' \
                  'mv %s ~/scripts/ 2>/dev/null;' \
                  '%s'\
                  % (filename, filename, remote_path)
        return self.run_command(command)

    def wait_ready(self):
        """
        Waits until it is able to run SSH commands on the VM or a timeout is reached
        """
        success = False
        attempts = 0
        if not self.created:
            self.log.debug("Not active yet. Sleeping")
            while not self.created: sleep(3)
        addr = self.get_private_addr()
        self.log.debug("Waiting for SSH daemon (%s)" % addr)
        end_time = datetime.now() + timedelta(seconds=env_vars['ssh_giveup_timeout'])
        timer = Timer()
        timer.start()
        while not success:
            attempts += 1
            self.log.debug("ssh attempt: " + str(attempts))
            res = test_ssh(addr, 'root', logger=self.log)
            if res:
                self.log.debug("ssh succeeded: " + str(res))
                success = True
            else:
                self.log.debug("ssh failed")
                if datetime.now() > end_time:
                    break
                sleep(ATTEMPT_INTERVAL)
        delta = timer.stop()
        if success:
            self.log.info("VM is now ready (took %d sec)" % delta)
        else:
            self.log.error("FAILED to be SSH-able (after %d sec)" % delta)
        return success

    def get_public_addr(self):
        """ Returns a publicly accessible IP address !!! for now, only checks for IPv6+fixed !!!"""
        rv = None
        if len(self.addresses) == 0:
            self.load_addresses()
        for i in self.addresses:
            if i.type == "fixed" and i.version == 6:
                rv = i.ip
        #if there is a floating IP available, return this one
        for i in self.addresses:
            if i.type == "floating" and i.version == 4:
                rv = i.ip
        return rv

    def get_private_addr(self):
        while not self.addresses: # wait till we get a private address!
            self.load_addresses()
            sleep(2)
        #find fixed ip
        for i in self.addresses:
            if i.version == 4 and i.type == "fixed":
                return i.ip


def get_all_vms(check_active=False):
    """
    Creates VM instances for all the VMs of the user available in the IaaS
    """
    log = get_logger("VM [static]", 'INFO')
    log.debug("getting all VMs")
    vms = []
    vm_ids = iaas.get_all_vm_ids()
    for vm_id in vm_ids:
        vm = VM.vm_from_dict(iaas.get_vm_details(vm_id))
        if check_active and vm.get_cloud_status() != "ACTIVE":
            continue
        else:
            vms.append(vm)
    return vms


if not exists(LOGS_DIR):
    mkdir(LOGS_DIR)


class Timer():
    """
    Helper class that gives the ablility to measure time between events
    """
    def __init__(self):
        self.started = False
        self.start_time = 0

    def start(self):
        assert self.started is False, " Timer already started"
        self.started = True
        self.start_time = int(round(time() * 1000))

    def stop(self):
        end_time = int(round(time() * 1000))
        assert self.started is True, " Timer had not been started"
        start_time = self.start_time
        self.start_time = 0
        self.started = False
        return float(end_time - start_time)/1000

    @staticmethod
    def get_timer():
        timer = Timer()
        timer.start()
        return timer
