"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


import sys
from trades import Trade, THRESHOLD
from tradelist import TradeList
from utils import tax_year, star_line,pretty

zero_tax_tuple=(0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0)


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
    

    def group_display_taxes(self, taxyear, CGTCalc, reportinglevel, groupid=0, report=None):

        ## Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        ##        number_disposals, commissions, taxes, gross profit

        if report is None:
            report=sys.stdout

        if not self._in_tax_year(taxyear):
            ## print nothing, return zero tuples
            return zero_tax_tuple


        ## Put all the matching opening trades into one list
        matchinglist=self.matches_as_tradelist()
        
        fxrate=self.fxrate()
        
        ## Values, done on cashflow basis. -ve means buy, +ve means sell
        close_value=self.closingtrade.Value
        open_value=sum([trade.Value for trade in matchinglist])

        
        close_tax=self.closingtrade.Tax
        close_comm=self.closingtrade.Commission
        open_tax=sum([trade.Tax for trade in matchinglist])
        open_comm=sum([trade.Commission for trade in matchinglist])
        
        ## Fees, all positive
        taxes=open_tax+close_tax
        commissions=open_comm+close_comm

        ## Cost and proceeds, positive only
        ## We reverse these for short sales
        
        if close_value>0:
            ## Normal, close with a sell
            allowable_costs=abs(open_value) + open_tax + open_comm 
            disposal_proceeds=abs(close_value) - close_tax - close_comm 
        else:
            disposal_proceeds=abs(open_value) + open_tax + open_comm 
            allowable_costs=abs(close_value) - close_tax - close_comm 
            
        
        ## Values are done on cash flow basis, so we can add up
        gross_profit = open_value+close_value
        
        net_profit = gross_profit - taxes - commissions 
        gbp_net_profit = round(net_profit*fxrate)

        self._print_tax_details(report, reportinglevel, CGTCalc,  net_profit, open_value, close_value,
                          groupid, gbp_net_profit, open_comm, close_comm, open_tax, close_tax, allowable_costs,
                          disposal_proceeds, commissions, taxes)

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
        
    def _print_tax_details(self, report, reportinglevel, CGTCalc,  net_profit, open_value, close_value,
                          groupid, gbp_net_profit, open_comm, close_comm, open_tax, close_tax, allowable_costs,
                          disposal_proceeds, commissions, taxes):
    
        code=self.closingtrade.Code
        currency=self.closingtrade.Currency
        
        assetclass=(getattr(self.closingtrade, "AssetClass",""))
            
        datelabel=self.closingtrade.Date.strftime('%d/%m/%Y') 
    
    
        ## quantity will be negative for a closing sale / opening buy
        sign_quantity=self.closingtrade.SignQuantity
    
        abs_quantity=abs(sign_quantity)
    
    
        average_open_value= abs(open_value) / abs_quantity
        average_close_value= abs(close_value) / abs_quantity
    
    
        ## Labelling
        if sign_quantity<0:
            labels=("BUY", "SELL")
            signs=("-", "")
        else:
            labels=("OPEN SHORT", "CLOSE SHORT")
            signs=("+","-")
    
        if net_profit<0:
            pandl="LOSS"
        else:
            pandl="PROFIT" 

        ## Calculation strings, build up to show how we calculated our profit or loss
        calc_string="%s(%d*%s) - %s - %s " % \
        (signs[1], int(abs_quantity), pretty(average_close_value, commas=False), pretty(close_comm), pretty(close_tax))


    
        assert reportinglevel in ["VERBOSE", "CALCULATE", "NORMAL", "BRIEF", "ANNUAL"]
        
        if reportinglevel in ["VERBOSE", "CALCULATE","NORMAL", "BRIEF"]:
            """ 
            Don't report if annual
            """
            if reportinglevel in ["VERBOSE", "CALCULATE","NORMAL"]:
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
                
                report.write("%d: %s %d %s %s on %s at %s %s each gives %s of %s %s equals GBP %s\n" % \
                      (groupid, labels[1], int(abs_quantity), code, assetclass, datelabel, currency, pretty(average_close_value), 
                       pandl, currency, pretty(round(net_profit)), pretty(gbp_net_profit)))
    
                if reportinglevel in ["VERBOSE", "CALCULATE","NORMAL"]:
                    report.write(" Commission %s %s and taxes %s %s on %s\n"% (currency, pretty(close_comm), currency, pretty(close_tax),labels[1]))
        
                    if reportinglevel=="VERBOSE":
                        report.write("Trade details:"+self.closingtrade.__repr__()+"\n")
        
                    report.write("Total allowable cost %s %s   Total disposal proceeds %s %s\n" % \
                         (currency, pretty(allowable_costs), currency, pretty(disposal_proceeds))) 
                                
                    report.write("\nMatches with:\n")
                    if len(self.sameday)>0:
                        sameday_quantity=int(round(abs(self.sameday.final_position())))
                        sameday_avg_value=self.sameday.average_value()
                        sameday_tax=sum([trade.Tax for trade in self.sameday])
                        sameday_comm=sum([trade.Commission for trade in self.sameday])

                        sameday_calc_string="%s(%d*%s) - %s - %s " % \
                            (signs[0], sameday_quantity, pretty(sameday_avg_value, commas=False), pretty(sameday_comm), pretty(sameday_tax))

                        calc_string=calc_string+sameday_calc_string
                        
                        report.write("SAME DAY TRADE(S) Matches with %s of %d %s at average of %s %s each \n Commissions %s %s Taxes %s %s \n" % \
                          (labels[0], sameday_quantity, code, currency, pretty(sameday_avg_value), currency, pretty(sameday_comm), currency, pretty(sameday_tax)))
    
                        if reportinglevel == "VERBOSE":
                            report.write("\nTrades:\n")
                            self.sameday.print_trades_and_parents(report)
                                
                    
                    if len(self.withinmonth)>0:
                        withinmonth_quantity=int(abs(round((self.withinmonth.final_position()))))
                        withinmonth_avg_value=self.withinmonth.average_value()
                        withinmonth_tax=sum([trade.Tax for trade in self.withinmonth])
                        withinmonth_comm=sum([trade.Commission for trade in self.withinmonth])
                        
                        tradecount=len(self.withinmonth)
                        (startdate,enddate)=self.withinmonth.range_of_dates()

                        withinmonth_calc_string="%s(%d*%s) - %s - %s " % \
                            (signs[0], withinmonth_quantity, pretty(withinmonth_avg_value, commas=False), pretty(withinmonth_comm), pretty(withinmonth_tax))

                        calc_string=calc_string+withinmonth_calc_string
                        
        
                        report.write("SUBSEQUENT %d TRADE(S) Within 30 days between %s and %s: Matches with %s of %d %s at of %s %s each \n Commissions %s %s Taxes %s %s  \n" % \
                          (tradecount, str(startdate.date()), str(enddate.date()), labels[0], withinmonth_quantity, code, currency, pretty(withinmonth_avg_value), currency, pretty(withinmonth_comm), currency, pretty(withinmonth_tax)))
    
                        if reportinglevel == "VERBOSE":
                            report.write("\nTrades:\n")
                            self.withinmonth.print_trades_and_parents(report)

                    
                    if len(self.s104)>0:
                        s104_quantity=int(round(abs(self.s104.final_position())))
                        s104_avg_value=self.s104.average_value()
                        s104_tax=sum([trade.Tax for trade in self.s104])
                        s104_comm=sum([trade.Commission for trade in self.s104])

                        tradecount=len(self.s104)
                        (startdate,enddate)=self.s104.range_of_dates()
                        parent_quantity=self.s104.total_including_parents()

                        s104_calc_string="%s(%d*%s) - %s - %s " % \
                            (signs[0], s104_quantity, pretty(s104_avg_value, commas=False), pretty(s104_comm), pretty(s104_tax))

                        calc_string=calc_string+s104_calc_string
        
                        report.write("PRO-RATA SECTION 104 Holding of %f %s allocated out from total of %s trades between %s and %s at average value of %s %s \n Commissions %s %s Taxes %s %s  \n" % \
                          ( s104_quantity, code, int(parent_quantity), str(startdate.date()), str(enddate.date()), currency, pretty(s104_avg_value), currency, pretty(s104_comm), currency, pretty(s104_tax)))

                        if reportinglevel == "VERBOSE":
                            report.write("\nTrades:\n")
                            self.s104.print_trades_and_parents(report)

    
                    if reportinglevel in ["VERBOSE","CALCULATE"]:
                        
                        ## Show full calculations
                        report.write("\nCALCULATION: "+calc_string+" = %s \n" % pretty(round(net_profit)))
                
            else:
                """
                Example of non CGT output
                
                SELL 40867 RSA (Stock) on 17/12/2013 at EUR0.911 gives net LOSS of EUR 8,275 equals GBP5,000.0
                AVERAGE price EUR .  Total commission: EUR   Total tax:  EUR 
                """
                
                report.write("%d: %s of %d %s %s on %s at %s %s each Net %s of %s %s equals GBP %s\n" % \
                      (groupid, labels[1], int(abs_quantity), code, assetclass, datelabel, currency, pretty(average_close_value),
                       pandl, currency, pretty(round(net_profit)), pretty(gbp_net_profit)))                       

                if reportinglevel=="VERBOSE":
                    
                    report.write("Trade details:"+self.closingtrade.__repr__()+"\n")
                    
                        
                       
                if reportinglevel in ["VERBOSE", "NORMAL", "CALCULATE"]:
                    
                    tradecount=len(self.s104)
                    (startdate,enddate)=self.s104.range_of_dates()
                    parent_quantity=self.s104.total_including_parents()

                    closing_calc_string="%s(%d*%s) - %s - %s " % \
                        (signs[0], int(abs_quantity), pretty(average_open_value, commas=False), pretty(open_comm), pretty(open_tax))

                    calc_string=calc_string+closing_calc_string

        
                    report.write("\n%s at average value %s each between %s and %s.  Total round-trip commission %s %s, and taxes %s %s" % \
                           (labels[0], pretty(average_open_value), str(startdate.date()), str(enddate.date()), currency, pretty(commissions), currency, pretty(taxes)))
                
                    
                    if reportinglevel == "VERBOSE":
                        ## Trade by trade breakdown
                        report.write("\nTrades:\n")
                        self.s104.print_trades_and_parents(report)
                        pass

                    if reportinglevel in ["VERBOSE",  "CALCULATE"]:
 
                        ## calculations
                        report.write("\nCALCULATION: "+calc_string+" = %s \n" % pretty(round(net_profit)))
    
            if reportinglevel in ["VERBOSE", "NORMAL", "CALCULATE"]:
                report.write("\n")
    