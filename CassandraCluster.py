__author__ = 'cmantas'
from Node import Node
from VM import get_all_vms
from json import loads, dumps
from os import remove
from os.path import isfile
from lib.persistance_module import get_script_text, env_vars

orchestrator = None     # the VM to which the others report to

seeds = []              # the seed node(s) of the casssandra cluster !!! ONLY ONE IS SUPPORTED !!!
nodes = []              # the rest of the nodes of the Cassandra cluster
clients = []            # the clients of the cluster
stash = []              # list of the Nodes that are available (active) but not used

# the name of the cluster is used as a prefix for the VM names
cluster_name = env_vars['active_cluster_name']

# the save file for saving/reloading the active cluster
save_file = "files/saved_%s_cluster.json" % cluster_name

# the flavor and image for the VMs used int the cluster
Node.flavor = env_vars["default_flavor"]
Node.image = env_vars["cassandra_base_image"]


def create_cluster(worker_count=0, client_count=0):
    """
    Creates a Cassandra Cluster with a single Seed Node and 'worker_count' other nodes
    :param worker_count: the number of the nodes to create-apart from the seednode
    """
    #create the seed node
    seeds.append(Node(cluster_name, node_type="seed", number=0, create=True, IPv4=True))
    #create the rest of the nodes
    for i in range(worker_count):
        name = cluster_name+str(len(nodes)+1)
        nodes.append(Node(cluster_name, node_type="node", number=len(clients)+1, create=True))
    for i in range(client_count):
        clients.append(Node(cluster_name, node_type="client", number=len(clients)+1, create=True))
    #wait until everybody is ready
    save_cluster()
    wait_everybody()
    inject_hosts_files()
    print "CLUSTER: Every node is ready for SSH"


def wait_everybody():
    """
    Waits for all the Nodes in the cluster to be SSH-able
    """
    print "CLUSTER: Waiting for SSH on all nodes"
    for i in seeds + nodes + clients:
        i.wait_ready()


def bootstrap_cluster():
    """
    Runs the necessary boostrap commnands to each of the Seed Node and the other nodes
    """
    inject_hosts_files()
    print "CLUSTER: Running bootstrap scripts"
    #bootstrap the seed node
    seeds[0].bootstrap()
    #bootstrap the rest of the nodes
    for n in nodes+clients:
        n.bootstrap(params={"seednode": seeds[0].get_private_addr()})
    print "CLUSTER: READY!!"


def resume_cluster():
    """
    Re-loads the cluster representation based on the VMs pre-existing on the IaaS and the 'save_file'
    """
    if not isfile(save_file):
        print "CLUSTER: No existing created cluster"
        return
    saved_cluster = loads(open(save_file, 'r').read())
    saved_nodes = saved_cluster['nodes']
    saved_clients = saved_cluster['clients']
    saved_seeds = saved_cluster['seeds']
    nodes[:] = []
    seeds[:] = []
    in_nodes = Node.get_all_nodes(cluster_name=cluster_name, check_active=True)
    #check that all saved nodes actually exist and exit if not remove
    to_remove = []
    for n in saved_nodes:
        if n not in [i.name for i in in_nodes]:
            print "CLUSTER: ERROR, node %s does actually exist in the cloud, re-create the cluster" % n
            remove(save_file)
            exit(-1)
    for n in in_nodes:
        if n.name not in saved_nodes+saved_seeds+saved_clients:
            continue
        else:
            if n.type == "seed": seeds.append(n)
            elif n.type == "node": nodes.append(n)
            elif n.type == "client": clients.append(n)


def save_cluster():
    """
    Creates/Saves the 'save_file'
    :return:
    """
    cluster = dict()
    cluster["seeds"] = [s.name for s in seeds]
    cluster["nodes"] = [n.name for n in nodes]
    cluster["clients"] = [c.name for c in clients]
    string = dumps(cluster, indent=3)
    f = open(save_file, 'w+')
    f.write(string)


def kill_clients():
    """
    Runs the kill scripts for all the clients
    """
    print "CLUSTER: Killing clients"
    for c in clients: c.kill()


def kill_nodes():
    """
    Runs the kill scripts for all the nodes in the cluster
    """
    print "CLUSTER: Killing cassandra nodes"
    for n in seeds+nodes+stash:
        n.kill()


def kill_all():
    """
    Kill 'em all
    """
    kill_clients()
    kill_nodes()


def inject_hosts_files():
    """
    Creates a mapping of hostname -> IP for all the nodes in the cluster and injects it to all Nodes so that they
    know each other by hostname. Also restarts the ganglia daemons
    :return:
    """
    print "CLUSTER: Injecting host files"
    hosts = dict()
    for i in seeds+nodes + clients:
        hosts[i.name] = i.get_private_addr()
    #manually add  the entry for the seednode
    hosts["cassandra_seednode"] = seeds[0].get_private_addr()
    #add the host names to etc/hosts
    orchestrator.inject_hostnames(hosts)
    for i in seeds+nodes+clients:
        i.inject_hostnames(hosts)
    seeds[0].run_command("service ganglia-monitor restart; service gmetad restart")
    orchestrator.run_command("service ganglia-monitor restart; service gmetad restart")


def find_orchestrator():
    """
    Uses the firs VM whose name includes 'orchestrator' as an orchestrator for the cluster
    :return:
    """
    vms = get_all_vms()
    for vm in vms:
        if "orchestrator" in vm.name:
            global orchestrator
            orchestrator = Node(vm=vm)
            return


def add_node_sync():
    """
    Adds a node to the cassandra cluster. Refreshes the hosts in all nodes
    :return:
    """
    print "CLUSTER: Adding node cassandra_node_%d" % str(len(nodes)+1)
    if not len(stash) == 0:
        new_guy = stash[0]
        del stash[0]
    else:
        new_guy = Node(cluster_name, str(len(nodes)+1), create=True)
    nodes.append(new_guy)
    new_guy.wait_ready()
    #inject host files to everybody
    inject_hosts_files()
    new_guy.bootstrap()
    print "CLUSTER: Node %s is live " % (new_guy.name)
    save_cluster()


def remove_node():
    """
    Removes a node from the cassandra cluster. Refreshes the hosts in all nodes
    :return:
    """
    dead_guy = nodes[-1]
    print "CLUSTER: Removing node %s" % dead_guy.name
    dead_guy.decommission()
    stash[:] = [nodes.pop()] + stash
    inject_hosts_files()
    print "CLUSTER: Node %s is removed" % dead_guy.name
    save_cluster()


def run_load_phase(record_count):
    """
    Runs the load phase on all the cluster clients with the right starting entry, count on each one
    :param record_count:
    """
    #first inject the hosts file
    host_text = ""
    for h in seeds+nodes: host_text += h.get_private_addr()+"\n"
    start = 0
    step = record_count/len(clients)
    for c in clients:
        load_command = "echo '%s' > /opt/hosts;" % host_text
        load_command += get_script_text("ycsb", "load") % (str(record_count), str(step), str(start), c.name[-1:])
        print "CLUSTER: running load phase on %s" % c.name
        c.run_command(load_command, silent=True)
        start += step


def run_sinusoid(target_total, offset_total, period):
    """
    Runs a sinusoidal workload on all the Client nodes of the cluster
    :param target_total: Total target ops/sec for all the cluster
    :param offset_total: total offset
    :param period: Period of the sinusoid
    """
    target = target_total / len(clients)
    offset = offset_total / len(clients)
    #first inject the hosts file
    host_text = ""
    for h in seeds+nodes: host_text += h.get_private_addr()+"\n"
    start = 0
    for c in clients:
        load_command = "echo '%s' > /opt/hosts;" % host_text
        load_command += get_script_text("ycsb", "run_sin") % (target, offset, period, c.name[-1:])
        print "CLUSTER: running workload on %s" % c.name
        c.run_command(load_command, silent=True)


def destroy_all():
    """
    Destroys all the VMs in the cluster (not the orchestrator)
    """
    for n in seeds+nodes+stash+clients:
        n.destroy()
    remove(save_file)


def get_hosts(include_clients=False, string=False, private=False):
    """
    Produces a mapping of hostname-->IP for the nodes in the cluster
    :param include_clients: if False (default) the clients are not included
    :param string: if True the output is a string able to be appended in /etc/hosts
    :return: a dict or a string of hostnames-->IPs
    """
    hosts = dict()
    all_nodes = seeds + nodes
    if include_clients:
        all_nodes += clients
    for i in all_nodes:
        if private:
            hosts[i.name] = i.get_private_addr()
        else:
            hosts[i.name] = i.get_public_addr()
    return hosts


def exists():
    if len(seeds+nodes) == 0:
        return False
    else:
        return True


def get_monitoring_endpoint():
    """
    returns the IP of the node that has gmetad
    """
    return seeds[0].get_public_addr(IPv4=True)


#=============================== MAIN ==========================


################ INIT actions ###########
find_orchestrator()
resume_cluster()
########################################



