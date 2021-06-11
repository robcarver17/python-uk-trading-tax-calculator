"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


"""
Shred the  reports produced by IB

This section is for global variables that define how the data is stored in the .html files

HEADER_NAMES indicates the asset classes which are specified in the table.

CURRENCIES contains all the currencies that you trade. 

TRADES_LOC and POSITIONS_LOC indicate where in the trade and activity report respectively the 
  tables of trades and current positions are held. They shouldn't 
"""

## Start of formatting globals


ASSETS=['Stocks', 'Futures', 'Forex']
CURRENCIES=['GBP', 'JPY' ,'EUR', 'KRW', 'AUD', 'CHF', 'USD']

TRADES_LOC=1
POSITIONS_LOC=7

## End of formatting globals

## Imports

import datetime

import pandas as pd
from bs4 import BeautifulSoup

from trades import Trade
from tradelist import TradeList


def _row_class(row):
    """
    Returns the class of a row or "" if no class. Used to find summary rows
    """
    if len(row.attrs)>0:
        dattrs=dict(row.attrs)
        if 'class' in dattrs:
            return dattrs['class']
    return ""

def _parse_html_table(rows):
    """
    Get data from rows
    """
    results = []
    headerrow=None
    for row in rows:
        table_headers = row.findAll('th')
        if table_headers:
            """
            We've got headers. Note the first set of headers we find will be used to name our data frame
            The rest ignored
            """
            if headerrow is None:

                ## Its the first set of headers
                ##We add a column for the row class

                headerlist=[str(headers.getText()) for headers in table_headers]+['Class']

                ##The terms notional value and proceeds are used depending on the asset class;
                ##consistently use notional value

                headerlist=["Notional Value" if x=="Proceeds" else x for x in headerlist]
                headerrow=headerlist

        table_data = row.findAll('td')

        if table_data:
            """
            Add some normal data, including the class of the row 
            """
            rowclass=_row_class(row)
            results.append([str(data.getText()) for data in table_data]+[rowclass])

    return (headerrow, results)



def _html_row(row, clength):
    """
    row is a list of length, probably with unicode strings in it
    We return a list of normal strings, padded out with Nones to clength
    """

    assert len(row)<=clength

    strings_row=[str(x) for x in row]
    strings_row += [''] * (clength - len(strings_row))

    return strings_row

def _html_table_to_pddataframe(headerrow, table_data):
    """
    Returns a pandas data frame from a list table_data, where headerrow are column names

    """

    ## Column names ... getting rid of any unicode
    colnames=[str(x) for x in headerrow]
    clength=len(colnames)

    ## Pad out the rows so the same length and all strings
    new_data=[_html_row(row, clength) for row in table_data]

    ## Create a dict
    results=dict([(colnames[idx], [row[idx] for row in new_data]) for idx in range(clength)])

    main_table=pd.DataFrame(results)

    return main_table

def _check_ignore_row(row, colref="Acct ID"):
    """
    Returns TRUE if rows don't contain real data or positions
    """
    if "Total" in row[colref]:
        """
        It's a sub total row
        """
        return True

    row_class = row['Class']

    if not (row_class=='summaryRow' or row_class=="row-summary"
            or row_class=="row-summary no-details"
    or row_class=="['row-summary']"
            or row_class =="['summaryRow']"
    or row_class == "['row-summary', 'no-details']"):
        """
        It's Granualar detail, can ignore
        """
        return True

    return False

def _select_and_clean_pd_dataframe(main_table, selection_idx, colref="Acct ID"):
    """
    Remove 'dirty' rows from a dataframe, i.e. not real data
    """

    if len(selection_idx)==0:
        return None

    pd_df=main_table.iloc[selection_idx,:]

    dirty_rows=[rowidx for rowidx in range(len(pd_df.index))
                if _check_ignore_row(pd_df.iloc[rowidx], colref)]
    pd_df=pd_df.drop(pd_df.index[dirty_rows])

    if len(pd_df.index)==0:
        return None

    return pd_df


def _check_index_row(row, colref="Acct ID"):
    """
    Index rows are empty except for the contents of colref. Returns bool
    """
    restorfow=row.drop(colref)
    ans=list(restorfow.values)
    otherrowsempty=all([len(x)==0 for x in ans])

    return otherrowsempty

def _check_blank_row(row):
    return all([len(x)==0 for x in row])


def _get_index_row(row, colref):
    return row[colref]


def _get_all_longnames_assets(table, colref="Acct ID"):
    """
    Returns the list of asset classes in this file as tuple (shortname, longname)
    """
    hrows=table[colref]
    headers=[]
    for x in hrows:
        for shortname in ASSETS:
            if shortname in x and "Total" not in x:
                headers.append((shortname, x))

    return list(set(headers))

def _get_all_currencies(table, colref="Acct ID"):
    """
    Returns the list of currencies in this file
    """
    hrows=table[colref]
    ccys=[x for x in hrows if x in CURRENCIES]
    return list(set(ccys))


def _parse_pandas_df(main_table, colref="Acct ID"):
    """
    Turns a pandas df into a recursive version

    Returns a dict (key names are asset classes)
     Elements in dict are also dicts (key names are currencies)
      Elements in those dicts are pd data frames

    Also deletes superflous rows
    """

    assetspacked=_get_all_longnames_assets(main_table, colref)
    assetlongnames=[x[1] for x in assetspacked]
    assetshortnames=[x[0] for x in assetspacked]
    currencies=_get_all_currencies(main_table, colref)

    ## Create an empty recursive structure
    ## Each entry contains a list of row indices
    results=dict([(hname, dict([(ccy, []) for ccy in currencies])) for hname in assetshortnames])

    ## Loop through populating the recursive structure, adding row names to it
    rowidx=0
    current_header=None
    current_currency=None

    total_len=len(main_table.index)


    while rowidx<total_len:
        row=main_table.iloc[rowidx]

        if _check_blank_row(row):
            rowidx=rowidx+1
            continue

        if _check_index_row(row, colref):
            ## It's an index row, i.e. it contains eithier an asset class or a currency
            ## Return the name of the index (asset class or currency
            indexentry=_get_index_row(row, colref)

            if indexentry in assetlongnames:
                ## It's an asset class. Since these are at a higher level than FX we reset the currency
                current_header=[shortname for shortname, longname in assetspacked
                                if longname==indexentry][0]
                current_currency=None

            elif indexentry in currencies:
                ## It's a currency.
                current_currency=indexentry
            else:
                raise Exception("Unrecognised header")

        else:
            ## not an index, populating the table
            if current_header is None or current_currency is None:
                ## This will happen if we have extraenous rows before the headers
                raise Exception("Found data before eithier asset class or currency was set")
            else:
                ## Add the row index to the right part of the dict
                results[current_header][current_currency].append(rowidx)

        ## next row
        rowidx=rowidx+1


        ## Create a dict of dicts of dataframes, with the appropriate subindex, cleaned up
    df_results=dict([(assetname, dict([
                                    (ccy, _select_and_clean_pd_dataframe(main_table, results[assetname][ccy], colref) )
                                    for ccy in currencies])) for assetname in assetshortnames])

    return df_results

def _collapse_recursive_dict(df_results):
    """
    Convert the df_results back to a dataframe

    df_results will be a two level dict with dataframes inside. We add the dict keys as extra columns
    """

    all_results=[]
    assets=df_results.keys()

    for assetname in assets:
        df_subresults=df_results[assetname]
        currencies=df_subresults.keys()

        for ccy in currencies:
            df_subsub=df_subresults[ccy]
            if df_subsub is None:
                ## Empty dict. It happens
                continue

            ## Create extra columns for sub dataframe
            df_subsub["AssetClass"]=[assetname]*len(df_subsub.index)
            df_subsub["Currency"]=[ccy]*len(df_subsub.index)

            ## Add the sub dataframe to the list of dataframes
            all_results.append(df_subsub)

    all_results=pd.concat(all_results)

    return all_results



def _parse_trade_date(tradedate):
    try:
        return datetime.datetime.strptime(tradedate, "%Y-%m-%d, %H:%M:%S")
    except:
        return datetime.datetime.strptime(tradedate, "%Y-%m-%d")



def _read_ib_html(fname, table_ref):
    """
    Reads a single table from an .html file fname produced by IB reports, and returns a pandas dataframe

    table_ref gives position of table in .html stack
    """

    ## Open the file
    with open(fname,'r') as file_handle:
        soup = BeautifulSoup(file_handle.read(), features="html.parser")
    if len(soup)==0:
        raise Exception("Empty or non existent html file %s" % fname)

    ## Find the right table and extract the rows
    tables=soup.findAll('table')
    table=tables[table_ref]
    table_rows = table.findAll('tr')

    ## Process the rows from html into lists
    (headerrow, table_data) = _parse_html_table(table_rows)

    ## Convert to pandas dataframe
    main_table=_html_table_to_pddataframe(headerrow, table_data)

    return main_table

def _from_positions_row_to_position(row):
    """
    Convert a row into a Position object
    """
    quantity=float(row.Quantity.replace(',',''))
    this_position=Position(Code=row.Symbol.replace('+',''), Position=quantity)
    return this_position

def _from_pddf_to_positions_object(all_results, pricerow='Price'):
    """
    Converts a pandas data frame to a list of positions
    """

    plist=PositionList([_from_positions_row_to_position(all_results.loc[idx], pricerow=pricerow)
                         for idx in range(len(all_results.index))])

    return plist


def _from_trades_row_to_trade(row, pricerow='Price', commrow="Comm"):
    """
    Convert a row of trades into a trade object
    """

    ## IB has negative for buys, and positive for sales (i.e. cashflow method)
    value=float(row['Notional Value'].replace(',',''))
    quantity=float(row.Quantity.replace(',',''))

    ## Note that taxes and commissions are reported as negative (cashflow)
    ## Value is negative for buys and positive for sells, which is fine
    ## quantities are already signed

    try:
        Tax=abs(float(row.Tax.replace(',','')))
    except:
        Tax=0.0

    col_labels=row.keys()
    col_labels=[str(x) for x in col_labels]
    if "Trade Date" in col_labels:
        date_label="Trade Date"
    elif "Trade Date/Time" in col_labels:
        date_label="Trade Date/Time"
    elif "Date/Time" in col_labels:
        date_label="Date/Time"
    else:
        raise Exception("Date column not found")

    price_value = float(row[pricerow].replace(',', ''))
    comm_value = abs(float(row[commrow].replace(',', '')))

    this_trade=Trade(Code=row.Symbol, Currency=row.Currency, Price=price_value,
                     Tax=Tax,
                     Commission=comm_value,
                     Date=_parse_trade_date(row[date_label]), SignQuantity=quantity,
                     Quantity=abs(quantity), Value=value, AssetClass=row.AssetClass)

    return this_trade

def _from_pddf_to_trades_object(all_results, pricerow='Price', commrow="Comm"):
    """
    Converts a pandas data frame to a list of trades
    """

    tlist=TradeList([_from_trades_row_to_trade(all_results.iloc[idx], pricerow=pricerow, commrow=commrow)
                      for idx in range(len(all_results.index))])

    return tlist



def get_ib_trades(fname, table_ref = TRADES_LOC, colref="Acct ID", pricerow='Price', commrow="Comm"):
    """
    Reads an .html file output by interactive brokers
    Returns a trade_list object

    To get the file log in to Account manager... Reports.... trade confirmations....

    Save the resulting report as trades.html (or whatever)

    You'll need the report for the current financial year, plus

    """

    print("Getting trades from %s" % fname)
    main_table=_read_ib_html(fname, table_ref=table_ref)

    ## Convert to a recursive dict of dicts, whilst doing some cleaning
    df_results=_parse_pandas_df(main_table,  colref=colref)

    ## Go back to a single data frame with extra columns added
    all_results=_collapse_recursive_dict(df_results)

    ## Finally convert to a list of trades
    return _from_pddf_to_trades_object(all_results, pricerow=pricerow, commrow=commrow)

