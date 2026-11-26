from collections import Counter
import pytest
from app.evaluation import count_metrics, tracking_metrics


def frame(t, identity=1, category='car', box=None):
    return {'t':t,'objects':[{'tracker_id':identity,'category':category,'box':box or [.1,.1,.4,.4]}]}


def test_count_metrics_and_empty_denominator():
    values=count_metrics(Counter({('A','B','car'):10}),Counter({('A','B','car'):8}))
    assert values['mae']==2 and values['rmse']==2 and values['wape']==.2
    assert count_metrics(Counter(),Counter())['wape'] is None


def test_tracking_perfect_missed_false_positive_and_switch():
    reference=[frame(0),frame(1)]
    exact=tracking_metrics(reference,[frame(0,5),frame(1,5)])
    assert exact['mota']==exact['idf1']==exact['f1']==1
    switched=tracking_metrics(reference,[frame(0,5),frame(1,6)])
    assert switched['id_switches']==1 and switched['mota']==.5 and switched['idf1']==.5
    missed=tracking_metrics(reference,[frame(0,5),frame(1,5,'bus')])
    assert missed['tp']==1 and missed['fp']==1 and missed['fn']==1
    assert missed['mota']==0


def test_unannotated_predictions_are_excluded_and_missing_frame_is_not_reused():
    metrics=tracking_metrics([frame(0),frame(1)],[frame(0,5),frame(.5,5)])
    assert metrics['fn']==1 and metrics['fp']==0 and metrics['predicted_detections']==1
    assert metrics['idf1']==pytest.approx(2/3)


def test_duplicate_or_invalid_reference_is_rejected():
    with pytest.raises(ValueError): tracking_metrics([frame(0),frame(0)],[])
    with pytest.raises(ValueError): tracking_metrics([frame(0,box=[.5,.5,.1,.1])],[])
    duplicate=frame(0);duplicate['objects']*=2
    with pytest.raises(ValueError): tracking_metrics([duplicate],[])
