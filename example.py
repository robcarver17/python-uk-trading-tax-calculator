"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""

import numpy as np

from shredIBfiles import get_ib_trades
from shredgenericcsv import read_generic_csv
from calculatetax import calculatetax

from tradelist import TradeList
from utils import profit_analyser

def get_all_trades():
    """
    You can change this file for your own purposes
    """

    """
    Get trades, from IB trade reports.
    
    Save as .html
        
    You can only run one year of trade reports at a time, so its a good idea to run them and save them
    """


    """
    You can also use .csv files to store trades. I'm doing that here to account for positions I 
    transferred to IB
    
    """
    ## OBVIOUSLY YOU WILL NEED TO CHANGE THIS
    mydir="/home/rob/python-uk-trading-tax-calculator/"

    ## YOU MAY NEED TO FIDDLE WITH THE ARGUMENTS TO GET THIS TO WORK
    ## THIS IS BECAUSE THE FORMAT OF THE IB REPORT HAS CHANGED OVER TIME
    ## THE FOLLOWING ARGUMENTS SEEM TO WORK BEST WITH THE MOST RECENT OUTPUT
    ## SOMETIMES TABLE_REF WILL NEED TO BE 7 DEPENDING ON WHAT OTHER ASSETS ARE IN YOUR
    ##  ACCOUNT
    trades3 = get_ib_trades(mydir + "jan2021_apr2021.html", table_ref=8,
                             colref="Account", pricerow="T. Price", commrow="Comm/Fee")

    ## HERES A SLIGHTLY OLDER FILE
    trades2 = get_ib_trades(mydir + "U1228709.2020.html", table_ref=8,
                            colref="Symbol", pricerow="T. Price", commrow="Comm/Fee")


    ## HERES AN OLDER FORMAT
    trades1=get_ib_trades(mydir+"MAINtrades2014to20150205.html")

    # CAN ALSO GET FROM A CSV
    trades0=read_generic_csv(mydir+"tradespre2014.csv")

    ## Doesn't inherit the type
    all_trades=TradeList(trades0+trades1+trades2+trades3)


    return all_trades



### Get trades and positions
all_trades=get_all_trades()


"""
Create a big report

reportfile is where we output. If omitted, prints to screen.

    reportinglevel - ANNUAL - summary for each year, BRIEF- plus one line per closing trade,
               NORMAL - plus matching details per trade, CALCULATE - as normal plus calculations
               VERBOSE - as calculate plus full breakdown of sub-trades used for matching


fx source can be: 'FIXED' uses fixed rates for whole year, 'QUANDL' downloads rates from www.quandl.com
  'DATABASE' this is my function for accessing my own database. It won't work for you, need to roll your own

"""

### Decide if we're calculating on a CGT or a 'true cost' basis
CGTCalc=True
reportfile="TaxReport.txt"
reportinglevel="VERBOSE"
fxsource="CSV"

taxcalc_dict=calculatetax(all_trades, CGTCalc=CGTCalc, reportfile=reportfile,
                          reportinglevel=reportinglevel, fxsource=fxsource)


#return (avgwin, avgloss, countwins, countlosses)


## Example of how we can delve into the finer details. This stuff is all printed to screen
## You can also run this interactively
## CGTCalc needs to match, or it wont' make sense

taxcalc_dict.display_taxes(taxyear=2014, CGTCalc=CGTCalc, reportinglevel="BRIEF")


## Display all the trades for one code ('element')
#taxcalc_dict['IAPl'].display_taxes_for_code(taxyear=2017, CGTCalc=CGTCalc, reportinglevel="CALCULATE")
#taxcalc_dict['NXGl'].display_taxes_for_code(taxyear=2017, CGTCalc=CGTCalc, reportinglevel="CALCULATE")
#taxcalc_dict['TCAPl'].display_taxes_for_code(taxyear=2017, CGTCalc=CGTCalc, reportinglevel="CALCULATE")


"""
## Display a particular trade. The number '3' is as shown the report
taxcalc_dict['FBTP DEC 14'].matched[3].group_display_taxes(taxyear=2015, CGTCalc=CGTCalc, reportinglevel="VERBOSE")

## Heres a cool trade
#taxcalc_dict['FGBS DEC 14'].element_display_taxes(taxyear=2015, CGTCalc=CGTCalc, reportinglevel="NORMAL")
taxcalc_dict['FGBS DEC 14'].matched[17].group_display_taxes(taxyear=2015, CGTCalc=CGTCalc, reportinglevel="VERBOSE")


## Bonus feature - analyse profits
"""
profits=taxcalc_dict.return_profits(2021, CGTCalc)
profit_analyser(profits)

avgcomm=taxcalc_dict.average_commission(2019)
codes=avgcomm.keys()
codes.sort()
for code in codes:
    print("%s %f" % (code, avgcomm[code]))

print(np.nanmean(avgcomm.values()))
