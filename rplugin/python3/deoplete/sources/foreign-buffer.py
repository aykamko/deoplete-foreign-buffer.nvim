from foreign_buffer import create_registered_client, LOCAL_NVIM_ID
from .buffer import Source as BufferSource


class Source(BufferSource):
    def __init__(self, vim):
        super().__init__(vim)

        self.name = 'foreign-buffer'
        self.mark = '[fB]'
        self.mc_client = create_registered_client()
        self.__buffers = _MemcachedBuffers(self.mc_client)


def buf_id(nvim_id, bufnr):
    return 'buf_{}_{}'.format(nvim_id, bufnr)


class _MemcachedBuffers:
    def __init__(self, mc_client):
        self.mc_client = mc_client

    def __contains__(self, bufnr):
        return (LOCAL_NVIM_ID, bufnr) in self.get_bufnrs()

    def __setitem__(self, bufnr, value):
        self.update_bufnrs(bufnr)
        self.mc_client.set(buf_id(LOCAL_NVIM_ID, bufnr), value)

    def values(self):
        return (self.mc_client.get(buf_id(nvim_id, bufnr))
                for nvim_id, bufnr in self.get_bufnrs() if nvim_id != LOCAL_NVIM_ID)

    def get_bufnrs(self):
        return self.mc_client.get('bufnrs') or set()

    def update_bufnrs(self, bufnr):
        new_bufnrs = self.get_bufnrs().union({(LOCAL_NVIM_ID, bufnr)})
        self.mc_client.set('bufnrs', new_bufnrs)
        return new_bufnrs
