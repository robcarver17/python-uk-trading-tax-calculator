"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


"""
This code reads my own data base of FX prices (actually .csv files from pysystemtrade)

If you have a database of FX prices then replace the code here, keeping the same function name get_fx_data
"""

import datetime

import numpy as np
import sqlite3
import pandas as pd

def get_fx_data(currency):
    
    ans=_get_fx_prices(currency)
    getdollars=_get_fx_prices("GBP").reindex(ans.index, method="ffill")
    ans=ans/getdollars

    return ans

def _get_fx_prices(currency):
    if currency=="USD":
        date_range = pd.date_range(datetime.datetime(1970,1,1), datetime.datetime.now())
        return pd.DataFrame(
            [1.0]*len(date_range), index=date_range)
    ans =pd.read_csv("/home/rob/pysystemtrade/data/futures/fx_prices_csv/%sUSD.csv" % currency)
    ans_index = ans.DATETIME
    ans_index = pd.to_datetime(ans_index, format="%Y-%m-%d %H:%M:%S").values
    pd_data = pd.DataFrame(list(ans.PRICE.values), index = ans_index)

    return pd_data

