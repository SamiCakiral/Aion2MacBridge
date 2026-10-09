#!/usr/bin/env python3
"""AION 2 Rosetta/native-Steam launcher. GPL-3.0; no credentials bundled."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

HOME = Path.home()
SUPPORT = HOME/'Library/Application Support'
ROOT = Path(__file__).resolve().parent
ORIGINAL = '1b02dcf6ad9d9490870f1127a421c4c0d1471c65ec1574e1e84c05d69801ac7e'
PATCHED = 'e5ef486376a9c2cac9ff0cac8867c96a8c85f725174363f754b92ca23f6fab56'
BRIDGE_FILES = ('steamclient.dll','steamclient64.dll','tier0_s64.dll','vstdlib_s64.dll','steam.exe','lsteamclient.dll')

def private_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    with os.fdopen(fd,'wb') as f: f.write(data)
    os.chmod(path,0o600)

def environment(a):
    e = os.environ.copy()
    e.update(WINEPREFIX=str(a.prefix), WINESERVER=str(a.runner/'bin/wineserver-x86'),
             CX_ROOT=str(a.runner), CX_HOME=str(SUPPORT/'CrossOver'), WINEMSYNC='0',
             WINEDEBUG='err+all,fixme-all', SteamAppId='3393110', SteamGameId='3393110',
             STEAM_COMPAT_APP_ID='3393110', STEAM_COMPAT_DATA_PATH=str(a.prefix.parent),
             STEAM_COMPAT_CLIENT_INSTALL_PATH=str(SUPPORT/'Steam/Steam.AppBundle/Steam/Contents/MacOS'),
             WINEDLLOVERRIDES='steamclient=n;steamclient64=n;lsteamclient=b')
    e.pop('DYLD_INSERT_LIBRARIES',None)
    e['STEAM_DYLD_INSERT_LIBRARIES']=''
    steam = a.prefix/'drive_c/Program Files (x86)/Steam'
    e['WINEDLLPATH']=':'.join(map(str,(steam,a.runner/'lib/wine/x86_64-windows',a.runner/'lib/wine/x86_64-unix')))
    return e

def paths(a):
    return (a.runner/'lib/wine/x86_64-windows/ntdll.dll', a.runner/'lib/wine/x86_64-unix/lsteamclient.so')

def restore(a):
    """Restore only artifacts for which a durable transaction exists."""
    marker = a.state/'runner-transaction.json'
    if not marker.exists(): return
    m=json.loads(marker.read_text()); pe,so=paths(a)
    if m['runner'] != str(a.runner.resolve()): raise RuntimeError('Recovery runner differs from the saved transaction.')
    shutil.copyfile(a.state/'original-ntdll.dll',pe)
    if m['had_so']: shutil.copyfile(a.state/'original-lsteamclient.so',so)
    else: so.unlink(missing_ok=True)
    marker.unlink()
    print('Original runner files restored.')

@contextlib.contextmanager
def staged(a):
    pe,so=paths(a)
    if (a.state/'runner-transaction.json').exists():
        raise RuntimeError('Unfinished transaction: close this game, then run recover before retrying.')
    if hashlib.sha256(pe.read_bytes()).hexdigest()!=ORIGINAL:
        raise RuntimeError('Runner x64 ntdll is not the supported original. Close other tests and restore it first.')
    if not a.patch.is_file(): raise RuntimeError('Build the patch first.')
    if hashlib.sha256(a.patch.read_bytes()).hexdigest()!=PATCHED:
        raise RuntimeError('Patch differs from the verified working build; check compiler versions.')
    for p in (a.bridge/'x86_64-unix/lsteamclient.so', *(a.bridge/n for n in BRIDGE_FILES)):
        if not p.is_file(): raise RuntimeError('Missing NotProton bridge file: '+str(p))
    private_write(a.state/'original-ntdll.dll',pe.read_bytes())
    if so.exists(): private_write(a.state/'original-lsteamclient.so',so.read_bytes())
    private_write(a.state/'runner-transaction.json',json.dumps({'runner':str(a.runner.resolve()),'had_so':so.exists()}).encode())
    try:
        shutil.copyfile(a.patch,pe)
        shutil.copyfile(a.bridge/'x86_64-unix/lsteamclient.so',so)
        yield
    finally:
        try: subprocess.run([str(a.runner/'bin/wineserver-x86'),'-k'],env=environment(a),timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        finally: restore(a)

def setup(a):
    if (a.prefix/'system.reg').exists():
        raise RuntimeError('Prefix already exists; setup refuses to overwrite it. Use launch instead.')
    a.prefix.mkdir(parents=True,exist_ok=True)
    with staged(a):
        log=a.state/'setup.private.log'; private_write(log,b'')
        with log.open('ab') as f:
            subprocess.run([str(a.runner/'lib/wine/x86_64-unix/wine'),'wineboot','--init'],env=environment(a),stdout=f,stderr=f,timeout=120,check=True)
        steam=a.prefix/'drive_c/Program Files (x86)/Steam'; steam.mkdir(parents=True,exist_ok=True)
        for n in BRIDGE_FILES: shutil.copyfile(a.bridge/n,steam/n)
        shutil.copyfile(a.bridge/'x86_64-unix/lsteamclient.so',steam/'lsteamclient.so')
        shutil.copyfile(a.patch,a.prefix/'drive_c/windows/system32/ntdll.dll')
    print('Dedicated prefix ready. No game files copied.')

def capture(a):
    run=SUPPORT/'Steam/compatibilitytools.d/notproton/run'
    if not run.is_file(): raise RuntimeError('Install NotProton and select its compatibility tool for AION 2 first.')
    backup=a.state/'steam-run.original'; marker=a.state/'capture-transaction.json'
    if marker.exists(): raise RuntimeError('Unfinished capture: run recover first.')
    original=run.read_bytes(); mode=run.stat().st_mode
    argsfile=a.state/'launch.private.json'; argsfile.unlink(missing_ok=True)
    private_write(backup,original)
    private_write(marker,json.dumps({'mode':mode}).encode())
    # Shell-quote paths, including spaces and apostrophes; never interpolate game arguments.
    cmd=' '.join(shlex.quote(s) for s in (sys.executable,str(ROOT/'bridge.py'),'record','--state',str(a.state)))
    preamble=('#!/bin/sh\ncase "$*" in *AION2.exe*) exec '+cmd+' -- "$@" ;; esac\n').encode()
    try:
        run.write_bytes(preamble+original); os.chmod(run,mode)
        subprocess.run(['open','steam://rungameid/3393110'],check=True)
        deadline=time.monotonic()+60
        while not argsfile.exists() and time.monotonic()<deadline: time.sleep(.25)
        if not argsfile.exists(): raise RuntimeError('Steam did not provide a launch. Check its window; stop any previous AION 2 launch and retry.')
        print('Fresh launch captured privately. Now run launch.')
    finally:
        run.write_bytes(original); os.chmod(run,mode); marker.unlink()

def launch(a):
    datafile=a.state/'launch.private.json'
    data=json.loads(datafile.read_text())
    if time.time()-data['time']>300: raise RuntimeError('Launch data expired; run capture again.')
    if not (a.prefix/'system.reg').exists(): raise RuntimeError('Run setup first.')
    argv=data['argv']; start=next(i for i,s in enumerate(argv) if s.lower().endswith('aion2.exe'))
    e=environment(a); e.update(data['env']); e.update(environment(a))
    # environment(a) restores our routing and removes injected Steam libraries.
    e.pop('DYLD_INSERT_LIBRARIES',None); e['STEAM_DYLD_INSERT_LIBRARIES']=''
    with staged(a):
        shutil.copyfile(a.patch,a.prefix/'drive_c/windows/system32/ntdll.dll')
        log=a.state/'game.private.log'; private_write(log,b'')
        with log.open('ab') as f:
            proc=subprocess.Popen([str(a.runner/'lib/wine/x86_64-unix/wine'),*argv[start:]],env=e,cwd=Path(argv[start]).parent,stdout=f,stderr=f)
            print('AION 2 launched through Rosetta. Leave this terminal open while playing.',flush=True)
            code=proc.wait()
        print('Game loader exited:',code)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('setup','capture','record','launch','recover'))
    p.add_argument('--runner',type=Path,default=SUPPORT/'notproton/runners/current')
    p.add_argument('--bridge',type=Path,default=SUPPORT/'notproton/bridge')
    p.add_argument('--prefix',type=Path,default=SUPPORT/'Aion2MacBridge/pfx')
    p.add_argument('--state',type=Path,default=SUPPORT/'Aion2MacBridge/state')
    p.add_argument('--patch',type=Path,default=ROOT/'build/ntdll.dll')
    # record receives the original Steam arguments unchanged after --.
    tokens=sys.argv[1:]; split=tokens.index('--') if '--' in tokens else len(tokens)
    a=p.parse_args(tokens[:split]); arguments=tokens[split+1:]
    for n in ('runner','bridge','prefix','state','patch'): setattr(a,n,getattr(a,n).expanduser().absolute())
    a.state.mkdir(parents=True,exist_ok=True,mode=0o700)
    if a.action=='record':
        selected={k:v for k,v in os.environ.items() if k.startswith('Steam') or k.startswith('STEAM_')}
        private_write(a.state/'launch.private.json',json.dumps({'time':time.time(),'argv':arguments,'env':selected}).encode()); return
    # One transaction per runner; different local checkouts cannot stage it concurrently.
    with (a.runner/'aion2macbridge.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='recover':
            marker=a.state/'capture-transaction.json'
            if marker.exists():
                m=json.loads(marker.read_text()); run=SUPPORT/'Steam/compatibilitytools.d/notproton/run'
                run.write_bytes((a.state/'steam-run.original').read_bytes()); os.chmod(run,m['mode']); marker.unlink()
                print('Original Steam compatibility script restored.')
            restore(a)
        else: {'setup':setup,'capture':capture,'launch':launch}[a.action](a)

if __name__=='__main__':
    def interrupted(signum,frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    try: main()
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError,StopIteration,KeyboardInterrupt) as exc:
        print('Stopped:',str(exc) or 'interrupted',file=sys.stderr); sys.exit(1)
