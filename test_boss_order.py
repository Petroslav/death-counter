import unittest
from encounters import ordered_fights,fight_timestamp


class BossOrderTests(unittest.TestCase):
    def setUp(self):
        self.fights={
            'b':{'started_at':'2026-11-01T11:00:00+02:00','killed_at':'2026-11-01T13:00:00+02:00'},
            'a':{'started_at':'2026-11-01T10:00:00+02:00','killed_at':'2026-11-01T14:00:00+02:00'},
            'c':{'started_at':'2026-11-02T10:00:00+02:00','killed_at':None},
        }
        self.rows={
            'b':[{'time':'2026-11-01T11:00:00+02:00'}],
            'a':[{'time':'2026-11-01T10:00:00+02:00'},{'time':'2026-11-01T12:00:00+02:00'}],
            'c':[], 'environment':[{'time':'2026-01-01T00:00:00+02:00'}],
        }

    def test_first_and_latest_use_actual_death_timestamps(self):
        self.assertEqual(ordered_fights(self.fights,self.rows,'first'),['a','b','c','environment'])
        self.assertEqual(ordered_fights(self.fights,self.rows,'latest'),['c','a','b','environment'])

    def test_kill_order_keeps_unkilled_and_environment_below(self):
        self.assertEqual(ordered_fights(self.fights,self.rows,'killed'),['b','a','c','environment'])

    def test_timezone_offsets_are_compared_as_instants(self):
        self.rows['a']=[{'time':'2026-11-01T11:30:00+03:00'}]
        self.assertEqual(ordered_fights(self.fights,self.rows,'first')[:2],['a','b'])

    def test_transferred_deaths_determine_first_time_without_rewriting_history(self):
        self.assertEqual(fight_timestamp(self.fights['b'],[{'time':'2026-10-31T10:00:00+02:00'}],'first'),'2026-10-31T10:00:00+02:00')


if __name__=='__main__':unittest.main()
