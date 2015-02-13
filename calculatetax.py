
from positions import compare_trades_and_positions, tax_calc_dict_umatched_as_positions
from fxrates import FXDict
from taxcalcdict import TaxCalcDict
from utils import star_line

def calculatetax(all_trades, all_positions=None, CGTCalc=True, reportfile="TaxReport", reportinglevel="NORMAL", fxsource="DATABASE"):
    """
    Calculate the tax
    
    all_trades is a TradeList object
    all_positions is an optional PositionList object which we use to check consistency with trades
    
    CGTCalc = True means we use same day and 30 day matching before S104 matching
              False means we use only S104; effectively calculating average cost for each trade
    
    reportinglevel - ANNUAL - summary for each year, BRIEF- plus one line per trade, 
                   NORMAL - matching details per trade, VERBOSE - full breakdown of subtrade matching
    
    reportfile- text file we dump answersinto

    fxsource will indicate source of data; change FXData function as appropriate 
    
    """
    
    assert reportinglevel in ["VERBOSE", "NORMAL", "BRIEF", "ANNUAL"]
    report = open(reportfile, "w")
    
    print "Report will be written to %s" % reportfile
    
    if all_positions is not None:    
        breaklist=compare_trades_and_positions(all_trades, all_positions)
        if len(breaklist)>0:
            print "Breaks. Should be none apart from FX rates"
            print breaklist
        else:
            print "Trades and positions consistent"


    all_trades.add_tradeids()
    
    ## Get FX data
    print "Getting fx data"
    all_currencies=all_trades.all_currencies()
    fx_dict=FXDict(all_currencies, fxsource)
    
    all_trades.add_fxdict_rates(fx_dict)

    
    ## Do various preprocessing measures
    trade_dict_bycode=all_trades.separatecode()
    trade_dict_bycode.add_cumulative_data()
    trade_dict_bycode.generate_pseduo_trades()

    ## Create a tax dictionary        
    taxcalc_dict=TaxCalcDict(trade_dict_bycode)
    
    ## Do the trade matching
    print "Matching trades"
    taxcalc_dict.allocate_dict_trades(CGTCalc)

    ## Consistency check    
    breaklist=compare_trades_and_positions(all_trades, tax_calc_dict_umatched_as_positions(taxcalc_dict))
    
    if len(breaklist)>0:
        print "BREAKS between final positions and those implied by trades. Something gone horribly wrong!"
        print breaklist
        raise Exception("Breaks occured!")
    else:
        print "Passed consistency check"
    
    taxyears=taxcalc_dict.tax_year_span()
    
    for taxyear in taxyears:
        report.write(star_line())
        report.write("\n TAX YEAR: %d \n\n" % taxyear)
        taxcalc_dict.display_taxes(taxyear, CGTCalc, reportinglevel, report)

    report.close()
    
    print "Report finished"
        
    return taxcalc_dict
