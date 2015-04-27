#!/usr/bin/env python
from pprint import pprint
from lib import connector_eucalyptus as iaas

#new_id = iaas.create_vm('test-vm', 'm1.medium', 'dsarlis-master', False, None)
new_id = iaas.create_vm('test-vm', 'm1.medium', 'nchalv_worker_hadoop', False, None)
#new_id = iaas.create_vm('test-vm', 'm1.small', 'Ubuntu 14.04.2 x64', False, None)
#print "new vm id: " + str(new_id)
#iaas.destroy_vm('i-000006b1')
#iaas.shutdown_vm('i-000006b1')
#iaas.startup_vm('i-000006b1')
#exit()

instances = iaas.describe_instances()
pprint(instances)
exit()

ids = iaas.get_all_vm_ids()
print "ids = " + str(ids)
for vm_id in ids:
    print vm_id + ":"
    print "details = " + str(iaas.get_vm_details(vm_id))
    print "status = " + str(iaas.get_vm_status(vm_id))
    print "addresses = " + str(iaas.get_addreses(vm_id))
    print ""
