import numpy as np
from app.clustering import cluster_tracks, cluster_counts


def track(start, end):
    return {'start':start,'end':end,'seen':10,'points':np.linspace(start,end,30).tolist()}


def test_opposite_flows_are_separate_and_noise_is_retained():
    tracks={str(i):track([.1,.2+i*.003],[.9,.2+i*.003]) for i in range(3)}
    tracks.update({str(i+3):track([.9,.2+i*.003],[.1,.2+i*.003]) for i in range(3)})
    tracks['noise']=track([.1,.9],[.1,.1]);tracks['static']=track([.5,.5],[.51,.5])
    result=cluster_tracks(tracks)
    assert len(result['clusters'])==2
    assert result['assignments']['0'] != result['assignments']['3']
    assert result['noise_tracks']==2
    assert result==cluster_tracks(dict(reversed(list(tracks.items()))))
    events=[{'tracker_id':i,'category':'car'} for i in range(6)]+[{'tracker_id':None,'category':'car'}]
    report=cluster_counts(result,events)
    assert sum(row['count'] for row in report['counts'])+report['unresolved_events']==7


def test_curved_paths_and_invalid_tracks():
    tracks={str(i):{'seen':12,'points':[[.1,.9],[.1,.5],[.5,.1],[.9,.1]]} for i in range(3)}
    tracks['bad']={'seen':20,'points':[[0,0],[float('nan'),1]]}
    assert len(cluster_tracks(tracks)['clusters'])==1
    assert cluster_tracks({})['clusters']==[]
