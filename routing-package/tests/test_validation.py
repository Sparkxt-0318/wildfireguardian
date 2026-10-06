import copy,unittest
from routing.fixture import example
from routing.validation import validate_graph,validate_hazard,validate_request,ValidationError

class AdmissionTests(unittest.TestCase):
    def test_good_fixture_and_copy_isolation(self):
        x=example();g=validate_graph(x['graph']);h=validate_hazard(g,x['hazard'],x['request']['as_of']);q=validate_request(g,h,x['request']);q['incurred']['m0']=4
        self.assertEqual(x['request']['incurred']['m0'],0)
    def test_full_payload_and_request_rejections(self):
        changes=[('hazard','schema','probability/1'),('hazard','crs','EPSG:4326'),('hazard','version',True),('hazard','dt',0),('hazard','channels',['fire_arrival']),('hazard','units',{'flux':'MW/m'}),('hazard','time_origin','nope'),('hazard','available_at','2026-10-05T00:00:00+08:00'),('hazard','issued_at','2026-10-05T00:00:00+08:00'),('request','position',{'node':'absent'}),('request','position',{'edge':'OA','fraction':.5}),('request','objective','shortest_distance'),('request','exposure_scope','implicit'),('request','incurred',{'m0':0}),('request','horizon',31),('request','departure',.5),('request','incoming_edge','DA'),('request','destinations',[])]
        for part,key,value in changes:
            with self.subTest(part=part,key=key):
                x=example();x[part][key]=value
                with self.assertRaises(ValidationError):validate_request(x['graph'],x['hazard'],x['request'])
        for channel,value in [('flux',-1),('flux',float('nan')),('flux',True),('flame',1),('support',0)]:
            with self.subTest(channel=channel,value=value):
                x=example();x['hazard']['members'][0][channel][0][0]=value
                with self.assertRaises(ValidationError):validate_hazard(x['graph'],x['hazard'])
        for key,value in [('flux',[[1]]),('breakpoints',[0,0,30]),('breakpoints',[1,30])]:
            x=example();x['hazard']['members'][0][key]=value
            with self.assertRaises(ValidationError):validate_hazard(x['graph'],x['hazard'])
    def test_spatial_alignment_reverse_and_turns(self):
        for mutation in ['alignment','revision','grid','reverse','turn','duplicate']:
            x=example()
            if mutation=='alignment':x['graph']['edges'][0]['segments'][0]['cell']=2
            elif mutation=='revision':x['hazard']['graph_revision']='other'
            elif mutation=='grid':x['hazard']['grid']['resolution']=20
            elif mutation=='reverse':x['graph']['edges'][0]['reverse_edge']='BD'
            elif mutation=='turn':x['graph']['forbidden_turns']=[['OA','BD']]
            else:x['hazard']['members'].append(copy.deepcopy(x['hazard']['members'][0]))
            with self.subTest(mutation=mutation),self.assertRaises(ValidationError):validate_request(x['graph'],x['hazard'],x['request'])
    def test_endpoint_normalization_and_causal_time(self):
        x=example();x['request']['position']={'edge':'OA','fraction':1};x['request']['incoming_edge']='OA'
        self.assertEqual(validate_request(x['graph'],x['hazard'],x['request'])['position'],{'node':'A'})
        x=example();x['request']['as_of']='2026-10-04T00:00:01+08:00'
        with self.assertRaises(ValidationError):validate_request(x['graph'],x['hazard'],x['request'])
    def test_missing_support_stays_explicit(self):
        x=example();x['hazard']['members'][0]['support'][0][0]=False
        self.assertFalse(validate_hazard(x['graph'],x['hazard'])['members'][0]['support'][0][0])

if __name__=='__main__':unittest.main()
