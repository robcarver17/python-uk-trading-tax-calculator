from trades import Trade, THRESHOLD
from tradelist import TradeList, TradeDictByCode
from utils import tax_year, which_tax_year, star_line

zero_tax_tuple=(0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0)

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



    def display_taxes(self,  taxyear, CGTCalc, reportinglevel, report):
        """
        Run through each element, displaying the tax information in full
        
        Then print a summary
        """
        assert reportinglevel in ["VERBOSE", "NORMAL", "BRIEF", "ANNUAL"]
        
        ## Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        ##        number_disposals, commissions, taxes, gross profit, net profit
        
        codes= self.values()
        codes.sort()
        elements_taxdata=[taxelement.element_display_taxes(taxyear, CGTCalc, reportinglevel, report) for taxelement in codes]

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
            
            self.matched[str(tradecount)]=taxcalcgroup
            
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
                self.matched[str(tradecount)]=taxcalcgroup
                
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
    

    def element_display_taxes(self, taxyear, CGTCalc, reportinglevel, report):
        ## Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        ##        number_disposals, commissions, taxes, gross profit, net profit
        groupidlist=self.matched.keys()
        groupidlist.sort()
        
        taxdata=[self.matched[groupid].group_display_taxes(taxyear, CGTCalc, reportinglevel, report, groupid) for groupid in groupidlist]
        if len(taxdata)==0:
            return zero_tax_tuple
        
        ## Sum up the tuple, and return the sums
        sum_taxdata=map(sum, zip(*taxdata))
        
        assert len(sum_taxdata)==len(zero_tax_tuple)
        
        return sum_taxdata

class TaxCalcTradeGroup(object):
    """
    attributes: closingtrade, sameday, withinmonth, s104 
            closingtrade - contains single trade 
            sameday - TradeList of all matched trades done in the same day (if relevant)
            withinmonth - TradeList of all matched trades done in next 30 days (if relevant)
            s104 - TradeList of all remaining matched trades 
    """
    
    def __init__(self, closingtrade):

        '''
        We'd normally set up the group with a single closing trade 
        '''
    
        assert type(closingtrade) is Trade
        assert closingtrade.tradetype is "Close"
        
        setattr(self, "closingtrade", closingtrade)
        setattr(self, "sameday", TradeList())
        setattr(self, "withinmonth", TradeList())
        setattr(self, "s104", TradeList())

    def __repr__(self):
        
        return "Match for %s of which unmatched %d" % (self.closingtrade.__repr__(), self.count_unmatched())

    def is_unmatched(self):
        return self.count_unmatched()!=0

    def count_unmatched(self):
        ### Returns zero if all trades matched
        ## Else returns quantity left to match
        
        
        sizetomatch=self.closingtrade.SignQuantity
        
        ## matching trades should have opposite quantity
        samedaymatch=self.sameday.final_position()
        inmonthmatch=self.withinmonth.final_position()
        s104match=self.s104.final_position()
        
        matched=samedaymatch + inmonthmatch + s104match
        unmatched= -(sizetomatch + matched)
        
        ## eg matched = -5, sizetomatch = 6, unmatched = -1
        ## eg matched = 5, sizetomatch = -6, unmatched = 1
        
        assert abs(matched)<=abs(matched)
        
        if abs(unmatched)<THRESHOLD:
            ## Just in case pro-rata leaves rounding errors
            return 0.0
        
        return unmatched
    

    def matches_as_tradelist(self):
        """
        Returns a single tradelist with the various elements inside 
        """

        tradelist=TradeList()
        [tradelist.append(trade) for trade in self.sameday]
        [tradelist.append(trade) for trade in self.withinmonth]
        [tradelist.append(trade) for trade in self.s104]
        
        return tradelist

    

    def fxrate(self):
        """
        Return the relevant fx rate to use
        """
        return self.closingtrade.FXRate
    
    def _in_tax_year(self, taxyear=None):

        if taxyear is None:
            return True
        
        (startofyear, endofyear) = tax_year(taxyear)
        
        if self.closingtrade.Date<startofyear or self.closingtrade.Date>endofyear:
            return False  
        else:
            return True
    

    def group_display_taxes(self, taxyear, CGTCalc, reportinglevel, report, groupid):

        ## Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        ##        number_disposals, commissions, taxes, gross profit

        if not self._in_tax_year(taxyear):
            ## print nothing, return zero tuples
            return zero_tax_tuple


        ## Put all the matching opening trades into one list
        matchinglist=self.matches_as_tradelist()
        
        fxrate=self.fxrate()
        code=self.closingtrade.Code
        currency=self.closingtrade.Currency
        
        if 'AssetClass' in self.closingtrade.argsused:
            assetclass="("+self.closingtrade.AssetClass+")"
        else:
            assetclass=""
            
        datelabel=self.closingtrade.Date.strftime('%d/%m/%Y') 
        
        ## Values, done on cashflow basis. -ve means buy, +ve means sell
        close_value=self.closingtrade.Value
        open_value=sum([trade.Value for trade in matchinglist])

        ## quantity will be negative for a closing sale / opening buy
        sign_quantity=self.closingtrade.SignQuantity
        abs_quantity=abs(sign_quantity)

        ## Labelling
        if sign_quantity<0:
            labels=("BUY", "SELL")
        else:
            labels=("OPEN SHORT", "CLOSE SHORT")
        
        close_tax=self.closingtrade.Tax
        close_comm=self.closingtrade.Commission
        open_tax=sum([trade.Tax for trade in matchinglist])
        open_comm=sum([trade.Commission for trade in matchinglist])
        
        ## Fees, all positive
        taxes=open_tax+close_tax
        commissions=open_comm+close_comm

        ## Cost and proceeds, positive only
        allowable_costs=abs(open_value) + open_tax + open_comm 
        disposal_proceeds=abs(close_value) - close_tax - close_comm 
        
        average_open_price= abs(open_value) / abs_quantity
        average_close_price= abs(close_value) / abs_quantity
        
        ## Values are done on cash flow basis, so we can add up
        gross_profit = open_value+close_value
        
        net_profit = gross_profit - taxes - commissions 
        gbp_net_profit = net_profit*fxrate

        if net_profit<0:
            pandl="LOSS"
        else:
            pandl="PROFIT" 

        assert reportinglevel in ["VERBOSE", "NORMAL", "BRIEF", "ANNUAL"]
        
        if reportinglevel in ["VERBOSE", "NORMAL", "BRIEF"]:
            """ 
            Don't report if annual
            """
            if reportinglevel in ["VERBOSE", "NORMAL"]:
                report.write(star_line())
                report.write("\n")
            
            if CGTCalc:
    
                """
                Example of CGT output
                1. SELL: 40867 XYZ (Stock) on 17/12/2013 at EUR0.911 gives LOSS of XYZ 8,275.00 equals GBP 5,000
                
                (or CLOSE SHORT:  . Matches with OPEN SHORT: )
                
                Matches with: 
                BUY: SAME DAY TRADES.
                TRADES WITHIN 30 days 
                SECTION 104 HOLDING. 40867 shares of XYZ bought at average price of EUR1.11333
                
                """
                
                report.write("%s: %s %d %s %s on %s at %s %.6f gives %s of %s %s equals GBP %s\n" % \
                      (groupid, labels[1], int(abs_quantity), code, assetclass, datelabel, currency, average_close_price, 
                       pandl, currency, "{:,.2f}".format(net_profit), "{:,.2f}".format(gbp_net_profit)))
    
                if reportinglevel in ["VERBOSE", "NORMAL"]:
                    report.write(" Commission %s %.2f and taxes %s %.2f on %s\n"% (currency, close_comm, currency, close_tax,labels[1]))
        
                    report.write("Total allowable cost %s %s   Total disposal proceeds %s %s\n" % \
                         (currency, "{:,.2f}".format(allowable_costs), currency,"{:,.2f}".format(disposal_proceeds))) 
                                
                    report.write("\nMatches with:\n")
                    if len(self.sameday)>0:
                        sameday_quantity=int(abs(self.sameday.final_position()))
                        sameday_avg_price=self.sameday.average_price()
                        sameday_tax=sum([trade.Tax for trade in self.sameday])
                        sameday_comm=sum([trade.Commission for trade in self.sameday])
                        
                        report.write("SAME DAY TRADE(S) Matches with %s of %d %s at average price of %s %.6f \n Commissions %s %.2f Taxes %s %.2f \n" % \
                          (labels[0], sameday_quantity, code, currency, sameday_avg_price, currency, sameday_comm, currency, sameday_tax))

                        if reportinglevel=="VERBOSE":
                            
                            ## Trade by trade breakdown
                            pass

                    
                    if len(self.withinmonth)>0:
                        withinmonth_quantity=self.withinmonth.final_position()
                        withinmonth_avg_price=self.withinmonth.average_price()
                        withinmonth_tax=sum([trade.Tax for trade in self.withinmonth])
                        withinmonth_comm=sum([trade.Commission for trade in self.withinmonth])
        
                        report.write("SUBSEQUENT TRADE(S) Within 30 days Matches with %s of %d %s at average price of %s %.6f \n Commissions %s %.2f Taxes %s %.2f  \n" % \
                          (labels[0], withinmonth_quantity, code, currency, withinmonth_avg_price, currency, withinmonth_comm, currency, withinmonth_tax))

                        if reportinglevel=="VERBOSE":
                            
                            ## Trade by trade breakdown
                            pass

                        
                    
                    if len(self.s104)>0:
                        s104_quantity=self.s104.final_position()
                        s104_avg_price=self.s104.average_price()
                        s104_tax=sum([trade.Tax for trade in self.s104])
                        s104_comm=sum([trade.Commission for trade in self.s104])
        
                        report.write("PRO-RATA SECTION 104 Holding  %d %s at average price of %s %.6f \n Commissions %s %.2f Taxes %s %.2f  \n" % \
                          ( s104_quantity, code, currency, s104_avg_price, currency, s104_comm, currency, s104_tax))

                        if reportinglevel=="VERBOSE":
                            
                            ## Trade by trade breakdown
                            pass
                    
                
            else:
                """
                Example of non CGT output
                
                SELL 40867 RSA (Stock) on 17/12/2013 at EUR0.911 gives net LOSS of EUR 8,275 equals GBP5,000.0
                AVERAGE price EUR .  Total commission: EUR   Total tax:  EUR 
                """
                
                report.write("\n%s: %s of %d %s %s on %s at %s %.6f Net %s of %s %s equals GBP %s" % \
                      (groupid, labels[1], int(abs_quantity), code, assetclass, datelabel, currency, average_close_price,
                       pandl, currency, "{:,.2f}".format(net_profit), "{:,.2f}".format(gbp_net_profit)))                       
                        
                       
                if reportinglevel in ["VERBOSE", "NORMAL"]:
                    report.write("\n%s at average price %.6f.  Total round-trip commission %s %.2f, and taxes %s %.2f" % \
                           (labels[0], average_open_price, currency, commissions, currency, taxes))
                
                    if reportinglevel=="VERBOSE":
                        
                        ## Trade by trade breakdown
                        pass
                

            if reportinglevel in ["VERBOSE", "NORMAL"]:
                report.write("\n")

        ## Need everything in GBP for summary tables
        
        gbp_gross_profit = gross_profit*fxrate
        
        gbp_commissions = commissions*fxrate
        gbp_taxes = taxes*fxrate

        gbp_disposal_proceeds = disposal_proceeds*fxrate
        gbp_allowable_costs = allowable_costs*fxrate
        
        gbp_gains  = max(gbp_net_profit, 0.0)
        gbp_losses = min(gbp_net_profit, 0.0) 
        
        ## Only one disposal per group
        number_disposals=1

        return (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
                gbp_commissions, gbp_taxes, gbp_gross_profit, gbp_net_profit)
        

def display_summary_tax(summary_taxdata, CGTCalc, taxyear, report):
            
        """
        taxdata contains a list of tuples
        ## Each tuplue (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
                commissions, taxes, gbp_gross_profit, gbp_net_profit)
    
        
        
        """    

        ## Unpack tuple
        (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
                gbp_commissions, gbp_taxes, gbp_gross_profit, gbp_net_profit) = summary_taxdata

        report.write(star_line())
        
        report.write("\n\n                Summary for tax year ending 5th April %d " % taxyear)
        report.write("\n\n                              Figures in GBP\n")


        if CGTCalc:
            report.write("Disposal Proceeds = %s, Allowable Costs = %s, Disposals = %d \n Year Gains = %s  Year Losses = %s PROFIT = %s\n" % \
                ("{:,.2f}".format(gbp_disposal_proceeds), "{:,.2f}".format(gbp_allowable_costs), 
                 number_disposals, "{:,.2f}".format(gbp_gains), "{:,.2f}".format(gbp_losses), "{:,.2f}".format(gbp_net_profit)))
            
        else:
            report.write("Gross trading profit %s, Commission paid %s, Taxes paid %s, Net profit %s\n" % \
              ("{:,.2f}".format(gbp_gross_profit), "{:,.2f}".format(gbp_commissions),
               "{:,.2f}".format(gbp_taxes), "{:,.2f}".format(gbp_net_profit)))
              
            report.write("\nNot included: interest paid, interest received, data and other fees, internet connection,...\n hardware, software, books, subscriptions, office space, Dividend income (report seperately)\n\n")
            
        report.write("\n\n")