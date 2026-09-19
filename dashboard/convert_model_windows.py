"""Convert the bundled XGBoost snapshot for Windows without training or API calls.

Run with .venv/Scripts/python.exe convert_model_windows.py.
The original model is preserved. The converted copy is saved only after all
reference predictions and scores have been checked.
"""
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
import xgboost

from features import RAW_COLUMNS

ROOT = Path(__file__).resolve().parent


def restore_booster(self, state):
    snapshot = bytes(state['handle'])
    # This bundled snapshot contains Config followed by Model. Load the native
    # model directly, avoiding the cross-platform memory-snapshot deserializer.
    marker = b'L\x00\x00\x00\x00\x00\x00\x00\x05Model'
    if snapshot.count(marker) != 1 or not snapshot.endswith(b'}}'):
        raise ValueError('Unexpected snapshot format; original model unchanged.')
    start = snapshot.index(marker) + len(marker)
    xgboost.Booster.__init__(self)
    self.load_model(bytearray(snapshot[start:-1]))
    self.__dict__.update({k: v for k, v in state.items() if k != 'handle'})


def main():
    with patch.object(xgboost.Booster, '__setstate__', restore_booster):
        model = joblib.load(ROOT / 'models/final_pipeline.joblib')
    raw = pd.read_csv(ROOT / 'data/raw_test.csv').set_index('CustomerID')
    reference = pd.read_csv(ROOT / 'data/live_reference.csv').set_index('CustomerID').loc[raw.index]
    scores = model.predict_proba(raw[RAW_COLUMNS])[:, 1] * 100
    predictions = model.predict(raw[RAW_COLUMNS])
    np.testing.assert_array_equal(predictions, reference.LivePrediction.to_numpy())
    np.testing.assert_allclose(scores, reference.LiveRiskScore.to_numpy(), rtol=0, atol=1e-4)
    destination = ROOT / 'models/final_pipeline.windows.joblib'
    joblib.dump(model, destination, compress=3)
    reloaded = joblib.load(destination)
    np.testing.assert_array_equal(reloaded.predict_proba(raw[RAW_COLUMNS])[:, 1] * 100, scores)
    print(f'Validated {len(raw)} rows; no prediction mismatches.')
    print(f'Maximum score difference: {np.max(np.abs(scores-reference.LiveRiskScore.to_numpy())):.9f}')
    print(f'Saved {destination.name}; original preserved; no training performed.')


if __name__ == '__main__':
    main()
