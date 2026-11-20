import os
import sys
import tempfile
from gltest.direct.sdk_loader import setup_sdk_paths
import gltest.direct.loader
import gltest.direct.vm

# Initialize SDK paths so tests can import Address, u256, etc.
setup_sdk_paths()


def patched_inject_message_to_fd0(vm):
    try:
        from genlayer.py import calldata
        from genlayer.py.types import Address
    except ImportError:
        return

    sender_addr = vm.sender
    if isinstance(sender_addr, bytes):
        sender_addr = Address(sender_addr)

    contract_addr = vm._contract_address
    if isinstance(contract_addr, bytes):
        contract_addr = Address(contract_addr)

    origin_addr = vm.origin
    if isinstance(origin_addr, bytes):
        origin_addr = Address(origin_addr)

    message_data = {
        'contract_address': contract_addr,
        'sender_address': sender_addr,
        'origin_address': origin_addr,
        'stack': [],
        'value': vm._value,
        'datetime': vm._datetime,
        'is_init': False,
        'chain_id': vm._chain_id,
        'entry_kind': 0,
        'entry_data': b'',
        'entry_stage_data': None,
    }

    encoded = calldata.encode(message_data)
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, encoded)
        os.lseek(fd, 0, os.SEEK_SET)
        original_stdin = os.dup(0)
        vm._original_stdin_fd = original_stdin
        os.dup2(fd, 0)
    finally:
        os.close(fd)
        try:
            os.unlink(path)
        except Exception:
            pass


gltest.direct.loader._inject_message_to_fd0 = patched_inject_message_to_fd0

original_refresh = gltest.direct.vm.VMContext._refresh_gl_message


def patched_refresh(self):
    original_refresh(self)
    if 'genlayer.gl' in sys.modules:
        gl = sys.modules['genlayer.gl']
        if hasattr(gl, 'message_raw') and gl.message_raw is not None:
            gl.message_raw['datetime'] = self._datetime
            gl.message_raw['value'] = self._value


gltest.direct.vm.VMContext._refresh_gl_message = patched_refresh
