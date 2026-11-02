import unittest
import copy
from encounters import migrate, route_death, mark_killed, label, split_after, assign_to


def death(second,boss='Boss'):
    return {'boss':boss,'time':f'2026-11-02T00:00:{second:02d}+02:00','screenshots':{'before':{'path':'before.jpg'}}}


class EncounterTests(unittest.TestCase):
    def test_migration_keeps_counts_and_evidence(self):
        deaths=[death(1),death(2)]
        original=copy.deepcopy(deaths)
        encounters={}
        migrate(deaths,encounters)
        self.assertEqual(len(encounters),1)
        for current,old in zip(deaths,original):
            self.assertEqual(current['screenshots'],old['screenshots'])
            self.assertEqual(current['time'],old['time'])
        migrate(deaths,encounters)
        self.assertEqual(len(encounters),1)

    def test_killed_fight_gets_separate_rematch(self):
        encounters={}
        first=death(1)
        ident=route_death(first,encounters)
        mark_killed(encounters,ident,'2026-11-02T00:00:05+02:00')
        second=death(7)
        second_id=route_death(second,encounters)
        third=death(8)
        self.assertEqual(route_death(third,encounters),second_id)
        self.assertNotEqual(ident,second_id)
        self.assertIn('[Killed]',label(encounters[ident]))
        self.assertIn('Rematch 1',label(encounters[second_id]))
        self.assertEqual(first['encounter_id'],ident)

    def test_pending_ocr_for_earlier_death_uses_completed_fight(self):
        encounters={}
        ident=route_death(death(1),encounters)
        mark_killed(encounters,ident,'2026-11-02T00:00:05+02:00')
        route_death(death(8),encounters)
        pending=death(4)
        self.assertEqual(route_death(pending,encounters),ident)

    def test_environment_not_a_boss_encounter(self):
        encounters={}
        self.assertIsNone(route_death(death(1,'Enemy/environment death'),encounters))
        self.assertFalse(encounters)

    def test_retroactive_boundary_only_moves_later_same_fight(self):
        deaths=[death(1),death(2),death(7),death(8),death(9,'Other boss')]
        encounters={}
        migrate(deaths,encounters)
        original=deaths[0]['encounter_id']
        other=deaths[-1]['encounter_id']
        self.assertEqual(split_after(deaths,encounters,deaths[1]),2)
        self.assertEqual(deaths[0]['encounter_id'],original)
        self.assertEqual(deaths[1]['encounter_id'],original)
        self.assertNotEqual(deaths[2]['encounter_id'],original)
        self.assertEqual(deaths[-1]['encounter_id'],other)
        new=route_death(death(10),encounters)
        self.assertEqual(new,deaths[2]['encounter_id'])

    def test_manual_move_can_target_an_exact_completed_fight(self):
        encounters={}
        first=death(1)
        ident=route_death(first,encounters)
        mark_killed(encounters,ident,'2026-11-02T00:00:05+02:00')
        second=death(8)
        route_death(second,encounters)
        assign_to([first,second],[second],encounters,'Boss',ident)
        self.assertEqual(second['encounter_id'],ident)
        self.assertTrue(second['manual_assignment'])


if __name__=='__main__':
    unittest.main()
