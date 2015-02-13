import datetime
from copy import copy

from utils import type_and_sense_check_arguments, signs_match, repr_class

THRESHOLD=0.0001    

class Trade(object):

    def _possible_args(self):
        return self._required_columns()+self._optional_columns()
    
    def _required_columns(self):
        return ['Code', 'Commission', 'Price', 'Quantity', 'Tax', 'Date',  'Currency']

    def _optional_columns(self):
        return self._optional_columns_misc()+self._optional_columns_values()+self._optional_columns_fx()+ \
            self._optional_columns_allocation()
        
    def _optional_columns_misc(self):
        return ['AssetClass', 'parent']
        
    def _optional_columns_values(self):
        return ['Value', 'SignQuantity', 'BS']

    def _optional_columns_fx(self):
        return ['FXRate']
        
    def _optional_columns_allocation(self):
        return ['tradetype', 'pseudotrade','sharedtrade', 'TradeID']

    def _has_fx_data(self):
        return all([x in self.argsused for x in self._optional_columns_fx()]) 
    
    def _has_allocation_data(self):
        return all([x in self.argsused for x in self._optional_columns_allocation()]) and \
            "SignQuantity" in self.argsused
    
    def _ready_for_split(self):
        """
        Can this trade be split? 
        """
        return self._has_fx_data() and self._has_allocation_data()
        
    
    def _type_check(self):
        arg_types=dict(Code=str, Commission=float, Price=float, Quantity=float, Tax=float, Date=datetime.datetime, 
                       BS=str, Currency=str,  Value=float, 
                       SignQuantity=float, FXRate=float, AssetClass=str,
                       tradetype=str, pseudotrade=bool, sharedtrade=bool, TradeID=str, parent=Trade)

        return arg_types

    def _check_inputs(self):
        if self.Commission<0.0:
            raise Exception("can't have negative commssion")
        if self.Tax<0.0:
            raise Exception("can't have negative tax")
        if self.Quantity<0:
            raise Exception("Quantity can't be negative (you're confusing with SignQuantity")
        if "SignQuantity" in self.argsused:
            if "Quantity" in self.argsused and "BS" in self.argsused:
                checksignquant = self._signed_quantity()
                
                if checksignquant!=self.SignQuantity:
                    raise Exception("Signed quantity of %d not consistent with quantity of %d and BS of %s" % 
                                    (self.SignQuantity, self.Quantity, self.BS))

        if "typestring" in self.argsused:
            assert self.typestring in ["Open", "Close", "OverClose"]

        if "Value" in self.argsused:
            assert not signs_match(self.Value, self.SignQuantity) 
        
    def __init__(self, **kwargs):

        '''
        Constructor 
        
        
        '''

        type_and_sense_check_arguments(self, kwargs)

        argsused=[]
        for key in kwargs:
            argsused.append(key)
            setattr(self, key, kwargs[key])

        setattr(self, 'argsused', argsused)
        self._check_inputs()
    
    def modify(self, **kwargs):

        modorderfill=type_and_sense_check_arguments(self, kwargs, checkrequired=False)
        argsused=self.argsused

        for key in modorderfill:
            setattr(self, key, modorderfill[key])
            argsused.append(key)
            
        argsused=list(set(argsused))    
        setattr(self, 'argsused', argsused)
        
        self._check_inputs()

    def __repr__(self):
        return "Code: %s Sign Date %s Quantity %.2f tradeType %s" % (self.Code, str(self.Date), self.SignQuantity, self.tradetype)

    def full(self):
        print repr_class(self)

    def add_value(self, raiseerror=True):
        if "Value" in self.argsused and raiseerror:
            raise Exception("Can't add_value on trade as Value field already set")
        
        if not "SignQuantity" in self.argsused:
            self.add_signed_quantity()
        
        ## Cash flow method. Negative means buy ...
        value= - self.Price * self.SignQuantity
        self.modify(Value=value)
        
        return self

    def bslabel(self):
        if "BS" in self.argsused:
            return self.BS
        
        if "SignQuantity" in self.argsused:
            if self.SignQuantity>0:
                return "BUY"
            elif self.SignQuantity<0:
                return "SELL"
        
        return "Unknown"

    
    def _signed_quantity(self):
        if "BS" not in self.argsused:
            raise Exception("can't add signed quantity without BUY or SELL") 
        
        if self.BS=="BUY":
            multiplier=1
        elif self.BS=="SELL":
            multiplier=-1
        else:
            raise Exception("BS can't be %s" % self.BS)
        
        sign_quantity=multiplier * self.Quantity
        
        return sign_quantity

    def add_signed_quantity(self):
        if "SignQuantity" in self.argsused:
            raise Exception("Already have signed quantity")
        
        sign_quantity=self._signed_quantity()
        self.modify(SignQuantity=sign_quantity)
        
        return self

        
    def _init_allocation(self, tradetype):
        
        if not self._has_fx_data():
            raise Exception("Can't do an allocation without fx data, Value and SignQuantity")
        
        self.modify(tradetype=tradetype, pseudotrade=False, sharedtrade=False)

        
    def share_of_trade(self, share=None, pro_rata=None):
        """
        Returns a trade, a clones of self, with quantity share or a pro_rata proportion
        
        """
        
        assert not (share is None and pro_rata is None)
        
        newtrade=copy(self)
        oldquantity=copy(self.SignQuantity)

        if pro_rata is None:
            assert type(share) is float
            assert signs_match(share, oldquantity)
            assert abs(share)<=abs(oldquantity)

            pro_rata=share/oldquantity

        if share is None:
            assert type(pro_rata) is float 
            assert pro_rata>0.0 and pro_rata<1.0

            share=oldquantity*pro_rata

        
        newtrade.modify(Value=self.Value*pro_rata, Commission=self.Commission*pro_rata, Tax=self.Tax*pro_rata, 
                        SignQuantity=share, Quantity=abs(share),   
                        )
        
        return newtrade
        
    def spawn_pseudo_trades(self, tradetoclose):
        """
        Returns a new clone trade with tradetoclose, and a residual clone trade
        
        """
        if not self._ready_for_split():
            raise Exception("You need to have done added fx and allocation data to this trade")

        oldquantity=copy(self.SignQuantity)
        
        residualtrade=oldquantity - tradetoclose

        assert type(tradetoclose) is float
        assert signs_match(tradetoclose, oldquantity)
        assert abs(tradetoclose)<=abs(oldquantity)
        assert abs(tradetoclose)>0.0
        
        neworder=self.share_of_trade(share=tradetoclose)
        changedorder=self.share_of_trade(share=residualtrade)
        
        neworder.modify(tradetype="Close")
        changedorder.modify(tradetype="Open")
        
        neworder.modify(pseudotrade=True)
        changedorder.modify(pseudotrade=True)

        oldtradeid=self.TradeID
        neworder.modify(TradeID=oldtradeid+":1")
        changedorder.modify(TradeID=oldtradeid+":2")
        
        ## To avoid duplications we make the opening order a second after the old one
        newdate=changedorder.Date+datetime.timedelta(seconds=1)
        changedorder.modify(Date=newdate)
        
        return [changedorder, neworder]

    