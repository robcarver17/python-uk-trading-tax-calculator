"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


import pandas as pd
from databasefxrates import get_fx_data
from quandlfxrates import get_quandl_currency

def FXDict(all_currencies, source):
    """
    Return pd dataframe of currencies
    
    all_currencies is list of currencies to get
    
    fx source can be: 'FIXED' uses fixed rates for whole year, 'QUANDL' downloads rates from www.quandl.com
      'DATABASE' this is my function for accessing my own database. It won't work for you, need to roll your own
    """

    
    if source=="DATABASE":    
        print "WARNING WILL BLOW UP IF YOU HAVEN'T SET UP A DATABASE"
        fx_dict=dict([(currency, get_fx_data(currency)) for currency in all_currencies])
    elif source=="FIXED":
        fx_dict=dict([(currency, get_fixed_fx_data(currency)) for currency in all_currencies])
    elif source=="QUANDL":
        fx_dict=dict([(currency, get_quandl_currency(currency)) for currency in all_currencies])
        
    else:
        raise Exception("Source %s for fx data unknown. Use DATABASE or FIXED" % source)
        
    return fx_dict

RATE_DICT=dict(GBP=1.0, USD=0.60, KRW=0.00078, JPY=0.0038, EUR=0.66, CHF=0.66, AUD=0.55)

def get_fixed_fx_data(currency):
    """
    Use this if you don't have proper FX data and are happy to use fixed values
    
    Rate starts in 2008 (before that old CGT rules applied) and will be forward filled as required
    """
    
    if currency not in RATE_DICT:
        raise Exception("Don't have an fx rate for %s " % currency)
    
    rate_value=RATE_DICT[currency]
    
    print "Warning using approximate rate of %f for %s" % (rate_value, currency)
    
    return pd.TimeSeries([rate_value], index=[pd.datetime(2008,1,1)])

