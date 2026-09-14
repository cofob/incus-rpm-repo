#!/usr/bin/env python3
"""Join verified, signed repositories without mixing architectures or SRPMs."""
import json
from pathlib import Path
import shutil
import sys

ARCHITECTURES = ('x86_64', 'aarch64')


def main(signed, output):
    signed, output = Path(signed), Path(output)
    releases = []
    for arch in ARCHITECTURES:
        release = json.loads((signed / arch / 'release.json').read_text())
        if release.pop('architecture') != arch:
            raise ValueError('Signed build architecture mismatch')
        releases.append(release)
        for repo in (arch, 'SRPMS'):
            for filename in ('repomd.xml', 'repomd.xml.asc'):
                if not (signed / arch / repo / 'repodata' / filename).is_file():
                    raise ValueError('Missing signed repository metadata')
    if releases[0] != releases[1]:
        raise ValueError('Architecture builds have different release identities')
    output.mkdir(parents=True, exist_ok=False)
    for arch in ARCHITECTURES:
        shutil.copytree(signed / arch / arch, output / arch)
        shutil.copytree(signed / arch / 'SRPMS', output / 'SRPMS' / arch)
    (output / 'release.json').write_text(json.dumps({**releases[0], 'architectures': list(ARCHITECTURES)}) + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:])
