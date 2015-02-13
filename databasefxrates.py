"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


"""
This code reads my own data base of FX prices 

If you have a database of FX prices then replace the code here, keeping the same function name get_fx_data
"""

import datetime

import numpy as np
import sqlite3
import pandas as pd

def get_fx_data(currency):
    
    ans=_get_fx_prices("LIVE", currency).PRICE
    getdollars=_get_fx_prices("LIVE", "GBP").PRICE.reindex(ans.index, method="ffill")
    ans=ans/getdollars
    
    return ans


def get_db_conn_for(dbsystem, dbtype, system=""):

    """
    
    Database connections
    
    Returns a sqllite3 connection according to two arguments: System and database
    
    This is the place where you would hack to change the defaults
    
    Arguments: dbtype is LIVE or TEST (could be others or an actual file name)
            dbsystem is {static, prices, diags, control, accounts}
    
    returns sqllite3 connection
    
    """

    
    pathname=None
     
    if dbtype=="LIVE":
        pathname="/home/run/data/live"     
    else:
        raise Exception("Only LIVE supported here")
        
    pathfilename="%s/%s.db" % (pathname, dbsystem)

    try:
        conn=sqlite3.connect(pathfilename, timeout=30)
    except:
        error_msg="Couldn't connect to database specified as %s %s resolved to %s" % (dbsystem, dbtype, pathfilename)
        raise Exception(error_msg)

    return conn


def date_as_string(dtobject=datetime.datetime.now(), short=False, long=False):
    if short:
        return dtobject.strftime("%Y-%m-%d")
    elif long:
        return dtobject.strftime("%Y-%m-%d %H:%M:%S.%f")
    else:
        return dtobject.strftime("%Y-%m-%d %H:%M:%S")

def erfloat(x):
    try:
        return(float(x))
    except:
        return(np.nan)




def _get_fx_prices(dbtype, currency):
    
    ctable=_fx_table(dbtype)
    ans=ctable.read_fx_prices(currency)
    ctable.close()
    
    return ans

class _fx_table(object):
    '''
    object is a connection to an fx table
    
    with this we can read and write from fx table as required
    
    note we never directly access the table, to avoid issues and to hide definition
    
    
    Standards for _table classes:
    
    init, close, read, update, add, delete
    
    We never modify self except when closing
    '''


    def __init__(self, dbtype):
        '''
        
        All sysdatabase objects contain a connection when initialised
        
        '''

        
        self.conn=get_db_conn_for(dbsystem="prices_fxprices", dbtype=dbtype)
        self.dbtype=dbtype

        
    def close(self):
        """
        Close the database connection
        """
        self.conn.close()

    def read_fx_prices(self, currency):
        """
        Returns a pandas dataframe of all the fx rates for a particular currency
        """ 
        self.conn.row_factory=sqlite3.Row
        ans=self.conn.execute("SELECT datetime, fxprice FROM fxprices WHERE currency=? ORDER BY datetime", (currency, ))
        ans=ans.fetchall()

        """
        Returns a list of tuples, unicode at that
        """
        
        px_datetimes=[pd.to_datetime(x[0]) for x in ans]
        prices=[erfloat(x[1]) for x in ans]
        
        ans=pd.DataFrame(dict(PRICE=prices),index=px_datetimes)

        return ans

        
