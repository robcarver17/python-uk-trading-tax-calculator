from shredIBfiles import get_ib_trades, get_ib_positions
from shredgenericcsv import read_generic_csv
from calculatetax import calculatetax

from tradelist import TradeList
from positions import PositionList

def get_all_trades_and_positions():

    trades1=get_ib_trades("/home/rsc/MAINtrades2014to20150205.html")
    trades2=get_ib_trades("/home/rsc/LONGtrades2014to20150205.html")
    trades3=read_generic_csv("/home/rsc/tradespre2014.csv")
    
    ## Doesn't inherit the type
    all_trades=TradeList(trades1+trades2+trades3)
    
    positions1=get_ib_positions('/home/rsc/u1228709.html')
    positions2=get_ib_positions('/home/rsc/u144083.html')
    
    all_positions=PositionList(positions1+positions2)
    
    return (all_trades, all_positions)

(all_trades, all_positions)=get_all_trades_and_positions()

##    assert reportinglevel in ["VERBOSE", "NORMAL", "BRIEF", "ANNUAL"]

taxcalc_dict=calculatetax(all_trades, all_positions, CGTCalc=False, reportfile="/home/rsc/TaxReport.txt", 
                          reportinglevel="BRIEF", fxsource="DATABASE")

