"""Transaction and privacy checks, without starting Steam or touching CrossOver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.a=argparse.Namespace(runner=self.root/'runner',bridge=self.root/'bridge',prefix=self.root/'pfx',state=self.root/'state',patch=self.root/'patch.dll')
        self.a.state.mkdir(); self.a.bridge.mkdir(); self.a.patch.write_bytes(b'patched')
        self.pe,self.so=bridge.paths(self.a)
        self.pe.parent.mkdir(parents=True); self.so.parent.mkdir(parents=True)
        self.pe.write_bytes(b'original'); self.so.write_bytes(b'old-so')
        for n in bridge.BRIDGE_FILES: (self.a.bridge/n).write_bytes(b'shim')
        (self.a.bridge/'x86_64-unix').mkdir()
        (self.a.bridge/'x86_64-unix/lsteamclient.so').write_bytes(b'new-so')

    def test_exception_restores_runner_and_preserves_recovery_backup(self):
        with patch.object(bridge,'ORIGINAL',hashlib.sha256(b'original').hexdigest()), patch.object(bridge,'PATCHED',hashlib.sha256(b'patched').hexdigest()), patch.object(bridge.subprocess,'run'):
            with self.assertRaisesRegex(RuntimeError,'simulated failure'):
                with bridge.staged(self.a):
                    self.assertEqual(self.pe.read_bytes(),b'patched')
                    raise RuntimeError('simulated failure')
        self.assertEqual(self.pe.read_bytes(),b'original')
        self.assertEqual(self.so.read_bytes(),b'old-so')
        self.assertFalse((self.a.state/'runner-transaction.json').exists())
        self.assertEqual((self.a.state/'original-ntdll.dll').read_bytes(),b'original')

    def test_recovery_from_durable_transaction(self):
        bridge.private_write(self.a.state/'original-ntdll.dll',b'original')
        bridge.private_write(self.a.state/'runner-transaction.json',json.dumps({'runner':str(self.a.runner.resolve()),'had_so':False}).encode())
        self.pe.write_bytes(b'patched')
        bridge.restore(self.a)
        self.assertEqual(self.pe.read_bytes(),b'original')
        self.assertFalse(self.so.exists())

    def test_private_files_remain_private_when_overwriting_existing_file(self):
        p=self.a.state/'launch.private.json'; p.write_bytes(b'old'); p.chmod(0o644)
        bridge.private_write(p,b'new')
        self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_capture_restores_steam_script_when_launch_request_fails(self):
        run=self.root/'Steam/compatibilitytools.d/notproton/run'; run.parent.mkdir(parents=True)
        original=b'#!/bin/sh\necho original\n'; run.write_bytes(original); run.chmod(0o755)
        with patch.object(bridge,'SUPPORT',self.root), patch.object(bridge.subprocess,'run',side_effect=RuntimeError('Steam failure')):
            with self.assertRaisesRegex(RuntimeError,'Steam failure'): bridge.capture(self.a)
        self.assertEqual(run.read_bytes(),original)
        self.assertEqual(run.stat().st_mode & 0o777,0o755)
        self.assertFalse((self.a.state/'capture-transaction.json').exists())

    def test_setup_refuses_existing_prefix_before_any_mutation(self):
        self.a.prefix.mkdir(); (self.a.prefix/'system.reg').write_text('keep')
        with self.assertRaisesRegex(RuntimeError,'already exists'): bridge.setup(self.a)
        self.assertEqual(self.pe.read_bytes(),b'original')


if __name__=='__main__': unittest.main()
