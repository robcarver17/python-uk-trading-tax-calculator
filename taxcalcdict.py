"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""

import numpy as np
import sys
from tradelist import TradeList, TradeDictByCode
from utils import  which_tax_year, star_line,pretty

from taxcalctradegroup import TaxCalcTradeGroup, zero_tax_tuple
from positions import Position, PositionList

class TaxCalcDict(dict):
    """
    A tax calc dict is constructed from a normal trade dict seperated by code eg
    
    trade_dict_bycode=all_trades.separatecode()
    
    The structure is:
       dict, code keywords
           TaxCalcElement()
    """

        
    def __init__(self, tradedict):

        '''
        To set up the group we loop over the elements in the trade dict 
        '''
        assert type(tradedict) is TradeDictByCode

        for code in tradedict.keys():
            self[code]=TaxCalcElement(tradedict[code])
            
    def allocate_dict_trades(self, CGTcalc=True):
        
        [taxelement.allocate_trades(CGTcalc) for taxelement in self.values()]
        
        return self


    def return_profits(self, taxyear, CGTCalc):
        
        codes= self.keys()
        codes.sort()
        elements_profits=dict([(code,self[code].return_profits_for_code(taxyear, CGTCalc)) for code in codes])

        return elements_profits
        
    def average_commission(self, taxyear):
        codes= self.keys()
        codes.sort()
        average_commissions=dict([(code,self[code].average_commission(taxyear)) for code in codes])

        return average_commissions


        
    def display_taxes(self,  taxyear, CGTCalc, reportinglevel, report=None):
        """
        Run through each element, displaying the tax information in full
        
        Then print a summary
        """
        assert reportinglevel in ["VERBOSE","CALCULATE", "NORMAL", "BRIEF", "ANNUAL"]
        
        if report is None:
            report=sys.stdout
        
        ## Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        ##        number_disposals, commissions, taxes, gross profit, net profit
        
        codes= self.keys()
        codes.sort()
        elements_taxdata=[self[code].display_taxes_for_code(taxyear, CGTCalc, reportinglevel, report) for code in codes]

        if len(elements_taxdata)==0:
            report.write(star_line())        
            
            report.write("\n\nNo relevant trades for tax year %d\n\n" % taxyear)
            report.write(star_line())
            
            return None
        
        
        summary_taxdata=map(sum, zip(*elements_taxdata))

        assert len(summary_taxdata)==len(zero_tax_tuple)

        ## print the summary (always regardless of reporting level)
        display_summary_tax(summary_taxdata, CGTCalc, taxyear, report)

        report.write(star_line())        


        return None

    def tax_year_span(self):
        ## Get unique list of tax years
        datelist=[]
        for taxelement in self.values():
            datelist=datelist+taxelement.closing_trade_dates()
        taxyears=[which_tax_year(datex) for datex in datelist]
        taxyears=list(set(taxyears))
        taxyears.sort()

        return taxyears

    def umatched_as_positions(self):
        """
        Return a PositionList object containing the unmatched trades
        """
        result=PositionList()
        
        for code in self.keys():
            position=self[code].unmatched.final_position()
            result.append(Position(Code=code, Position=position))
    
        return result
    

class TaxCalcElement(object):
    """
    A tax calc element is constructed from a normal trade list for one code eg.
    
    tradelist=all_trades.separatecode()['a code']
    
    The structure is:
       attributes: matched, unmatched
           matched: list of TaxCalcTradeGroup objects (begins as empty)  
            
            unmatched: TradeList of all unmatched trades. Initially this inherits all the trades in tradelist 
    """

        
    def __init__(self, tradelist):

        '''
        To set up the group we populate unmatched and have an empty matched
        '''
        assert type(tradelist) is TradeList
        assert tradelist.check_same_code() is True
        
        setattr(self, "matched", dict())
        setattr(self, "unmatched", tradelist)


    def __repr__(self):
        
        return "%d matched, %d unmatched" % (len(self.matched), len(self.unmatched)) 


    def closing_trade_dates(self):
        datelist=[taxcalcgroup.closingtrade.Date for taxcalcgroup in self.matched.values()]
        
        return datelist

    def allocate_trades(self, CGTcalc):
        """
        One by one, push the closing trades (from earliest to latest) into matched
        
        Then match them
        """
        
        ## Find, and pop,  next closing trade in unmatched list
        ## This will be none if there aren't any
        ## Then add to tax calc trade group
        
        tradecount=1
        
        while True:
            earliest_closing_trade=self.unmatched._pop_earliest_closing_trade()
            
            if earliest_closing_trade is None:
                break
            
            ## Now create the matched group. This will pop things out of self.allocated            
            taxcalcgroup=self.matchingforgroup(earliest_closing_trade, CGTcalc)
            
            self.matched[tradecount]=taxcalcgroup
            
            tradecount=tradecount+1
        
        if len(self.unmatched)>0:
            
            if self.unmatched.final_position()==0:
                           
                ## Now we've got rid of the closing trades, we're probably left with a bunch of opening trades
                
                ## The last one of these must be a closer with a different sign, pretending to be 
                ##  an opener
                
                ## Make it into a closer, and then run a match
         
                ## get the last trade
                self.unmatched.date_sort()
                
                tradetomatch=self.unmatched.pop()
                tradetomatch.modify(tradetype="Close")
                
                assert self.unmatched.check_same_sign()
                
                taxcalcgroup=self.matchingforgroup(tradetomatch, CGTcalc)
                self.matched[tradecount]=taxcalcgroup
                
            else:
                ## We've got positions remaining, which is fine
                pass

 
        return self
    
    
    def matchingforgroup(self, tradetomatch, CGTcalc):
        """
        Build up a tax calc trade group with trades that match the closing trade, which are popped out of self
        
        If you want to change the logic for how trades are matched, this is the place to do it
         
        """

        ## Create the group initially with just
        taxcalcgroup=TaxCalcTradeGroup(tradetomatch)
        
        if CGTcalc:

            ## Same day
            while taxcalcgroup.is_unmatched():
                            
                tradeidx=self.unmatched.idx_of_last_trade_same_day(tradetomatch)
                if tradeidx is None:
                    break
                
                ## Remove the trade (creating a partial if needed)
                poppedtrade=self.unmatched._partial_pop_idx(tradeidx, taxcalcgroup.count_unmatched())
                
                ## Add to list
                taxcalcgroup.sameday.append(poppedtrade)
                
            ## 30 day rule
            while taxcalcgroup.is_unmatched():
                            
                tradeidx=self.unmatched.idx_of_first_trade_next_30days(tradetomatch)
                if tradeidx is None:
                    break
                
                ## Remove the trade (creating a partial if needed)
                poppedtrade=self.unmatched._partial_pop_idx(tradeidx, taxcalcgroup.count_unmatched())
                
                ## Add to list
                taxcalcgroup.withinmonth.append(poppedtrade)

        
        ## S104 (what we do without CGT calc, or what's left
        ## This is a bit more complicated because we need to do a 
        ##            proportionate partial pop of all previous trades
        
        if taxcalcgroup.is_unmatched():
            
            ## Get all the previous trades            
            tradeidxlist=self.unmatched.idx_of_trades_before_datetime(tradetomatch)
            
            if len(tradeidxlist)>0:
            
                ## Remove a proportion of all previous trades
                popped_trades=self.unmatched._proportionate_pop_idx(tradeidxlist, taxcalcgroup.count_unmatched())
                
                ## Add to list
                taxcalcgroup.s104=popped_trades


        if taxcalcgroup.is_unmatched():
            print "Can't find a match for %d lots of ...:" % taxcalcgroup.count_unmatched() 
            print taxcalcgroup.closingtrade
            raise Exception()
            
        
        return taxcalcgroup
    

    def return_profits_for_code(self, taxyear, CGTCalc):
        ## Returns a list of profits
        groupidlist=self.matched.keys()
        groupidlist.sort()

        ## Last is always net p&l        
        taxdata=[self.matched[groupid].group_display_taxes(taxyear, CGTCalc, reportinglevel="", groupid=groupid, report=None, display=False)[-1] \
                 for groupid in groupidlist]
        
        return taxdata

    def display_taxes_for_code(self, taxyear, CGTCalc, reportinglevel, report=None):
        ## Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        ##        number_disposals, commissions, taxes, gross profit, net profit
        
        groupidlist=self.matched.keys()
        groupidlist.sort()
        
        taxdata=[self.matched[groupid].group_display_taxes(taxyear, CGTCalc, reportinglevel, groupid, report) for groupid in groupidlist]
        if len(taxdata)==0:
            return zero_tax_tuple
        
        ## Sum up the tuple, and return the sums
        sum_taxdata=map(sum, zip(*taxdata))
        
        assert len(sum_taxdata)==len(zero_tax_tuple)
        
        return sum_taxdata

    def average_commission(self, taxyear):
        ## Returns the average commission
        groupidlist=self.matched.keys()
        groupidlist.sort()

        ## Last is always net p&l        
        taxdata=[self.matched[groupid].group_display_taxes(taxyear, CGTCalc=True, reportinglevel="", groupid=groupid, report=None, display=False) \
                 for groupid in groupidlist]
        
        commissions=[x[5] for x in taxdata]
        quants=[x[8] for x in taxdata]
        
        total_comm=sum(commissions)
        total_quant=sum(quants)
        
        if total_quant==0.0:
            if total_comm==0:
                return np.nan
            else:
                return 0.0
        
        return total_comm / (2.0*total_quant)

def display_summary_tax(summary_taxdata, CGTCalc, taxyear, report):
            
        """
        taxdata contains a list of tuples
        ## Each tuplue (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
                commissions, taxes, gbp_gross_profit, gbp_net_profit)
    
        
        
        """    

        ## Unpack tuple
        (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
                gbp_commissions, gbp_taxes, gbp_gross_profit,  abs_quantity, gbp_net_profit) = summary_taxdata

        report.write(star_line())
        
        report.write("\n\n                Summary for tax year ending 5th April %d \n" % taxyear)
        report.write("\n                              Figures in GBP\n\n")


        if CGTCalc:
            report.write("Disposal Proceeds = %s, Allowable Costs = %s, Disposals = %d \n Year Gains = %s  Year Losses = %s PROFIT = %s\n" % \
                (pretty(gbp_disposal_proceeds), pretty(gbp_allowable_costs), 
                 number_disposals, pretty(gbp_gains), pretty(gbp_losses), pretty(gbp_net_profit)))
            
        else:
            report.write("Gross trading profit %s, Commission paid %s, Taxes paid %s, Net profit %s\n" % \
              (pretty(gbp_gross_profit), pretty(gbp_commissions),
               pretty(gbp_taxes), pretty(gbp_net_profit)))
              
            report.write("\nNot included: interest paid, interest received, data and other fees, internet connection,...\n hardware, software, books, subscriptions, office space, Dividend income (report seperately)\n\n")
            
        report.write("\n\n")
        
        
