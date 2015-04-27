__author__ = 'cmantas'
from kamaki.clients import ClientError
from kamaki.clients.astakos import AstakosClient
from kamaki.clients.astakos import getLogger
from kamaki.clients.cyclades import CycladesClient, CycladesNetworkClient
#http://www.synnefo.org/docs/kamaki/latest/developers/code.html#the-client-api-ref
from sys import stderr
from os.path import abspath
from base64 import b64encode
from lib.persistance_module import *
from logging import ERROR

USER = "cmantas"

#retrieve the credentials for the specified users
AUTHENTICATION_URL, TOKEN = get_credentials(USER)

synnefo_user = AstakosClient(AUTHENTICATION_URL, TOKEN)
synnefo_user.logger.setLevel(ERROR)
getLogger().setLevel(ERROR)

cyclades_endpoints = synnefo_user.get_service_endpoints("compute")
CYCLADES_URL = cyclades_endpoints['publicURL']
cyclades_client = CycladesClient(CYCLADES_URL, TOKEN)
cyclades_net_client = CycladesNetworkClient(CYCLADES_URL, TOKEN)


pub_keys_path = 'keys/just_a_key.pub'
priv_keys_path = 'keys/just_a_key'


#creates a "personality"
def personality(username):
    """
    :param pub_keys_path: a path to the public key(s) to be used for this personality
    :param ssh_keys_path: a path to the private key(s) to be used for this personality
    """
    personality = []
    with open(abspath(pub_keys_path)) as f:
        personality.append(dict(
            contents=b64encode(f.read()),
            path='/root/.ssh/authorized_keys',
            owner='root', group='root', mode=0600))
        personality.append(dict(
            contents=b64encode('StrictHostKeyChecking no'),
            path='/root/.ssh/config',
            owner='root', group='root', mode=0600))
    return personality


def get_addreses(vm_id):
    nics = cyclades_client.get_server_nics(vm_id)
    addresses = nics["addresses"]
    rv = []
    for a in addresses:
        for addr in addresses[a]:
            rv.append({'version': addr['version'], 'ip': addr['addr'], 'type': addr['OS-EXT-IPS:type']})
    kati = cyclades_client.servers_ips_get(vm_id)
    return rv


def create_vm(name, flavor_id, image_id, IPv4, logger):
    """
    Creates this VM in the okeanos through kamaki
    """
    networks = [{'uuid': env_vars['cassandra_network_id']}]
    if IPv4: networks.append({'uuid': 2216})
    vm_id = -1
    try:
        logger.info("creating flavor %s, image %s" % (flavor_id, image_id))
        my_dict = cyclades_client.create_server(name, flavor_id, image_id, personality=personality('root'),
                                                networks=networks)
        vm_id = my_dict['id']

    except ClientError as e:
        logger.error("failed to create server with kamaki")
        logger.error(e)
        # print('Error: %s' % e)
        # if e.status:
        #     print('- error code: %s' % e.status)
        # if e.details:
        #     for detail in e.details:
        #         print('- %s' % detail)
        raise Exception("Failed creating server")
    return vm_id


def get_vm_status(vm_id):
    return cyclades_client.wait_server(vm_id)


def shutdown_vm(vm_id):
    cyclades_client.shutdown_server(vm_id)


def startup_vm(vm_id):
    resp = cyclades_client.start_server(vm_id)
    new_status = cyclades_client.wait_server(vm_id)
    if new_status == "ACTIVE": return True
    else: return False


def destroy_vm(vm_id):
    cyclades_client.delete_server(vm_id)


def get_vm_details(vm_id):
    synnefo_dict = cyclades_client.get_server_details(vm_id)
    name = synnefo_dict['name']
    vm_id = synnefo_dict['id']
    flavor_id = synnefo_dict['flavor']['id']
    image_id = synnefo_dict['image']['id']
    return {'name': name, 'id':vm_id, 'flavor_id': flavor_id, 'image_id': image_id}


def get_all_vm_ids():
    vm_ids=[]
    vm_list = cyclades_client.list_servers()
    for v in vm_list: vm_ids.append(v['id'])
    return vm_ids

