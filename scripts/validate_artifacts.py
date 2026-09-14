#!/usr/bin/env python3
"""Check the identity of downloaded RPMs before signing."""
import json
from pathlib import Path
import subprocess
import sys
from releases import version


def main(folder, tag):
    version(tag)
    folder = Path(folder)
    if json.loads((folder / 'release.json').read_text())['tag'] != tag:
        raise ValueError('Build release does not match selected release')
    names = set()
    source = False
    for path in folder.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError('Invalid artifact entry')
        if path.name == 'release.json':
            continue
        if path.suffix != '.rpm':
            raise ValueError('Unexpected artifact')
        name, ver, release, arch = subprocess.check_output(
            ['rpm', '-qp', '--qf', '%{NAME}\t%{VERSION}\t%{RELEASE}\t%{ARCH}', str(path)], text=True).split('\t')
        if not (name == 'incus' or name.startswith('incus-')) or ver != tag[1:] or release != '1.el10':
            raise ValueError('Unexpected RPM identity')
        if path.name.endswith('.src.rpm'):
            source = True
        elif arch not in ('x86_64', 'noarch'):
            raise ValueError('Unexpected RPM architecture')
        else:
            names.add(name)
    if not source or not {'incus', 'incus-client', 'incus-tools', 'incus-agent'} <= names:
        raise ValueError('Missing required packages')


if __name__ == '__main__':
    main(*sys.argv[1:])
