import neovim
import memcache
import os
import subprocess
import time

from os import path as osp

LOCAL_NVIM_ID = os.getenv('NVIM_LISTEN_ADDRESS')
MEMCACHED_SOCK_PATH = osp.join(os.getenv('TMPDIR'), 'foreign-buffer-memcache.sock')
CONNECT_SLEEP = 0.1
CONNECT_RETRIES = int(10 / CONNECT_SLEEP)


def create_registered_client():
    if not osp.exists(MEMCACHED_SOCK_PATH):
        subprocess.call(['memcached', '-A', '-d', '-s', MEMCACHED_SOCK_PATH])
    client = memcache.Client(['unix:%s' % (MEMCACHED_SOCK_PATH)],
                             socket_timeout=10)
    for _ in range(CONNECT_RETRIES):
        success = client.servers[0].connect()
        if success == 1:
            break
        client.forget_dead_hosts()
        time.sleep(CONNECT_SLEEP)
        # TODO: else, fail
    register_client(client)
    return client


def register_client(client):
    '''
    Register this neovim client with memcached.
    '''
    nvim_clients = (client.get('nvim_clients') or set()).union({LOCAL_NVIM_ID})
    client.set('nvim_clients', nvim_clients)


def unregister_client(client):
    '''
    Unregister this neovim client with memcached,
    shut down memcached if last exiting client.
    '''
    nvim_clients = client.get('nvim_clients')
    if not nvim_clients:
        return  # TODO: error

    try:
        nvim_clients.remove(LOCAL_NVIM_ID)
    except KeyError:  # happens when we exit nvim before we're even able to register
        pass

    if not nvim_clients or not len(nvim_clients):
        # we're the last nvim client to exit so we kill memcached too
        client.servers[0].send_cmd('shutdown')
        os.remove(MEMCACHED_SOCK_PATH)
        return

    client.set('nvim_clients', nvim_clients)


@neovim.plugin
class ForeignBuffer:
    def __init__(self, vim):
        self.vim = vim

    @neovim.autocmd('VimLeave')
    def _unregister_client(self):
        client = memcache.Client(['unix:%s' % (MEMCACHED_SOCK_PATH)])
        if client.servers[0].connect() != 1:
            return
        unregister_client(client)
