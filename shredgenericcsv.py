"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


"""
Import a generic csv


"""

import numpy as np
import datetime
import pandas as pd
from trades import Trade
from tradelist import TradeList

def _resolveBS(xstring):
    if xstring=="B":
        return "BUY"
    elif xstring=="S":
        return "SELL"

def _resolvetype(xstring):
    if type(xstring)==np.float64 or type(xstring)==np.int64 or type(xstring)==int:
        xstring=float(xstring)
        
    if type(xstring)==float:
        return xstring

    if type(xstring)==str:
        return float(xstring.replace(',',''))
    
    raise Exception("Type error")

def from_csv_row_to_trade(row, useassetclass):
    """
    Taxes and commissions are positive 
    
    Quantity is unsigned
    """
    this_trade=Trade(Code=row.Company, Currency=row.Currency, Price=_resolvetype(row.Price), 
                     Tax=_resolvetype(row.Tax), 
                     Commission=_resolvetype(row.Charges), BS=_resolveBS(row["B/S"]), 
                     Date=datetime.datetime.strptime(row['Date'], "%d/%m/%Y"), 
                     Quantity=abs(_resolvetype(row.Shares)),
                     AssetClass=useassetclass)
    
    return this_trade

def _from_genericpdf_to_trades_object(all_results, useassetclass):
    """
    Converts a pandas data frame to a list of trades
    """
    tlist=TradeList([from_csv_row_to_trade(all_results.irow(idx), useassetclass) for idx in range(len(all_results.index))])
    
    return tlist


def read_generic_csv(fname, useassetclass="Stocks"):
    """
    Import a generic csv, return a TradeList
    
    Columns are B/S, Date, Company, Shares, Price, Charges, Tax, Currency
    B/S is B for buy, S for sell
    Date is in 14/02/2003 format
    Shares (quantity) is always positive
    Tax and Charges are always positive
    
    """

    ## 'Read it in
    all_results=pd.read_csv(fname)
    
    ## Convert to a list of trades
    tradelist=_from_genericpdf_to_trades_object(all_results, useassetclass)
    
    ## We need to add the values, and signed quantities, as these aren't included by default
    tradelist=tradelist.add_values()
    
    return tradelist

