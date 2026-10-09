#!/usr/bin/env python3
"""Build the tested Rosetta loader detour locally; never distribute ntdll.dll."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ORIGINAL = '1b02dcf6ad9d9490870f1127a421c4c0d1471c65ec1574e1e84c05d69801ac7e'
PATCHED = 'e5ef486376a9c2cac9ff0cac8867c96a8c85f725174363f754b92ca23f6fab56'
ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ntdll', type=Path, default=Path('/Applications/CrossOver Preview.app/Contents/SharedSupport/CrossOver/lib/wine/x86_64-windows/ntdll.dll'))
    p.add_argument('--llvm-bin', type=Path, help='Directory containing ld.lld and llvm-objcopy')
    p.add_argument('--output', type=Path, default=ROOT / 'build')
    a = p.parse_args()
    if hashlib.sha256(a.ntdll.read_bytes()).hexdigest() != ORIGINAL:
        p.error('Unsupported ntdll: use the untouched x64 DLL from Preview 27.0.0.41069 (2026-10-06).')
    def tool(name):
        found = str(a.llvm_bin / name) if a.llvm_bin else shutil.which(name)
        if not found or not Path(found).is_file():
            p.error(f'Missing {name}; provide --llvm-bin or install LLVM.')
        return found
    linker, objcopy = tool('ld.lld'), tool('llvm-objcopy')
    src = ROOT / 'vendor/notproton-ntdll'
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    result = subprocess.check_output([sys.executable, str(src/'resolve.py'), '--sh', str(a.ntdll)], text=True)
    vals = {line.split('=',1)[0]: shlex.split(line.split('=',1)[1])[0] for line in result.splitlines()}
    c = (src/'detour.c').read_text().replace('typedef u32 (*', 'typedef u32 (__attribute__((ms_abi)) *')
    c = re.sub(r'^static (?=[^\n]*\()', 'static __attribute__((ms_abi)) ', c, flags=re.M)
    c = c.replace('void detour_build_module(', '__attribute__((ms_abi)) void detour_build_module(')
    (out/'detour.c').write_text(c)
    for name in ('shim.S','link.ld'): shutil.copyfile(src/name, out/name)
    def run(args): subprocess.run(args, cwd=out, check=True)
    run(['/usr/bin/clang','-target','x86_64-unknown-linux-gnu','-Os','-ffreestanding','-fno-stack-protector','-fno-asynchronous-unwind-tables','-c','detour.c','-o','detour.o'])
    opts = ['-DWM_REG='+vals['NP_WM'],'-DSCRATCH_REG='+vals['NP_SCRATCH'],'-DLOAD_PATH_SLOT='+vals['NP_LOAD_PATH'],'-DSTOLEN_BYTES='+vals['NP_STOLEN_BYTES']]
    run(['/usr/bin/clang','-target','x86_64-unknown-linux-gnu','-c','-x','assembler-with-cpp','shim.S','-o','shim.o', *opts])
    symbols = {'CAVE_VA':'NP_PAYLOAD_VA','BM_RESUME':'NP_RESUME_VA','LDR_GETDLLHANDLE':'NP_LDR_GET_DLL_HANDLE','LDR_LOADDLL':'NP_LDR_LOAD_DLL','NT_PROTECT':'NP_NT_PROTECT_VIRTUAL_MEMORY'}
    defs = [item for name,key in symbols.items() for item in ('--defsym', name+'='+vals[key])]
    run([linker,'-T','link.ld','shim.o','detour.o','-o','payload.elf', *defs])
    run([objcopy,'-O','binary','-j','.cave','payload.elf','payload.bin'])
    run([sys.executable,str(src/'apply.py'),str(a.ntdll.resolve()),str(out/'ntdll.dll'),str(out/'payload.bin')])
    digest = hashlib.sha256((out/'ntdll.dll').read_bytes()).hexdigest()
    print('Built local patched ntdll:', digest)
    print('Matches original working build:', digest == PATCHED)

if __name__ == '__main__': main()
