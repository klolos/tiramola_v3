import boto.ec2
import sys, os, time
import commands
from boto.ec2.connection import EC2Connection
import lib.persistance_module
from lib.persistance_module import *
from scp_utils import run_ssh_command


##retreive the EC2 credentials from the persistance module's env_vars
ec2_access_key = os.environ['EC2_ACCESS_KEY'] # env_vars['klolos_EC2_ACCESS_KEY']
ec2_secret_key = os.environ['EC2_SECRET_KEY'] # env_vars['klolos_EC2_SECRET_KEY']
ec2_key_name = env_vars["openstack_key_pair_name"]


# init the connection object requred to run euca2ools commands
region = boto.ec2.regioninfo.RegionInfo(name="nova", endpoint="termi7")
euca_connection = boto.connect_ec2(
                    aws_access_key_id=ec2_access_key,
                    aws_secret_access_key=ec2_secret_key,
                    is_secure=False, 
                    region=region, 
                    port=8773, 
                    path="/services/Cloud"
                  )


# all the attributes of an instance that we may find useful
usefull_attributes = ["id", "image_id", "public_dns_name", "private_dns_name", "dnsNameV6",
                            "state", "key_name", "ami_launch_index", "product_codes",
                            "instance_type", "launch_time", "placement", "kernel",
                            "ramdisk", "additional_info"]

## Mapping from EC2 states to Openstack states (includes only the states we check for in the VM class)
statemap = {"running": "ACTIVE", "shutoff": "STOPPED"}


def describe_instances(instance_ids=None, state=None):
    """
    helper function that acts as a wrapper for the "get_all_instances command"
    :param state: if defined, only returns the instances that are in the requred state
    :return: a map of instance_id -> details
    """
    instances = dict()
    reservations = euca_connection.get_all_instances(instance_ids)
    for reservation in reservations:
        for instance in reservation.instances:
            details = dict()
            for attr in usefull_attributes:
                #get the member value from the instance instance
                val = getattr(instance, attr, "")
                # add this attribute to the instance details
                details[attr] = val
            #add this intance's details to the instances list (check and filter if 'state' is not None
            if state and state != instance.state:
                continue
            else:
                instances[instance.id] = details
    return instances


def create_vm(name, flavor_id, image_id, IPv4, logger):
        assert IPv4 != True, "Attaching floating IP not implemented yet"
        if logger:
            logger.info("creating flavor %s, image %s" % (flavor_id, image_id))
        response = euca_connection.run_instances(
                     image_id = image_id, 
                     instance_type = flavor_id, 
                     additional_info = name, 
                     key_name = ec2_key_name
                   )

        ## add the newly run instances to the database
        created_instance = response.instances.pop()
        vm_id = created_instance.id
        openstack_names[vm_id] = name
        save_openstack_names()
        return vm_id


def get_all_vm_ids():
    ids = describe_instances().keys()

    new_names = {}

    for i in ids:
        if not i in openstack_names: continue
        new_names[i] = openstack_names[i]
    openstack_names.clear()
    openstack_names.update(new_names)
    save_openstack_names()
    return ids


def get_vm_details(vm_id):
    test_dict = describe_instances(instance_ids=[vm_id])[vm_id]
    name = openstack_names.get(vm_id, 'None')
    flavor_id = test_dict['instance_type']
    image_id = test_dict['image_id']
    return {'name': name, 'id': vm_id, 'flavor_id': flavor_id, 'image_id': image_id}


def get_vm_status(vm_id):
    di = describe_instances(instance_ids=[vm_id])
    if len(di) == 0:
        return "NONE"
    dict = di[vm_id]

    ec2_state = dict["state"]
    if ec2_state in statemap:
        return statemap[ec2_state]
    return ec2_state


def destroy_vm(vm_id):
    ids = [vm_id]
    euca_connection.terminate_instances(ids)


def shutdown_vm(vm_id):
    euca_connection.stop_instances([vm_id], force=True)


def startup_vm(vm_id):
    euca_connection.start_instances([vm_id])


def get_addreses(vm_id):
    info = describe_instances(instance_ids=[vm_id])[vm_id]
    rv = []
    if info["public_dns_name"]:  # public IPv4
        rv.append({'version': 4 , 'ip': info["public_dns_name"], 'type': 'fixed'})
    if info["private_dns_name"]: # private IPv4
        rv.append({'version': 4, 'ip': info["private_dns_name"], 'type': 'fixed'})
    if info["dnsNameV6"]:        # public IPv6
        rv.append({'version': 6, 'ip': info["dnsNameV6"], 'type': 'public'})
    return rv

