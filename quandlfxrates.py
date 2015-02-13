"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


import pandas as pd
import Quandl

"""
Get currency data from www.quandl.com

You can also use an authentication code if you have one
"""


def get_quandl_currency(currency):
    """
    Given a currency code eg USDAUD returns a pandas data frame with the quandl price series
    
    Daily prices only
    
    If there is no quandl price error
    
    Watch out for the 100x per day limit
    
    
    """
    
    
    if currency=="GBP":
        ## Return a pd of 1's from ... to present day
        return pd.TimeSeries([1.0], index=[pd.datetime(2008,1,1)])
     

    quandldef='CURRFX/%sGBP' % currency
    data = Quandl.get(quandldef)
    data=data['Rate']
        
    return data


