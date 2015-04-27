__author__ = 'cmantas'

from VM import VM, Timer, LOGS_DIR
from VM import get_all_vms
from lib.persistance_module import env_vars, get_script_text
from lib.tiramola_logging import get_logger


class Node (VM):
    """
    Class that represents a node a cluster. extends VM
    """

    def __init__(self, cluster_name='', node_type='', number=0, create=False, IPv4=False, wait=False, vm=None, flavor=None, image=None):
        """
        Creates a Node object.
        :param cluster_name:
        :param node_type: the type of the node
        :param create: if True then the actual VM will be created
        :param vm: used to create a Node from a pre-existing VM
        """

        self.bootstrapped = False
        self.name = cluster_name + "_" + node_type + "_" + str(number)
        self.type = node_type
        self.number = number
        self.cluster_name = cluster_name

        if flavor is None:
            self.flavor = env_vars["default_flavor"]
        else:
            self.flavor = flavor
        if image is None:
            self.image = env_vars["default_image"]
        else:
            self.image = image

        if not vm is None:
            # init a node from a VM
            self.from_vm(vm)
        else:
            #create a VM for this node
            super(Node, self).__init__(self.name, self.flavor, self.image, IPv4=IPv4, create=create, wait=wait)

    def __str__(self):
        rv = "Node || name: %s, type: %s" % (self.name, self.type)
        return rv

    def from_vm(self, vm):
        """
        Creates a Node from a pre-existing VM
        :param vm:
        :return:
        """
        self.name = vm.name
        if not vm.created:
            self.log.error("this VM is not created, so you can't create a node from it")
            return
        self.log = vm.log
        super(Node, self).__init__(self.name, self.flavor, self.image, IPv4=vm.IPv4)
        self.id = vm.id
        self.created = True
        self.type = self.name[self.name.find("_")+1:][:self.name[self.name.find("_")+1:].find("_")]
        self.cluster_name = self.name[:self.name.find("_")]
        self.log.debug("cluster = "+self.cluster_name)
        self.addresses = vm.addresses

    def bootstrap(self):
        """
        Runs the required bootstrap scripts on the node
        """
        command = ""
        self.log.debug("Running bootstrap script")
        command += get_script_text(self.cluster_name, self.type, "bootstrap")
        timer = Timer.get_timer()
        rv = self.run_command(command)
        self.log.debug("command returned:\n"+str(rv))
        self.log.info("now bootstrapped (took %d sec)" % timer.stop())
        self.bootstrapped = True

    def decommission(self):
        """
        Cecommissions a node from the Cluster
        :return:
        """
        self.log.info( "running decommission script")
        command = get_script_text(self.cluster_name, self.type, "decommission")
        timer = Timer.get_timer()
        self.run_command(command, silent=True)
        action = env_vars["%s_decommission_action" % self.cluster_name]
        if action == "KEEP": pass
        elif action == "SHUTDOWN": self.shutdown()
        elif action == "DESTROY": self.destroy()
        self.log.info( "now decommissioned (took %d sec)" % (timer.stop()))

    def kill(self): # TODO
        """
        Runs the required scripts to kill the application being run in the cluster
        """
        self.log.debug ( "running kill script")
        command = get_script_text(self.cluster_name, self.type, "kill")
        self.run_command(command, silent=True)

    def inject_hostnames(self, hostnames, delete=None):
        """
        appends hostnames to /etc/hosts file in the node so that it inlcludes the given hostnames and ips
        if delete is specified, it removes from /etc/hosts the lines containing the given string
        :param hostnames: a mapping of hostnames-->IPs
        """
        text = ""
        if not delete is None:
            # delete required entries
            self.run_command('sed -i "/.*%s.*/g" /etc/hosts; sed -i "/^$/d" /etc/hosts' % delete)
        for host in hostnames.keys():
            text += "\n%s %s" % (hostnames[host], host)
        self.run_command("echo '%s' >> /etc/hosts; echo %s >/etc/hostname" %
                         (text, self.name), silent=True)

    def get_status(self): # TODO does not have ctool installed
        """
        Gets the status of the node, combining IaaS status and hooks inside the VM
        TODO: specify status script and run to get status
        :return the status
        """
        if self.get_cloud_status() != "ACTIVE":
            return "stopped"
        #wait for the vm to be ready and SSH-able
        self.wait_ready()
        status = self.run_command("ctool status", indent=0, prefix='')
        return status.strip()


    @staticmethod
    def get_all_nodes(cluster_name="", check_active=False):
        """
        Returns a Node instance for each one of the VMs running in the cluster
        :param cluster_name: only return Nodes of the specified cluster (whose name starts with 'cluster_name')
        :param check_active: if true only return VMs whose IaaS status is 'ACTIVE'
        :return:
        """
        vms = get_all_vms(check_active=check_active)
        nodes = []
        for vm in vms:
            if (cluster_name != "") and (not vm.name.startswith(cluster_name)):
                continue
            else:
                node = Node(vm=vm)
                nodes.append(node)
        return nodes

