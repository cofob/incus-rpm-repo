import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from releases import select, needs_build, version, main as release_main
from publish import publish, repo_file, verify_public
from prepare import go_version


def release(tag, name='', **kwargs):
    return dict(tag_name=tag, name=name, draft=False, prerelease=False, **kwargs)


class ReleaseTests(unittest.TestCase):
    def test_distribution_go_version(self):
        self.assertEqual(go_version('go1.26.7 (Red Hat 1.26.7-1.el10_2)'), (1, 26, 7))
        self.assertEqual(go_version('go1.25'), (1, 25, 0))
        with self.assertRaises(ValueError):
            go_version('devel go1.27')

    def test_numeric_sort_and_exclusions(self):
        data = [release('v7.9.0'), release('v7.10.0'), release('junk')]
        data += [dict(release('v8.0.0'), prerelease=True), dict(release('v9.0.0'), draft=True)]
        self.assertEqual(select(data, 'latest'), 'v7.10.0')

    def test_lts_rollover_and_unlabelled_patch(self):
        data = [release('v6.0.99', '6.0 LTS'), release('v7.0.0', '7.0 LTS'),
                release('v7.0.2'), release('v7.4.0')]
        self.assertEqual(select(data, 'lts'), 'v7.0.2')
        self.assertEqual(select(data + [release('v8.0.0', '8.0 LTS')], 'lts'), 'v8.0.0')

    def test_first_same_and_new(self):
        self.assertTrue(needs_build('v7.4.0', None))
        self.assertFalse(needs_build('v7.4.0', {'tag': 'v7.4.0'}))
        self.assertTrue(needs_build('v7.4.0', {'tag': 'v7.3.0'}))
        with self.assertRaises(ValueError):
            needs_build('v7.3.0', {'tag': 'v7.4.0'})
        with self.assertRaises(KeyError):
            needs_build('v7.4.0', {})

    def test_reject_shell_input(self):
        for tag in ['v7.4.0; echo bad', '../v7.4.0', 'v7.4.0\n', 'v7.4.0-rc1']:
            with self.assertRaises(ValueError):
                version(tag)


class DiscoveryTests(unittest.TestCase):
    def run_check(self, responses, extra=()):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'output'
            with patch('sys.argv', ['releases.py', '--channel', 'latest', *extra]), \
                 patch.dict('os.environ', {'GITHUB_OUTPUT': str(output)}), \
                 patch('releases.get_json', side_effect=responses) as fetch:
                release_main()
                return output.read_text(), fetch.call_count

    def test_all_pages_are_read(self):
        first = [release('v7.3.0')] * 100
        output, calls = self.run_check([first, [release('v7.4.0')], {'tag': 'v7.3.0'}])
        self.assertEqual(calls, 3)
        self.assertIn('tag=v7.4.0', output)
        self.assertIn('build=true', output)

    def test_missing_state_is_first_publication(self):
        missing = urllib.error.HTTPError('https://example.invalid', 404, 'missing', {}, None)
        self.addCleanup(missing.close)
        output, _ = self.run_check([[release('v7.4.0')], missing])
        self.assertIn('build=true', output)

    def test_access_error_is_not_empty_state(self):
        denied = urllib.error.HTTPError('https://example.invalid', 403, 'denied', {}, None)
        self.addCleanup(denied.close)
        with self.assertRaises(urllib.error.HTTPError):
            self.run_check([[release('v7.4.0')], denied])

    def test_build_only_does_not_read_public_state(self):
        output, calls = self.run_check([[release('v7.4.0')]], ['--build-only'])
        self.assertEqual(calls, 1)
        self.assertIn('build=true', output)


class PublicDownloadTests(unittest.TestCase):
    def test_identifies_client_and_checks_hash(self):
        with patch('publish.urllib.request.urlopen', return_value=io.BytesIO(b'rpm')) as fetch:
            verify_public('package.rpm', b'rpm')
        request = fetch.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'), 'incus-rpm-repo')

    @patch('publish.time.sleep')
    def test_http_failure_keeps_diagnostic(self, _sleep):
        denied = urllib.error.HTTPError('https://example.invalid', 403, 'Forbidden', {}, None)
        with patch('publish.urllib.request.urlopen', side_effect=denied) as fetch:
            with self.assertRaisesRegex(RuntimeError, '403: Forbidden'):
                verify_public('package.rpm', b'rpm')
        self.assertEqual(fetch.call_count, 6)

    @patch('publish.time.sleep')
    def test_wrong_content_is_rejected(self, _sleep):
        with patch('publish.urllib.request.urlopen', side_effect=lambda *_args, **_kwargs: io.BytesIO(b'bad')):
            with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch'):
                verify_public('package.rpm', b'rpm')


class FakeS3:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self):
        self.objects = {}
        self.writes = []

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey()
        return {'Body': io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, CacheControl):
        self.objects[Key] = Body
        self.writes.append(Key)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.snapshot = Path(self.temp.name)
        (self.snapshot / 'release.json').write_text(json.dumps({'tag': 'v7.4.0'}))
        (self.snapshot / 'rpm').write_bytes(b'rpm')
        self.s3 = FakeS3()

    def test_state_last_and_no_repeat(self):
        publish(self.s3, 'bucket', self.snapshot, 'latest', '1-1', lambda *_: None)
        self.assertEqual(self.s3.writes[-1], 'state/latest.json')
        writes = len(self.s3.writes)
        publish(self.s3, 'bucket', self.snapshot, 'latest', '2-1', lambda *_: None)
        self.assertEqual(len(self.s3.writes), writes)

    def test_failed_upload_preserves_channel_then_retry(self):
        self.s3.objects['channels/latest/el10/x86_64/mirrorlist'] = b'old'
        def fail(*_):
            raise RuntimeError('HTTP mismatch')
        with self.assertRaises(RuntimeError):
            publish(self.s3, 'bucket', self.snapshot, 'latest', '1-1', fail)
        self.assertEqual(self.s3.objects['channels/latest/el10/x86_64/mirrorlist'], b'old')
        self.assertNotIn('state/latest.json', self.s3.objects)
        publish(self.s3, 'bucket', self.snapshot, 'latest', '1-2', lambda *_: None)
        self.assertIn('state/latest.json', self.s3.objects)

    def test_retry_after_pointer_update(self):
        def fail(key, _):
            if key == 'channels/latest/el10/x86_64/mirrorlist':
                raise RuntimeError('Disconnected after PUT')
        with self.assertRaises(RuntimeError):
            publish(self.s3, 'bucket', self.snapshot, 'latest', '1-1', fail)
        self.assertNotIn('state/latest.json', self.s3.objects)
        publish(self.s3, 'bucket', self.snapshot, 'latest', '1-2', lambda *_: None)
        self.assertIn('state/latest.json', self.s3.objects)
        self.assertIn('snapshots/latest/v7.4.0/1-1/rpm', self.s3.objects)

    def test_stable_client_config(self):
        text = repo_file('lts')
        self.assertIn('mirrorlist=https://incusrpmrepo.cofob.dev/channels/lts/el10/$basearch/mirrorlist', text)
        self.assertIn('gpgcheck=1', text)
        self.assertIn('repo_gpgcheck=1', text)
        self.assertNotIn('snapshots/', text)


if __name__ == '__main__':
    unittest.main()
