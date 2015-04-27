#!/usr/bin/env python
from VM import VM, Timer, LOGS_DIR
from VM import get_all_vms
from Node import Node
from time import time, sleep
from lib import connector_eucalyptus as iaas
from pprint import pprint

#node = Node(cluster_name='hcluster', node_type='worker', create=True, wait=True)
#print node
#node.bootstrap()

#nodes = Node.get_all_nodes()
#for node in nodes: print node
#exit()

vm = VM.from_id('i-00000729')
node = Node(vm=vm)
print node
print vm
#node.startup()
#node.decommission()
#print node
exit()

hostnames = {"host1": "1.2.3.4", "host2": "4.3.2.1"}
print node.run_command("cat /etc/hosts");
print "--------------------------------------------------"

node.inject_hostnames(hostnames)
print node.run_command("cat /etc/hosts");
print "--------------------------------------------------"

node.inject_hostnames({}, delete="host1")
node.inject_hostnames({}, delete="host2")
print node.run_command("cat /etc/hosts");
print "--------------------------------------------------"

exit()

#vm = VM('test-vm', 'm1.small', 'dsarlis-master', create=True, wait=True)
#vm = VM('test-vm', 'm1.small', 'nchalv_worker_hadoop', create=True, wait=True)
#print vm

#exit()

#ids = iaas.get_all_vm_ids()
#for i in ids:
#    print i
#    pprint(iaas.get_vm_details(i))
#    pprint(iaas.get_addreses(i))
#    print ""

#details = iaas.get_vm_details('i-00000716')
#pprint(details)
#vm = VM.vm_from_dict(details)
#print vm

#vm = VM.from_id('i-00000719')
#print vm
#vm.run_command("mkdir testdir")
#vm.put_files('test.txt')
#vm.run_files('test.sh')
#vm.shutdown()
#sleep(10)
#print vm
#vm.startup()
#sleep(10)
#print vm

#vm = VM.from_id('i-00000716')
#vm.destroy()

#vms = get_all_vms()
#for vm in vms:
#    print vm
#    print "public address = " + str(vm.get_public_addr())
#    print "privates addresses = " + str(vm.get_private_addr())
#    print "status = " + str(vm.get_cloud_status())

