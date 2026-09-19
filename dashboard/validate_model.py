"""Offline model/CSV verification on Python 3.12, Windows or Linux.

No training, secrets access, HTTP calls, or modifications to model/data files.
"""
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from features import RAW_COLUMNS

ROOT=Path(__file__).resolve().parent


def main():
    if sys.version_info[:2] != (3,12):
        raise RuntimeError('Use Python 3.12 for the bundled model.')
    windows=ROOT/'models/final_pipeline.windows.joblib'
    path=windows if os.name=='nt' and windows.exists() else ROOT/'models/final_pipeline.joblib'
    model=joblib.load(path)
    raw=pd.read_csv(ROOT/'data/raw_test.csv').set_index('CustomerID')
    reference=pd.read_csv(ROOT/'data/live_reference.csv').set_index('CustomerID').loc[raw.index]
    scores=model.predict_proba(raw[RAW_COLUMNS])[:,1]*100
    np.testing.assert_array_equal(model.predict(raw[RAW_COLUMNS]),reference.LivePrediction.to_numpy())
    np.testing.assert_allclose(scores,reference.LiveRiskScore.to_numpy(),rtol=0,atol=1e-4)
    required=['customers.csv','raw_test.csv','live_reference.csv','nested_cv_summary.csv',
              'simulation_summary.csv','simulation_runs.csv','scenario_probabilities.csv','reviewed_messages.csv']
    for filename in required:
        assert not pd.read_csv(ROOT/'data'/filename).empty, f'Empty CSV: {filename}'
    metadata=json.loads((ROOT/'models/metadata.json').read_text(encoding='utf-8'))
    assert len(raw)==metadata['test_rows']
    print(f'Model: {path.name}; verified rows: {len(raw)}; prediction mismatches: 0')
    print(f'Maximum score difference: {np.max(np.abs(scores-reference.LiveRiskScore.to_numpy())):.9f}')
    print('Required CSV files: OK; no training or API requests.')


if __name__=='__main__':
    main()
