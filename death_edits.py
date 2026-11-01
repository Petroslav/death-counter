"""Change death assignments without changing timestamps or evidence."""
ENVIRONMENT = 'Enemy/environment death'


def transfer_deaths(deaths, selected, target):
    target = target.strip()
    if not target:
        raise ValueError('Choose a boss/category')
    identities = {id(death) for death in selected}
    changed = 0
    for death in deaths:
        if id(death) in identities:
            death['boss'] = target
            death['manual_assignment'] = True
            changed += 1
    return changed


def merge_categories(deaths, aliases, sources, target):
    target = target.strip()
    if not target:
        raise ValueError('Choose a boss/category')
    keys = {name.casefold() for name in sources}
    selected = [death for death in deaths if death['boss'].casefold() in keys]
    changed = transfer_deaths(deaths, selected, target)
    for source, destination in list(aliases.items()):
        if destination.casefold() in keys:
            aliases[source] = target
    # A historical environment merge must not redirect future unknown deaths.
    for source in sources:
        if source.casefold() != ENVIRONMENT.casefold():
            aliases[source] = target
    return changed
