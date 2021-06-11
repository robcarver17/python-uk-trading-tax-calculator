"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


import sys
from fxrates import FXDict
from taxcalcdict import TaxCalcDict
from utils import star_line

def calculatetax(all_trades,  CGTCalc=True, reportfile=None, reportinglevel="NORMAL", fxsource="DATABASE"):
    """
    Calculate the tax

    all_trades is a TradeList object

    CGTCalc = True means we use same day and 30 day matching before S104 matching
              False means we use only S104; effectively calculating average cost for each trade

    reportinglevel - ANNUAL - summary for each year, BRIEF- plus one line per trade,
                   NORMAL - plus matching details per trade, CALCULATE - as normal plus calculations
                   VERBOSE - full breakdown of subtrade matching

    reportfile- text file we dump answers into. If omitted will print to screen.

    fxsource will indicate source of data used by FXData function as appropriate

    """

    assert reportinglevel in ["VERBOSE", "CALCULATE", "NORMAL", "BRIEF", "ANNUAL"]

    if reportfile is None:
        reportfile="the screen."
        report=sys.stdout
    else:
        report = open(reportfile, "w")

    print("Report will be written to %s" % reportfile)


    ### Add TradeID's
    all_trades.add_tradeids()

    ## Get FX data
    print("Getting fx data")
    all_currencies=all_trades.all_currencies()
    fx_dict=FXDict(all_currencies, fxsource)

    all_trades.add_fxdict_rates(fx_dict)


    ## Do various preprocessing measures
    trade_dict_bycode=all_trades.separatecode()
    trade_dict_bycode.add_cumulative_data()
    trade_dict_bycode.generate_pseduo_trades()

    ## Create a tax dictionary containing the trade data
    taxcalc_dict=TaxCalcDict(trade_dict_bycode)

    ## Do the trade matching
    print("Matching trades")
    taxcalc_dict.allocate_dict_trades(CGTCalc)

    ## What tax years are our trades for
    taxyears=taxcalc_dict.tax_year_span()

    for taxyear in taxyears:
        report.write(star_line())
        report.write("\n TAX YEAR: %d \n\n" % taxyear)

        ## Display taxes
        taxcalc_dict.display_taxes(taxyear, CGTCalc, reportinglevel, report)

    if reportfile is not "the screen":
        report.close()

    print("Report finished")
        
    return taxcalc_dict
