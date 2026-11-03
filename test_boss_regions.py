import queue
import threading
import unittest
from unittest.mock import Mock
from types import SimpleNamespace
import numpy as np
from app import Counter
from boss_regions import general_region,crop_region


class RegionTests(unittest.TestCase):
    def worker(self,responses):
        counter=Counter.__new__(Counter)
        counter.stop=threading.Event()
        counter.paused=threading.Event()
        counter.ocr_lock=threading.Lock()
        counter.ocr_engine=Mock(side_effect=responses)
        counter.aliases={}
        counter.deaths=[]
        counter.events=queue.Queue()
        counter.use_general_region=True
        return counter

    def result(self,text):
        return SimpleNamespace(txts=[text] if text else [],scores=[.99] if text else [])

    def test_relative_region_scales_and_handles_negative_monitor_origin(self):
        monitor={'left':-2560,'top':0,'width':2560,'height':1440}
        area=general_region(monitor)
        self.assertEqual(area,{'left':-1920,'top':144,'width':1280,'height':86})
        image=np.zeros((720,1280,3),dtype=np.uint8)
        self.assertEqual(crop_region(image,area,monitor).shape,(43,640,3))

    def test_general_failure_uses_saved_region_and_records_result(self):
        counter=self.worker([self.result(''),self.result(''),self.result('Boss name'),self.result('Boss name')])
        image=np.zeros((100,200,3),dtype=np.uint8)
        region={'left':0,'top':50,'width':100,'height':30}
        before=dict(region)
        counter.recover_boss({},10,[(9,'',image),(8,'',image)],region,{'left':0,'top':0,'width':200,'height':100})
        events=[]
        while not counter.events.empty():events.append(counter.events.get_nowait())
        details=next(value[1] for kind,value in events if kind=='lookup_details')
        self.assertEqual(details['status'],'confirmed')
        self.assertEqual(details['source'],'saved fallback')
        self.assertEqual(region,before)
        self.assertEqual(counter.ocr_engine.call_count,4)

    def test_disagreeing_candidates_are_visible_and_not_confirmed(self):
        counter=self.worker([self.result('Boss Alpha'),self.result('Boss Beta')])
        image=np.zeros((100,200,3),dtype=np.uint8)
        counter.recover_boss({},10,[(9,'',image),(8,'',image)],None,{'left':0,'top':0,'width':200,'height':100})
        kind,(_,details)=counter.events.get_nowait()
        self.assertEqual(kind,'lookup_details')
        self.assertEqual(details['status'],'unconfirmed')
        self.assertEqual([item['text'] for item in details['observations']],['Boss Alpha','Boss Beta'])

    def test_no_buffer_does_not_load_ocr(self):
        counter=self.worker([])
        counter.ocr_engine=None
        counter.recover_boss({},10,[],None,{'left':0,'top':0,'width':200,'height':100})
        self.assertIsNone(counter.ocr_engine)
        self.assertEqual(counter.events.get_nowait()[1][1]['status'],'unconfirmed')

    def test_primary_ocr_error_still_tries_fallback(self):
        counter=self.worker([RuntimeError('primary failed'),self.result('Boss name'),self.result('Boss name')])
        image=np.zeros((100,200,3),dtype=np.uint8)
        counter.recover_boss({},10,[(9,'',image),(8,'',image)],{'left':0,'top':50,'width':100,'height':30},{'left':0,'top':0,'width':200,'height':100})
        counter.events.get_nowait()
        details=counter.events.get_nowait()[1][1]
        self.assertEqual(details['status'],'confirmed')
        self.assertEqual(details['source'],'saved fallback')

    def test_one_frame_read_in_two_regions_is_not_two_confirmations(self):
        counter=self.worker([self.result('Boss name'),self.result('Boss name')])
        image=np.zeros((100,200,3),dtype=np.uint8)
        counter.recover_boss({},10,[(9,'',image)],{'left':0,'top':50,'width':100,'height':30},{'left':0,'top':0,'width':200,'height':100})
        details=counter.events.get_nowait()[1][1]
        self.assertEqual(details['status'],'unconfirmed')


if __name__=='__main__':unittest.main()
