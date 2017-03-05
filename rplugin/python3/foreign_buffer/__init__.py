import neovim
import memcache
import os

from os import path as osp
from functools import lru_cache

memoized = lru_cache(maxsize=None)
MEMCACHED_SOCK_PATH = osp.join(os.getenv('TMPDIR'), 'foreign-buffer-memcache.sock')


@memoized
def local_nvim_id():
    return os.getenv('NVIM_LISTEN_ADDRESS')


def register_client(client):
    '''register this neovim client with memcached'''
    nvim_clients = (client.get('nvim_clients') or set()).union({local_nvim_id()})
    client.set('nvim_clients', nvim_clients)


def unregister_client(client):
    nvim_clients = client.get('nvim_clients')
    if not nvim_clients:
        return  # TODO: error
    nvim_clients.remove(local_nvim_id())
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
