"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.txt

"""


import datetime
from copy import copy
import numpy as np

from utils import  list_of_dict_class_to_pandas_df, uniquets, \
                   check_identical_attribute, signs_match, signs_match_list, any_duplicates

THRESHOLD=0.0001    

class TradeList(list):
    '''
    A trade_list object is a list of trades
    
    
    '''

    def separatecode(self):
        """
        Returns a trade_dict, with codes seperated out
        """
        codes=[x.Code for x in self]
        all_codes=list(set(codes))
        results=TradeDictByCode([(Code, TradeList([trade for trade in self if trade.Code==Code])) 
                                 for Code in all_codes])
        
        return results
    
    def _seperatefx(self):
        """
        Returns a trade_dict, with FX seperated out
        
        """
        currency=[x.Currency for x in self]
        all_ccy=list(set(currency))
        results=TradeDictByFX([(Currency, TradeList([trade for trade in self if trade.Currency==Currency])) 
                               for Currency in all_ccy])
    
        return results
    
    def check_same_currency(self):
        ## Returns True if all elements are same currency
        return check_identical_attribute(self, "Currency")
    
    def check_same_code(self):
        ## Returns True if all elements have same Code
        return check_identical_attribute(self, "Code")
    
    def check_same_sign(self):
        signs=[np.sign(trade.SignQuantity) for trade in self]
        return signs_match_list(signs)
    
    def timestampsort(self):
        """
        Sorts into TS order
        """
        return TradeList(sorted(self, key=lambda x: x.Date))

    def add_signed_quantities(self):
        """
        Add an extra column, signed quantities
        """
        return TradeList([trade.add_signed_quantity() for trade in self if "SignQuantity" not in trade.argsused])
    
    def add_values(self,  raiseerror=True):
        """
        Add values
        """
        return TradeList([x.add_value(raiseerror=raiseerror) for x in self])
    
    
    def final_position(self):

        if len(self)==0:
            return 0.0

        if not self.check_same_code():
            raise Exception("You can't produce final position as not same code")
        
        quant_series=[x.SignQuantity for x in self]
        
        return sum(quant_series)
    
    def final_positions_as_dict(self):
        return self.separatecode().final_positions_as_dict()

    def average_value(self):
        ## Return average value (absolute)
        quantity=self.final_position() 
        
        ## can be zero
        if quantity==0.0:
            return np.nan
        
        values=sum([trade.Value for trade in self])
        
        return abs(values/quantity)
    
    def as_dataframe(self, indexby="Date"):
        
        return list_of_dict_class_to_pandas_df(self, indexby)
    
    def add_fxdict_rates(self, fx_dict):
        """
        
        """
        self=self._seperatefx().add_fx_rates(fx_dict).as_joint_list()
        
    def _add_onefx_rate(self, fxmat):
        """
        Add the fx rates in the pandas dataframe or timeseries fxmat to our trades
        
        Assumes we have the right FX rate, hence hidden
        """
        
        if not self.check_same_currency():
            raise Exception("You can't apply FX rate as different currencies in TradeList")
        
        dataframe=self.as_dataframe().sort()
        fxmat=uniquets(fxmat)
        fxmat=fxmat.reindex(dataframe.index, method="ffill")
        [self[idx].modify(FXRate=float(fxmat[idx])) for idx in range(len(self))]
        
        
    def all_currencies(self):
        """
        Unique list of currencies used
        """
        return list(set(self.as_dataframe().Currency))
    
    def date_sort(self):
        self.sort(key=lambda x: x.Date)
    
    def _cumulative_trades(self):

        self.date_sort()
        self.add_signed_quantities()
        

        if not self.check_same_code():
            raise Exception("You can't get cumulative trade data as not same code")

        ## return the cumulative trade
        return list(np.cumsum([x.SignQuantity for x in self]))
        
    
    def add_tradeids(self):
        
        existing_ids_exist=["TradeID" in trade.argsused for trade in self]
        
        if all(existing_ids_exist):
            existing_ids=[trade.TradeID for trade in self]
            if not any_duplicates(existing_ids):
                print "All trades have ID's - not renumbering"
                return None
            else:
                print "All trades have ID's but duplicates! *** renumbering"
        
        self.timestampsort()
        [self[idx].modify(TradeID=str(idx)) for idx in range(len(self))]
        
        
        
    
    def _add_cumulative_data(self):
        """
        Add the  'tradetype', 'pseudotrade' labels to each trade
        
        """
        
        ## Cumulative trade is effectively position        
        position=self._cumulative_trades()
        
        ## Trade type is determined by change from previous trade to this one
        tradetypes=["Open"]+[_return_trade_type(position[idx], position[idx-1]) 
                             for idx in range(len(position))[1:]]

        ## Add data to trades        
        [self[idx]._init_allocation(tradetype=tradetypes[idx]) for idx in range(len(self))]

        
        return self
    
    def list_of_overclosed_trades(self):

        trade_types=[trade.tradetype for trade in self]
        overclosed_trades=[idx for idx in range(len(trade_types)) if trade_types[idx]=="OverClose"]

        return overclosed_trades
    
    def list_of_closed_trades(self):

        trade_types=[trade.tradetype for trade in self]
        closed_trades=[idx for idx in range(len(trade_types)) if trade_types[idx]=="Close"]

        return closed_trades
        
    def idx_of_trades_before_datetime(self, tradetomatch):
        tradedatetime=tradetomatch.Date
        self.date_sort()
        idx_trades_before_datetime=[idx for idx in range(len(self)) if self[idx].Date<=tradedatetime]
        
        return idx_trades_before_datetime
        
        
    def idx_of_last_trade_same_day(self, tradetomatch):
        ## Return indices of trades with same date, executed prior to this trade, with opposite sign
        
        tradedatetime=tradetomatch.Date
        
        self.date_sort()
        
        tradedate=tradedatetime.date()
        
        listdatetimes=[trade.Date for trade in self]
        listdates=[x.date() for x in listdatetimes]
        listsignquant=[trade.SignQuantity for trade in self]
        
        ## done on same day, but not in future
        ## Future trades on same day will be picked up in 'within 30 days' rule
        same_day_trades=[idx for idx in range(len(listdates)) 
                         if listdates[idx]==tradedate and listdatetimes[idx]<tradedatetime
                         and not signs_match(listsignquant[idx], tradetomatch.SignQuantity)]
        
        if len(same_day_trades)==0:
            return None
        
        return same_day_trades[-1]
        
    def idx_of_first_trade_next_30days(self, tradetomatch):
        ## Return index of first trade done after this trade, with opposite sign, and within 30 days 

        self.date_sort()

        tradedatetime=tradetomatch.Date

        listdatetimes=[trade.Date for trade in self]
        listdates=[x.date() for x in listdatetimes]

        tradedate30daysafter=trade.Date.date()+datetime.timedelta(30)
        listsignquant=[trade.SignQuantity for trade in self]


        ## trades are in next 30 days or today, but not in the past
        ## and with opposite sign
        next_30days_trades=[idx for idx in range(len(listdates)) 
                            if listdates[idx]<=tradedate30daysafter and listdatetimes[idx]>tradedatetime
                            and not signs_match(listsignquant[idx], tradetomatch.SignQuantity)]

        if len(next_30days_trades)==0:
            return None

        ## Return the first trade
        return next_30days_trades[0]
    
    def _spawn_pseudo_trades(self):
        """
        Remove OverClose trades and add pseudo trades in place
        
        Returns trades removed 
        """
        
        old_final_position=copy(self.final_position())
        old_trade_count=copy(len(self))
        
        if not all([trade._has_allocation_data() for trade in self]):
            raise Exception("You can't add spawn pseudo trades without _add_cumulative_data first")
        
        removedtrades=TradeList()

        ## Cumulative trade is effectively position, overclosed_trades is list of indices  
        overclosed_trades=self.list_of_overclosed_trades()
        position=self._cumulative_trades()
        
        starting_count_overclosed=len(overclosed_trades)
        
        while len(overclosed_trades)>0:
            ## Find first overclose
            to_spawn=overclosed_trades[0]

            ## Need to have the previous position            
            assert to_spawn>0
            
            previous_position=float(position[to_spawn-1])
            new_trades=self[to_spawn].spawn_pseudo_trades(-previous_position)

            ## Drop the old trade
            removedtrades.append(self.pop(to_spawn))
            
            ## Add the new trades
            [self.append(trade) for trade in new_trades] 
            
            ## Date sort 
            self.date_sort()

            ## Recalculate, in case any left, and because we've changed size
            position=self._cumulative_trades()
            overclosed_trades=self.list_of_overclosed_trades()
    

        new_final_position=self.final_position()
        new_trade_count=len(self)
        
        assert old_final_position == new_final_position
        assert new_trade_count == starting_count_overclosed+old_trade_count
        
        return removedtrades
    
    def _pop_earliest_closing_trade(self):
        """
        Pops the earliest closing trade out of the list
        """
        
        self.date_sort()
        closed_index=self.list_of_closed_trades()
        
        if len(closed_index)==0:
            return None
        
        earliest_closing_trade=self.pop(closed_index[0])
        
        return earliest_closing_trade

    def _partial_pop_idx(self, tradeidx, maxtopop):
        """
        Pop the trade tradeidx, up to a limit of maxtopop
        
        If this trade is too big then leave behind a residual trade
        
        Returns the trade
        """
        old_final_position=copy(self.final_position())
        old_trade_count=copy(len(self))
        
        if not all([trade._has_allocation_data() for trade in self]):
            raise Exception("You can't add spawn pseudo trades without _add_cumulative_data first")
        
        tradetopop=self[tradeidx]
        
        
        
        assert signs_match(tradetopop.SignQuantity, maxtopop)
        
        if abs(tradetopop.SignQuantity)<=abs(maxtopop):
            ## Pop the entire trade
            finaltradetopop=self.pop(tradeidx)
            assert (len(self)+1) == old_trade_count

        else:
            ## Pop part of the trade, by spawing a child order
            (parent_trade, finaltradetopop)=tradetopop.spawn_child_trade(share=maxtopop)
            
            ## Remove the original trade
            self.pop(tradeidx)
            
            ## Add the residual trade
            self.append(parent_trade)
            
            assert len(self) == old_trade_count

        self.date_sort()

        assert self.final_position()+finaltradetopop.SignQuantity == old_final_position
        
        return finaltradetopop

        
    def _proportionate_pop_idx(self, tradeidxlist, totaltopop):
        """
        Reduce all trades in tradeidxlist by a proportion
        
        """

        old_final_position=copy(self.final_position())
        old_trade_count=copy(len(self))
        
        if not all([trade._has_allocation_data() for trade in self]):
            raise Exception("You can't add spawn pseudo trades without _add_cumulative_data first")

        original_trades_to_trim=TradeList([self[idx] for idx in tradeidxlist])
        
        total_in_list=original_trades_to_trim.final_position()
        
        assert signs_match(totaltopop, total_in_list)
        
        pro_rata=totaltopop/total_in_list
        
        residual = 1.0 - pro_rata
        
        if abs(residual)<THRESHOLD:
            residual=0.0
            pro_rata=1.0
            
        ## Returns list of tuples (parent, child)
        tradetuplelist=TradeList([tradetopop.spawn_child_trade(pro_rata=pro_rata) for tradetopop in original_trades_to_trim])

        ## remove original trades
        for trade in original_trades_to_trim:
            ## find matching trade (can't use original indices since will change with size of list)
            trade_idx=[idx for idx in range(len(self)) if self[idx]==trade]
            assert len(trade_idx)==1
            
            self.pop(trade_idx[0])

                    
        popped_trades=TradeList([tradetuple[1] for tradetuple in tradetuplelist])
        assert abs(totaltopop - popped_trades.final_position())<THRESHOLD

        ## Residual left behind...
        if residual>0.0:
            ## Put residual parent trades back in
            [self.append(tradetuple[0]) for tradetuple in tradetuplelist]

            assert len(self) == old_trade_count

        else:
            ## No residual trades, just pop in their entirity
            ## We've permanently lost these trades
            assert (len(self) + len(popped_trades)) == old_trade_count 

        self.date_sort()
        
        assert abs(self.final_position()+totaltopop - old_final_position)<THRESHOLD
        
        return popped_trades
                               
    def print_trades_and_parents(self,report):
        
        ## Print trade, and parent
        for trade in self:
            if "parent" in trade.argsused:
                parentstring=" (Allocated from: "+trade.parent.brief()+")"
            else:
                parentstring=""
            report.write(trade.__repr__()+parentstring+"\n")
    
    def range_of_dates(self):
        ## Return a tuple, with the range of dates
        
        if len(self)==0:
            return (None, None)
        
        datesinlist=[trade.Date for trade in self]
        datesinlist.sort()
        
        return (datesinlist[0], datesinlist[-1])

    def total_including_parents(self):
        ## If a parent exists, return that; otherwise return own
        
        totalsinlist=[trade.total_mine_or_parent() for trade in self]
        
        return sum(totalsinlist)

def _sign_change(x,y):
    if x>0 and y<0:
        return True
    elif x<0 and y>0:
        return True
    return False

def _return_trade_type(x, lastx):
    if _sign_change(x, lastx):
        return "OverClose"
    if abs(x)<abs(lastx):
        return "Close"
    return "Open"
    
        
class TradeDictByCode(dict):
    """
    A dict, each element of which is a trade_list
    
    Many methods are hidden, since they require the dict to be split in the right way first
    """
    
    
    def final_positions_as_dict(self):
        final_positions=dict([(code, self[code].final_position()) for code in self.keys()])
        return final_positions
    
    def as_joint_list(self):
        return from_tradedict_to_list(self)

    def add_cumulative_data(self):
        """
        Add the 'tradetype', 'pseudotrade', 'sharedtrade' labels to each trade, in each
        element of the code dict. 
        """
        [x._add_cumulative_data() for x in self.values()]
        return self
    
    def generate_pseduo_trades(self):
        """
        Removes trades with type 'OverClose' and generates two orders in place 
        """
        
        [x._spawn_pseudo_trades() for x in self.values()]
        return self
    
class TradeDictByFX(dict):
    """
    A dict, keys are currencies, each element of which is a trade_list
    
    """
    
    
    def add_fx_rates(self, fx_dict):
        """
        Add fx rates, given a dictionary of FX rates 
        """
        for ccy in self.keys():
            fxmat=fx_dict[ccy]
            self[ccy]._add_onefx_rate(fxmat)
        
        return self
    
    def as_joint_list(self):
        return from_tradedict_to_list(self)




def from_tradedict_to_list(tradedict):
    """
    Returns the dict joined together into one giant list
    """
    
    all_keys=tradedict.keys()
    results=[[x for x in tradedict[key]] for key in all_keys]
    results=sum(results, [])
    results=TradeList(results)
    
    return results

