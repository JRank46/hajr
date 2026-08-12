#!/usr/bin/env python3
"""
syncPvCharge.py

Synchronises PV charge-related files from local repo to Home Assistant OS either via SSH or a Samba share.

Usage:
  python syncPvCharge.py --mode ssh --host 192.168.2.125 --user root --key /path/to/id_rsa
  python syncPvCharge.py --mode ssh --host 192.168.2.125 --user root --password SECRET
  python syncPvCharge.py --mode samba --share "\\\\192.168.2.125\\config" --dry-run

Environment variables supported:
  HA_SSH_KEY  - path to private key file
  HA_PASSWORD - password for SSH (if not using key)

This script compares SHA256 checksums and copies files that differ or are missing on the HA host.
"""

import argparse
import hashlib
import os
import sys
import posixpath
import getpass
import shutil
from pathlib import Path
from datetime import datetime

try:
    import paramiko
except ImportError:
    paramiko = None

FILES = [
    'automations/pv_charging_schedule.yaml',
    'scripts/pv_daily_charge_handler.yaml',
    'scripts/pv_adhoc_charge_handler.yaml',
    'helpers/input_number.yaml',
    'helpers/input_datetime.yaml',
    'helpers/input_boolean.yaml',
    'helpers/input_select.yaml',
    'dashboards/pv_charging_dashboard.yaml',
    'dashboards/resources.yaml',
    'sensors/pv_charge_estimates.yaml',
    'configuration_example.yaml',
    'README.md',
    'Spezifikation_PV_Ueberschussladen.txt'
]

REMOTE_BASE = '/config'
CHUNK_SIZE = 32768

# simple logger function variable - reassigned in main to write to file
LOG_WRITE = print


def sha256_local(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_remote(sftp, rpath):
    h = hashlib.sha256()
    try:
        with sftp.open(rpath, 'rb') as rf:
            while True:
                chunk = rf.read(CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except IOError:
        return None


def sha256_path(path):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as rf:
            while True:
                chunk = rf.read(CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except IOError:
        return None


def ensure_samba_dirs(remote_path):
    """Create parent directories on a Samba share path if needed."""
    parent = os.path.dirname(remote_path)
    if not parent:
        return
    os.makedirs(parent, exist_ok=True)
    LOG_WRITE(f'Ensured remote Samba path: {parent}')


def ensure_remote_dirs(sftp, remote_path):
    """Ensure that remote directory exists (mkdir -p behaviour)."""
    dirname = posixpath.dirname(remote_path)
    if dirname == '' or dirname == '/':
        return
    parts = dirname.split('/')
    cur = ''
    for p in parts:
        if p == '':
            cur = '/'
            continue
        cur = posixpath.join(cur, p) if cur != '/' else '/' + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
                LOG_WRITE(f'Created remote dir: {cur}')
            except Exception as e:
                LOG_WRITE(f'Failed to create remote dir {cur}: {e}')


def upload_file_ssh(sftp, local, remote, dry_run=False):
    ensure_remote_dirs(sftp, remote)
    if dry_run:
        LOG_WRITE(f'[DRY-RUN] Would upload: {local} -> {remote}')
        return True
    try:
        sftp.put(local, remote)
        LOG_WRITE(f'Uploaded: {local} -> {remote}')
        return True
    except Exception as e:
        LOG_WRITE(f'Failed upload {local} -> {remote}: {e}')
        return False


def upload_file_samba(local, remote, dry_run=False):
    ensure_samba_dirs(remote)
    if dry_run:
        LOG_WRITE(f'[DRY-RUN] Would copy: {local} -> {remote}')
        return True
    try:
        shutil.copy2(local, remote)
        LOG_WRITE(f'Copied: {local} -> {remote}')
        return True
    except Exception as e:
        LOG_WRITE(f'Failed copy {local} -> {remote}: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='Sync PV charging files to Home Assistant')
    parser.add_argument('--mode', choices=['ssh', 'samba'], default='ssh', help='Transfer mode: ssh or samba')
    parser.add_argument('--host', help='Home Assistant host (IP or hostname) for SSH mode')
    parser.add_argument('--share', help='UNC share path for Samba mode, e.g. \\\\192.168.2.125\\config')
    parser.add_argument('--user', default='root', help='SSH user (default: root)')
    parser.add_argument('--key', help='Path to private key file (optional)')
    parser.add_argument('--password', help='SSH password (optional)')
    parser.add_argument('--local-root', default='.', help='Local repo root (default: current directory)')
    parser.add_argument('--remote-base', default=REMOTE_BASE, help='Remote HA config base (default: /config)')
    parser.add_argument('--dry-run', action='store_true', help='Do not upload, only compare')
    args = parser.parse_args()

    if args.mode == 'ssh' and not paramiko:
        print("SSH mode requires paramiko. Install it with: pip install -r requirements.txt")
        sys.exit(2)

    if args.mode == 'ssh' and not args.host:
        parser.error('--host is required for ssh mode')

    if args.mode == 'samba' and not args.share:
        parser.error('--share is required for samba mode')

    local_root = os.path.abspath(args.local_root)
    transfer_mode = args.mode
    remote_base = args.remote_base
    log_info = []

    if transfer_mode == 'ssh':
        host = args.host
        user = args.user
        key = args.key or os.environ.get('HA_SSH_KEY')
        password = args.password or os.environ.get('HA_PASSWORD')

        if not key and not password:
            password = getpass.getpass(f'Password for {user}@{host}: ')

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        pkey = None
        if key:
            try:
                pkey = paramiko.RSAKey.from_private_key_file(os.path.expanduser(key))
            except Exception as e:
                try:
                    pkey = paramiko.Ed25519Key.from_private_key_file(os.path.expanduser(key))
                except Exception:
                    print(f'Failed to load private key {key}: {e}')
                    sys.exit(3)

        try:
            if pkey:
                ssh.connect(hostname=host, username=user, pkey=pkey, timeout=10)
            else:
                ssh.connect(hostname=host, username=user, password=password, timeout=10)
        except Exception as e:
            print(f'Failed to connect to {host}: {e}')
            sys.exit(4)

        sftp = ssh.open_sftp()
    else:
        share_path = os.path.normpath(args.share)
        if not os.path.isdir(share_path):
            print(f'Samba share path not found: {share_path}')
            sys.exit(5)
        sftp = None

    # prepare logging
    script_dir = Path(__file__).parent
    logs_dir = script_dir / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = logs_dir / f'sync_{ts}.log'
    log_fh = open(log_path, 'a', encoding='utf-8')

    def _log(msg: str):
        now = datetime.now().isoformat(sep=' ', timespec='seconds')
        line = f'[{now}] {msg}'
        print(line)
        try:
            log_fh.write(line + '\n')
            log_fh.flush()
        except Exception:
            pass

    global LOG_WRITE
    LOG_WRITE = _log

    LOG_WRITE(f'Start sync mode={transfer_mode} local_root={local_root} remote_base={remote_base}')
    if transfer_mode == 'ssh':
        LOG_WRITE(f'SSH host={host} user={user}')
    else:
        LOG_WRITE(f'Samba share={share_path}')

    summary = {'checked': 0, 'uploaded': 0, 'skipped': 0, 'missing_local': 0}

    for rel in FILES:
        local_path = os.path.join(local_root, rel)
        if transfer_mode == 'ssh':
            remote_path = posixpath.join(remote_base, rel.replace('\\', '/'))
        else:
            remote_path = os.path.join(share_path, rel.replace('/', os.sep))

        summary['checked'] += 1

        if not os.path.exists(local_path):
            LOG_WRITE(f'Local file missing, skipping: {local_path}')
            summary['missing_local'] += 1
            continue

        local_hash = sha256_local(local_path)

        if transfer_mode == 'ssh':
            remote_hash = sha256_remote(sftp, remote_path)
        else:
            remote_hash = sha256_path(remote_path)

        LOG_WRITE(f'Checking: {rel} local_hash={local_hash} remote_hash={remote_hash}')

        if remote_hash is None:
            LOG_WRITE(f'Remote missing: {remote_path} — will upload')
            if transfer_mode == 'ssh':
                ok = upload_file_ssh(sftp, local_path, remote_path, dry_run=args.dry_run)
            else:
                ok = upload_file_samba(local_path, remote_path, dry_run=args.dry_run)
            if ok:
                summary['uploaded'] += 1
            continue

        if local_hash != remote_hash:
            LOG_WRITE(f'File changed: {rel} — uploading')
            if transfer_mode == 'ssh':
                ok = upload_file_ssh(sftp, local_path, remote_path, dry_run=args.dry_run)
            else:
                ok = upload_file_samba(local_path, remote_path, dry_run=args.dry_run)
            if ok:
                summary['uploaded'] += 1
        else:
            LOG_WRITE(f'Up-to-date: {rel}')
            summary['skipped'] += 1

    if transfer_mode == 'ssh':
        sftp.close()
        ssh.close()

    LOG_WRITE('\nSummary:')
    LOG_WRITE(f"Checked: {summary['checked']}")
    LOG_WRITE(f"Uploaded: {summary['uploaded']}")
    LOG_WRITE(f"Skipped (up-to-date): {summary['skipped']}")
    LOG_WRITE(f"Missing local files: {summary['missing_local']}")

    try:
        log_fh.close()
    except Exception:
        pass

    return 0


if __name__ == '__main__':
    sys.exit(main())
