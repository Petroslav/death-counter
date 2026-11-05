"""Keep repeated fights with one named boss separate from OCR spelling aliases."""
from datetime import datetime
import uuid

ENVIRONMENT = 'Enemy/environment death'


def moment(text):
    value=datetime.fromisoformat(text)
    return value.astimezone() if value.tzinfo is None else value


def new_encounter(encounters, boss, started_at):
    number = 1 + max((e['number'] for e in encounters.values() if e['boss'].casefold()==boss.casefold()), default=0)
    ident = uuid.uuid4().hex
    encounters[ident] = {'boss':boss, 'number':number, 'started_at':started_at, 'killed_at':None}
    return ident


def route_death(death, encounters):
    boss = death['boss']
    if boss.casefold()==ENVIRONMENT.casefold():
        death.pop('encounter_id',None)
        return None
    matches = [(ident,e) for ident,e in encounters.items() if e['boss'].casefold()==boss.casefold()]
    # An OCR result completed after Mark killed can still belong to the old fight.
    closed = [(ident,e) for ident,e in matches if e.get('killed_at') and moment(death['time']) <= moment(e['killed_at'])]
    if closed:
        ident = min(closed,key=lambda pair:pair[1]['number'])[0]
    else:
        opened = [(ident,e) for ident,e in matches if not e.get('killed_at')]
        ident = max(opened,key=lambda pair:pair[1]['number'])[0] if opened else new_encounter(encounters,boss,death['time'])
    death['encounter_id']=ident
    return ident


def migrate(deaths, encounters):
    for death in deaths:
        ident=death.get('encounter_id')
        if ident in encounters:
            # Encounter identity survives OCR normalization, imports, and restarts.
            death['boss']=encounters[ident]['boss']
        else:
            route_death(death,encounters)


def label(encounter):
    name=encounter['boss']
    if encounter['number']>1:
        name+=f" — Rematch {encounter['number']-1}"
    if encounter.get('killed_at'):
        name+=' [Killed]'
    return name


def death_label(death, encounters):
    encounter=encounters.get(death.get('encounter_id'))
    return label(encounter) if encounter else death['boss']


def fight_timestamp(encounter, deaths, mode):
    if mode=='killed':
        return encounter.get('killed_at')
    times=[death['time'] for death in deaths if death.get('time')]
    if not times:
        return encounter.get('started_at')
    def value(text):
        try:
            return moment(text).timestamp()
        except (ValueError,TypeError):
            return float('-inf')
    return (max if mode=='latest' else min)(times,key=value)


def ordered_fights(encounters, rows, mode='first'):
    def order(ident):
        if ident not in encounters:
            return (2,0,ident)  # Environment is a summary, not a boss encounter.
        text=fight_timestamp(encounters[ident],rows[ident],mode)
        try:
            stamp=moment(text).timestamp()
        except (ValueError,TypeError):
            return (1,0,ident)
        return (0,-stamp if mode=='latest' else stamp,ident)
    return sorted(rows,key=order)


def mark_killed(encounters, ident, when):
    encounter=encounters[ident]
    if not encounter.get('killed_at'):
        encounter['killed_at']=when


def assign_to(deaths, selected, encounters, boss, ident=None):
    selected_ids={id(death) for death in selected}
    changed=0
    for death in deaths:
        if id(death) in selected_ids:
            death['boss']=boss
            death['manual_assignment']=True
            if ident:
                death['encounter_id']=ident
            else:
                route_death(death,encounters)
            changed+=1
    return changed


def split_after(deaths, encounters, last_death):
    ident=last_death.get('encounter_id')
    if ident not in encounters:
        raise ValueError('Select a death assigned to a boss first')
    encounter=encounters[ident]
    cutoff=last_death['time']
    encounter['killed_at']=cutoff
    later=[death for death in deaths if death.get('encounter_id')==ident and moment(death['time'])>moment(cutoff)]
    if later:
        new_id=new_encounter(encounters,encounter['boss'],min(d['time'] for d in later))
        assign_to(deaths,later,encounters,encounter['boss'],new_id)
    return len(later)
