"""Importable feature preparation, shared by training and serving."""
import numpy as np
RAW_COLUMNS = ['Tenure','PreferredLoginDevice','CityTier','WarehouseToHome','PreferredPaymentMode','Gender','HourSpendOnApp','NumberOfDeviceRegistered','PreferedOrderCat','SatisfactionScore','MaritalStatus','NumberOfAddress','Complain','OrderAmountHikeFromlastYear','CouponUsed','OrderCount','DaySinceLastOrder','CashbackAmount']
def prepare_customer_features(raw):
    missing = set(RAW_COLUMNS) - set(raw.columns)
    if missing: raise ValueError(f'Eksik alanlar: {sorted(missing)}')
    p = raw.loc[:,RAW_COLUMNS].copy()
    for col, mapping in {'PreferredLoginDevice':{'Phone':'Mobile Phone'},'PreferredPaymentMode':{'CC':'Credit Card','COD':'Cash on Delivery'},'PreferedOrderCat':{'Mobile':'Mobile Phone'}}.items():
        p[col] = p[col].replace(mapping)
    p['CouponUsageRate'] = p['CouponUsed'] / p['OrderCount'].replace(0,np.nan)
    p['ShortTenureFlag'] = np.where(p['Tenure'].isna(),np.nan,(p['Tenure']<=3).astype(float))
    p['ShortTenureComplaint'] = p['ShortTenureFlag'] * p['Complain']
    return p
