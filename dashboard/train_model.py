"""Rebuild only the final model. Never calls Gemini."""
import argparse, json, platform
from pathlib import Path
import pandas as pd
import numpy as np
import joblib, sklearn, xgboost
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,roc_auc_score,confusion_matrix
from xgboost import XGBClassifier
from features import RAW_COLUMNS, prepare_customer_features
ROOT=Path(__file__).resolve().parent
def main(path):
    df=pd.read_excel(path,sheet_name='E Comm')
    assert len(df)==5630 and df.CustomerID.is_unique
    train,test=train_test_split(df,test_size=.2,random_state=42,stratify=df.Churn)
    expected=pd.read_csv(ROOT/'data/customers.csv')
    assert set(test.CustomerID)==set(expected.CustomerID), 'Test IDs differ from notebook'
    X=train.set_index('CustomerID')[RAW_COLUMNS]
    prepared=prepare_customer_features(X)
    cats=prepared.select_dtypes(include=['object','category','string']).columns.tolist()
    nums=[c for c in prepared if c not in cats]
    pre=ColumnTransformer([
        ('numeric',Pipeline([('median_imputer',SimpleImputer(strategy='median')),('standard_scaler',StandardScaler())]),nums),
        ('categorical',Pipeline([('mode_imputer',SimpleImputer(strategy='most_frequent')),('one_hot_encoder',OneHotEncoder(handle_unknown='ignore',drop='first'))]),cats)])
    params=dict(n_estimators=700,learning_rate=.05,max_depth=5,min_child_weight=5,subsample=.8,colsample_bytree=1,reg_alpha=.1,reg_lambda=1,scale_pos_weight=5,objective='binary:logistic',eval_metric='logloss',random_state=42,n_jobs=1)
    model=Pipeline([('feature_engineering',FunctionTransformer(prepare_customer_features,validate=False)),('preprocessor',pre),('classifier',XGBClassifier(**params))])
    model.fit(X,train.Churn.to_numpy())
    raw=test.set_index('CustomerID')[RAW_COLUMNS]
    scores=model.predict_proba(raw)[:,1]; pred=model.predict(raw)
    metrics={name:float(fn(test.Churn,pred)) for name,fn in [('Accuracy',accuracy_score),('Precision',precision_score),('Recall',recall_score),('F1',f1_score)]}
    metrics['ROC_AUC']=float(roc_auc_score(test.Churn,scores))
    old=expected.set_index('CustomerID').loc[raw.index]
    maxdiff=float(np.max(np.abs(scores*100-old.RiskScore.to_numpy())))
    mismatches=int(np.sum(pred!=old.PredictedChurn.to_numpy()))
    assert mismatches==0 and maxdiff<.01, 'Notebook parity failed; inspect dependency versions before deploying.'
    out=ROOT/'models';out.mkdir(exist_ok=True)
    joblib.dump(model,out/'final_pipeline.joblib',compress=3)
    reloaded=joblib.load(out/'final_pipeline.joblib')
    np.testing.assert_allclose(reloaded.predict_proba(raw)[:,1],scores,rtol=0,atol=0)
    raw.to_csv(ROOT/'data/raw_test.csv')
    # Fixed reference cohort: preserve notebook rank assignments for existing IDs.
    # For new scores use empirical reference rank; ties are assigned conservatively higher.
    updated=pd.DataFrame({'CustomerID':raw.index,'LiveRiskScore':scores*100,'LivePrediction':pred,'ActualChurn':test.Churn.to_numpy()}).sort_values(['LiveRiskScore','CustomerID']).reset_index(drop=True)
    updated['LiveSegment']=pd.qcut(np.arange(len(updated)),10,labels=False)+1
    updated.to_csv(ROOT/'data/live_reference.csv',index=False)
    metadata={'metrics':metrics,'confusion_matrix':confusion_matrix(test.Churn,pred).tolist(),'max_score_difference':maxdiff,'prediction_disagreements':mismatches,'train_rows':len(train),'test_rows':len(test),'params':params,'python':platform.python_version(),'sklearn':sklearn.__version__,'xgboost':xgboost.__version__,'segmentation':'Live deployment uses its own frozen test cohort ranks; notebook results are historical. New inputs use right empirical rank. Not population risk thresholds.'}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(metadata,indent=2,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('excel');main(p.parse_args().excel)
