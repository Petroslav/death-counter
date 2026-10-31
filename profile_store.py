"""Independent game profiles; legacy data stays in place and exports are portable."""
import copy
import json
from pathlib import Path
import shutil
import uuid
import zipfile


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temp.replace(path)


class ProfileStore:
    def __init__(self, root):
        self.root = Path(root)
        self.index = self.root / 'profiles.json'
        if self.index.exists():
            self.state = json.loads(self.index.read_text(encoding='utf-8'))
        else:
            legacy = self.root / 'counter.json'
            if legacy.exists():
                backup = self.root / 'counter.before-profiles.json'
                if not backup.exists():
                    shutil.copy2(legacy, backup)
            self.state = {'version': 1, 'active': 'legacy', 'profiles': {'legacy': 'Phantom Blade Zero'}}
            write_json(self.index, self.state)

    @property
    def active(self):
        return self.state['active']

    def data_path(self, ident=None):
        ident = ident or self.active
        if ident == 'legacy':
            return self.root / 'counter.json'
        if ident not in self.state['profiles'] or len(ident) != 32 or not all(c in '0123456789abcdef' for c in ident):
            raise ValueError('Invalid profile ID')
        return self.root / 'profiles' / ident / 'counter.json'

    def activate(self, ident):
        if ident not in self.state['profiles']:
            raise ValueError('Unknown profile')
        self.state['active'] = ident
        write_json(self.index, self.state)

    def create(self, name, data=None):
        ident = uuid.uuid4().hex
        folder = self.root / 'profiles' / ident
        folder.mkdir(parents=True)
        write_json(folder / 'counter.json', data or {'deaths': [], 'aliases': {}, 'auto_enabled': False})
        self.state['profiles'][ident] = name.strip() or 'New game'
        write_json(self.index, self.state)
        return ident

    def export(self, destination):
        path = self.data_path()
        data = json.loads(path.read_text(encoding='utf-8'))
        data = copy.deepcopy(data)
        missing = 0
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
            for index, death in enumerate(data.get('deaths', [])):
                for kind, shot in death.get('screenshots', {}).items():
                    if not shot:
                        continue
                    source = Path(shot['path'])
                    if source.is_file():
                        member = f'images/{index}-{kind}.jpg'
                        archive.write(source, member)
                        shot['path'] = member
                    else:
                        death['screenshots'][kind] = None
                        missing += 1
            reference = data.get('reference_path')
            if reference:
                if not Path(reference).is_file():
                    raise ValueError('The custom death-screen reference is missing')
                archive.write(reference, 'reference.png')
                data['reference_path'] = 'reference.png'
            archive.writestr('profile.json', json.dumps({'version': 1, 'name': self.state['profiles'][self.active], 'data': data}, indent=2))
        return missing

    def import_archive(self, source):
        # Read only explicitly referenced files; never extract paths from a ZIP.
        with zipfile.ZipFile(source) as archive:
            if sum(info.file_size for info in archive.infolist()) > 2_000_000_000:
                raise ValueError('Profile archive exceeds 2 GB uncompressed')
            if archive.getinfo('profile.json').file_size > 20_000_000:
                raise ValueError('Profile manifest is too large')
            manifest = json.loads(archive.read('profile.json'))
            if manifest.get('version') != 1 or not isinstance(manifest.get('name'), str):
                raise ValueError('Unsupported profile archive')
            data = manifest['data']
            if not isinstance(data, dict) or not isinstance(data.get('deaths', []), list) or not isinstance(data.get('aliases', {}), dict):
                raise ValueError('Invalid profile data')
            for death in data.get('deaths', []):
                if not isinstance(death.get('boss'), str) or not isinstance(death.get('time'), str):
                    raise ValueError('Invalid death entry')
            payloads = []
            for i, death in enumerate(data.get('deaths', [])):
                for kind, shot in death.get('screenshots', {}).items():
                    if shot:
                        if kind not in ('before', 'death') or shot['path'] != f'images/{i}-{kind}.jpg':
                            raise ValueError('Invalid screenshot reference')
                        payloads.append((shot, archive.read(shot['path']), f'images/{i}-{kind}.jpg'))
            reference = data.get('reference_path')
            ref_bytes = None
            if reference:
                if reference != 'reference.png':
                    raise ValueError('Invalid death-screen reference')
                ref_bytes = archive.read(reference)
            # Validation and ZIP reads finish before adding anything to the index.
            ident = uuid.uuid4().hex
            folder = self.root / 'profiles' / ident
            folder.mkdir(parents=True)
            for shot, blob, relative in payloads:
                target = folder / relative
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(blob)
                shot['path'] = str(target.resolve())
            if ref_bytes is not None:
                (folder / 'reference.png').write_bytes(ref_bytes)
                data['reference_path'] = str((folder / 'reference.png').resolve())
            write_json(folder / 'counter.json', data)
            self.state['profiles'][ident] = manifest['name'] + ' (imported)'
            write_json(self.index, self.state)
            return ident
