import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from profile_store import ProfileStore, write_json


class ProfileTests(unittest.TestCase):
    def test_failed_export_preserves_previous_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_json(root/'counter.json', {'deaths':[], 'reference_path':str(root/'missing.png')})
            store = ProfileStore(root)
            destination = root/'export.zip'
            destination.write_bytes(b'previous-export')
            with self.assertRaises(ValueError):
                store.export(destination)
            self.assertEqual(destination.read_bytes(), b'previous-export')

    def test_legacy_preserved_and_backed_up(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'counter.json'
            content = '{"deaths": [], "monitor_index": 2}'
            path.write_text(content)
            store = ProfileStore(folder)
            self.assertEqual(store.data_path(), path)
            self.assertEqual(path.read_text(), content)
            self.assertEqual((Path(folder)/'counter.before-profiles.json').read_text(), content)
            ident = store.create('Other game')
            store.activate(ident)
            self.assertEqual(ProfileStore(folder).active, ident)
            self.assertEqual(path.read_text(), content)

    def test_export_import_keeps_images_and_does_not_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root/'old.jpg'; image.write_bytes(b'image-data')
            ref = root/'ref.png'; ref.write_bytes(b'reference-data')
            data = {'deaths': [{'boss':'Boss', 'time':'2026-11-01T10:00:00+02:00', 'screenshots': {'before': {'path': str(image), 'time':'earlier'}, 'death':None}}], 'reference_path': str(ref), 'aliases': {'BOSS':'Boss'}, 'region': {'left':0,'top':0,'width':100,'height':50}}
            write_json(root/'counter.json', data)
            store = ProfileStore(root)
            archive = root/'export.zip'
            self.assertEqual(store.export(archive),0)
            ident = store.import_archive(archive)
            imported = json.loads(store.data_path(ident).read_text())
            self.assertEqual(Path(imported['reference_path']).read_bytes(),b'reference-data')
            self.assertEqual(Path(imported['deaths'][0]['screenshots']['before']['path']).read_bytes(),b'image-data')
            self.assertEqual(json.loads((root/'counter.json').read_text()),data)
            self.assertEqual(store.active,'legacy')

    def test_rejects_archive_paths_without_adding_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(folder)
            archive = Path(folder)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('profile.json',json.dumps({'version':1,'name':'Bad','data':{'deaths':[{'boss':'Boss','time':'now','screenshots':{'before':{'path':'../../escape'}}}]}}))
            with self.assertRaises(ValueError):
                store.import_archive(archive)
            self.assertEqual(len(store.state['profiles']),1)


if __name__ == '__main__':
    unittest.main()
