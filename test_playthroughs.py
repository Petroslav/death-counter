import copy
import unittest
import playthroughs as ng
import encounters as fights


class NGTests(unittest.TestCase):
    def test_legacy_migration_keeps_counts_and_screenshot_links(self):
        deaths=[{'boss':'Boss','time':'2026-11-01T10:00:00+02:00','screenshots':{'before':{'path':'image.jpg'}}}]
        old=copy.deepcopy(deaths)
        encounters={}; runs={}
        ng.migrate(deaths,encounters,runs); fights.migrate(deaths,encounters)
        ng.migrate(deaths,encounters,runs)
        self.assertEqual(len(runs),1)
        self.assertEqual(deaths[0]['run_id'],'ng')
        self.assertEqual(deaths[0]['screenshots'],old[0]['screenshots'])
        self.assertEqual(len(encounters),1)

    def test_same_boss_in_new_ng_has_fresh_fight_and_kill_state(self):
        runs={'ng':{'name':'NG'}}; encounters={}
        old={'boss':'Boss','time':'2026-11-01T10:00:00+02:00','run_id':'ng'}
        ident=fights.route_death(old,encounters)
        fights.mark_killed(encounters,ident,'2026-11-01T11:00:00+02:00')
        new_run=ng.create(runs)
        new={'boss':'Boss','time':'2026-11-08T10:00:00+02:00','run_id':new_run}
        new_id=fights.route_death(new,encounters)
        self.assertNotEqual(ident,new_id)
        self.assertEqual(encounters[new_id]['number'],1)
        self.assertIsNone(encounters[new_id]['killed_at'])
        self.assertEqual(runs[new_run]['name'],'NG+')
        self.assertEqual(runs[ng.create(runs)]['name'],'NG+2')
        self.assertEqual(sum(ng.includes(d,ng.ALL) for d in [old,new]),2)
        self.assertEqual(sum(ng.includes(d,new_run) for d in [old,new]),1)

    def test_pending_result_keeps_original_run_even_after_new_ng_starts(self):
        encounters={}
        pending={'boss':'Boss','time':'2026-11-01T10:00:00+02:00','run_id':'ng'}
        newer={'boss':'Boss','time':'2026-11-08T10:00:00+02:00','run_id':'plus'}
        new_id=fights.route_death(newer,encounters)
        old_id=fights.route_death(pending,encounters)
        self.assertNotEqual(old_id,new_id)
        self.assertEqual(encounters[old_id]['run_id'],'ng')

    def test_cross_ng_transfer_rejected_without_mutating_entry(self):
        encounters={}
        old={'boss':'Boss','time':'2026-11-01T10:00:00+02:00','run_id':'ng'}
        new={'boss':'Other boss','time':'2026-11-08T10:00:00+02:00','run_id':'plus'}
        target=fights.route_death(old,encounters)
        before=copy.deepcopy(new)
        with self.assertRaises(ValueError):
            fights.assign_to([old,new],[new],encounters,'Boss',target)
        self.assertEqual(new,before)
