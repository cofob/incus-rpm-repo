import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_snapshot import main, ARCHITECTURES


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.signed = self.root / 'signed'
        self.output = self.root / 'snapshot'
        for arch in ARCHITECTURES:
            for repo in (arch, 'SRPMS'):
                path = self.signed / arch / repo
                (path / 'repodata').mkdir(parents=True)
                for filename in ('repomd.xml', 'repomd.xml.asc'):
                    (path / 'repodata' / filename).write_text(arch)
                (path / 'Packages').mkdir()
                (path / 'Packages/identical-name.rpm').write_text(arch)
            (self.signed / arch / 'release.json').write_text(json.dumps({
                'tag': 'v7.4.0', 'rpm_release': 3, 'source_sha256': 'same',
                'architecture': arch}))

    def test_source_rpms_are_not_overwritten(self):
        main(self.signed, self.output)
        for arch in ARCHITECTURES:
            self.assertEqual((self.output / 'SRPMS' / arch / 'Packages/identical-name.rpm').read_text(), arch)
        self.assertEqual(json.loads((self.output / 'release.json').read_text())['architectures'], list(ARCHITECTURES))

    def test_missing_architecture_fails_before_copy(self):
        (self.signed / 'aarch64/release.json').unlink()
        with self.assertRaises(FileNotFoundError):
            main(self.signed, self.output)
        self.assertFalse(self.output.exists())

    def test_mismatched_sources_fail_before_copy(self):
        path = self.signed / 'aarch64/release.json'
        info = json.loads(path.read_text())
        info['source_sha256'] = 'different'
        path.write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError, 'different release'):
            main(self.signed, self.output)
        self.assertFalse(self.output.exists())
