#!/usr/bin/env python3
"""Select stable releases. Only a missing state object means first publication."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

PUBLIC = 'https://incusrpmrepo.cofob.dev'
TAG = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')
RPM_RELEASE = json.loads((Path(__file__).resolve().parents[1] / 'packaging/provenance.json').read_text())['rpm_release']


def version(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f'Invalid release tag: {tag!r}')
    return tuple(map(int, match.groups()))


def select(releases, channel):
    stable = [r for r in releases if not r['draft'] and not r['prerelease']
              and TAG.fullmatch(r['tag_name'])]
    if channel == 'lts':
        # LTS series are identified by release titles, not assumed from x.0.
        series = {version(r['tag_name'])[:2] for r in stable
                  if re.search(r'\bLTS\b', r.get('name') or '', re.I)}
        if not series:
            raise ValueError('No upstream LTS series found')
        newest = max(series)
        stable = [r for r in stable if version(r['tag_name'])[:2] == newest]
    if not stable:
        raise ValueError('No stable release found')
    return max(stable, key=lambda r: version(r['tag_name']))['tag_name']


def get_json(url, token=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'incus-rpm-repo'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return json.load(response)


def needs_build(tag, state, rpm_release=RPM_RELEASE):
    if state is None:
        return True
    # A missing or malformed field is an error, not an empty repository.
    old = state['tag']
    if version(old) > version(tag):
        raise ValueError('Refusing a channel downgrade')
    previous_release = state.get('rpm_release', 1)
    if old == tag and previous_release > rpm_release:
        raise ValueError('Refusing a package release downgrade')
    return old != tag or previous_release != rpm_release


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', choices=['latest', 'lts'], required=True)
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    releases = []
    for page in range(1, 1001):
        batch = get_json(f'https://api.github.com/repos/lxc/incus/releases?per_page=100&page={page}',
                         os.environ.get('GH_TOKEN'))
        releases.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError('Release pagination limit reached')
    tag = select(releases, args.channel)
    state = None
    if not args.build_only:
        try:
            state = get_json(f'{PUBLIC}/state/{args.channel}.json')
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    build = args.build_only or needs_build(tag, state)
    print(json.dumps({'channel': args.channel, 'tag': tag, 'build': build}))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write(f'tag={tag}\nbuild={str(build).lower()}\n')


if __name__ == '__main__':
    main()
