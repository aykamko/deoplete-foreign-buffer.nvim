import subprocess
import os
import memcache
import time

from os import path as osp

from foreign_buffer import register_client, local_nvim_id
from .buffer import Source as BufferSource

MEMCACHED_SOCK_PATH = osp.join(os.getenv('TMPDIR'), 'foreign-buffer-memcache.sock')
CONNECT_SLEEP = 0.1
CONNECT_RETRIES = int(10 / CONNECT_SLEEP)


class _MemcachedBuffers:
    def __init__(self, mc_client):
        self.mc_client = mc_client

    def __contains__(self, item):
        return (local_nvim_id(), item) in self.get_bufnrs()

    def __setitem__(self, bufnr, value):
        self.update_bufnrs(bufnr)
        self.mc_client.set('buf_{}_{}'.format(local_nvim_id(), bufnr), value)

    def values(self):
        bufnrs = self.get_bufnrs()
        return (self.mc_client.get('buf_{}_{}'.format(nvim_id, bufnr))
                for nvim_id, bufnr in bufnrs if nvim_id != local_nvim_id())

    def get_bufnrs(self):
        return self.mc_client.get('bufnrs') or set()

    def update_bufnrs(self, bufnr):
        bufnrs = self.get_bufnrs().union({(local_nvim_id(), bufnr)})
        self.mc_client.set('bufnrs', bufnrs)
        return bufnrs


class Source(BufferSource):
    def __init__(self, vim):
        super().__init__(vim)

        self.name = 'foreign-buffer'
        self.mark = '[fB]'
        self.mc_client = self.connect_memcached()
        register_client(self.mc_client)
        self.__buffers = _MemcachedBuffers(self.mc_client)

    def connect_memcached(self):
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
        return client
