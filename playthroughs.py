"""Separate NG cycles while sharing the game's capture and recognition settings."""
import uuid

BASE='ng'
ALL='overall'


def migrate(deaths,encounters,runs):
    if not runs:
        runs[BASE]={'name':'NG'}
    for encounter in encounters.values():
        encounter.setdefault('run_id',BASE)
    for death in deaths:
        encounter=encounters.get(death.get('encounter_id'),{})
        death.setdefault('run_id',encounter.get('run_id',BASE))
    for item in list(deaths)+list(encounters.values()):
        ident=item.get('run_id',BASE)
        runs.setdefault(ident,{'name':'NG' if ident==BASE else 'Imported NG'})


def create(runs):
    number=len(runs)
    name='NG+' if number==1 else f'NG+{number}'
    ident=uuid.uuid4().hex
    runs[ident]={'name':name}
    return ident


def includes(item,view):
    return view==ALL or item.get('run_id',BASE)==view
