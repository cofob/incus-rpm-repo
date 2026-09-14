#!/usr/bin/env python3
"""Upload a complete snapshot, verify it over HTTPS, then move mirrorlists."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from releases import PUBLIC, version, needs_build

ROOT = Path(__file__).resolve().parents[1]


def repo_file(channel):
    sections = []
    for suffix, arch, enabled in (('', '$basearch', 1), ('-source', 'SRPMS', 0)):
        sections.append(f'''[incus-{channel}{suffix}]
name=Incus {channel} EL10{suffix}
mirrorlist={PUBLIC}/channels/{channel}/el10/{arch}/mirrorlist
gpgcheck=1
repo_gpgcheck=1
gpgkey={PUBLIC}/RPM-GPG-KEY-incus
enabled={enabled}
metadata_expire=1h
priority=50
''')
    return '\n'.join(sections)


def verify_public(key, expected):
    # A short cache delay is allowed; never accept a different object.
    request = urllib.request.Request(f'{PUBLIC}/{key}', headers={'User-Agent': 'incus-rpm-repo'})
    last_error = 'SHA-256 mismatch'
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                actual = hashlib.file_digest(response, 'sha256').hexdigest()
            if actual == hashlib.sha256(expected).hexdigest():
                return
            last_error = 'SHA-256 mismatch'
        except urllib.error.HTTPError as error:
            last_error = str(error)
            error.close()
        except OSError as error:
            last_error = str(error)
        if attempt < 5:
            time.sleep(5)
    raise RuntimeError(f'Public verification failed: {key}: {last_error}')


def publish(s3, bucket, snapshot, channel, run, verify=verify_public):
    release = json.loads((snapshot / 'release.json').read_text())
    version(release['tag'])
    state_key = f'state/{channel}.json'
    try:
        previous = json.loads(s3.get_object(Bucket=bucket, Key=state_key)['Body'].read())
    except s3.exceptions.NoSuchKey:
        previous = None
    if not needs_build(release['tag'], previous):
        print('Release already published; no change')
        return
    prefix = f'snapshots/{channel}/{release["tag"]}/{run}'

    def put(key, content, mutable=False):
        s3.put_object(Bucket=bucket, Key=key, Body=content,
                      CacheControl='no-cache, max-age=0' if mutable else 'public, max-age=31536000, immutable')
        verify(key, content)

    for path in sorted(snapshot.rglob('*')):
        if path.is_file():
            if path.is_symlink():
                raise ValueError('Symlink in snapshot')
            put(f'{prefix}/{path.relative_to(snapshot).as_posix()}', path.read_bytes())
    put('RPM-GPG-KEY-incus', (ROOT / 'keys/repository.asc').read_bytes(), True)
    put(f'incus-{channel}.repo', repo_file(channel).encode(), True)
    # Each mirrorlist changes in one S3 PUT. Old metadata and RPMs remain valid.
    for arch in ('SRPMS', 'x86_64'):
        put(f'channels/{channel}/el10/{arch}/mirrorlist',
            f'{PUBLIC}/{prefix}/{arch}/\n'.encode(), True)
    state = {**release, 'snapshot': prefix}
    put(state_key, (json.dumps(state) + '\n').encode(), True)


def main():
    import boto3
    from botocore.config import Config
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', required=True, choices=['latest', 'lts'])
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    run = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not re.fullmatch(r'\d+-\d+', run):
        raise ValueError('Invalid run identifier')
    s3 = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT_URL'], region_name=os.environ['AWS_REGION'],
                      config=Config(s3={'addressing_style': 'path'}, retries={'max_attempts': 5},
                                    request_checksum_calculation='when_required', response_checksum_validation='when_required'))
    publish(s3, os.environ['S3_BUCKET_NAME'], args.snapshot, args.channel, run)


if __name__ == '__main__':
    main()
