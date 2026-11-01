import copy
import unittest
from death_edits import merge_categories, transfer_deaths
from app import boss_text, resolve_boss
from types import SimpleNamespace


class EditTests(unittest.TestCase):
    def test_merge_keeps_evidence_and_updates_aliases(self):
        deaths=[{'boss':'Wrong','time':'one','screenshots':{'death':{'path':'image.jpg'}}},{'boss':'Right','time':'two'}]
        evidence=copy.deepcopy(deaths[0]['screenshots'])
        aliases={'OCR Wrong':'Wrong'}
        self.assertEqual(merge_categories(deaths,aliases,['Wrong'],'Right'),1)
        self.assertEqual([d['boss'] for d in deaths],['Right','Right'])
        self.assertEqual(deaths[0]['screenshots'],evidence)
        self.assertEqual(deaths[0]['time'],'one')
        self.assertEqual(aliases['Wrong'],'Right')
        self.assertEqual(aliases['OCR Wrong'],'Right')

    def test_move_only_selected_and_does_not_alias_environment(self):
        deaths=[{'boss':'Enemy/environment death','time':'one'},{'boss':'Enemy/environment death','time':'two'}]
        self.assertEqual(transfer_deaths(deaths,[deaths[1]],'Boss'),1)
        self.assertEqual(deaths[0]['boss'],'Enemy/environment death')
        self.assertTrue(deaths[1]['manual_assignment'])
        aliases={}
        merge_categories(deaths,aliases,['Enemy/environment death'],'Boss')
        self.assertNotIn('Enemy/environment death',aliases)

    def test_reordered_golden_mask_name_matches(self):
        for name in ['GOLD-MASKED THE ONE','GOLD-MASKED ONE THE']:
            self.assertEqual(resolve_boss(name,{},['THE GOLD-MASKED ONE']),'THE GOLD-MASKED ONE')

    def test_ocr_boxes_read_left_to_right(self):
        result=SimpleNamespace(txts=['GOLD-MASKED','ONE','THE'],scores=[.99,.99,.99],boxes=[[[50,0],[140,0],[140,20],[50,20]],[[150,0],[180,0],[180,20],[150,20]],[[0,0],[40,0],[40,20],[0,20]]])
        self.assertEqual(boss_text(result),'THE GOLD-MASKED ONE')


if __name__=='__main__':
    unittest.main()
