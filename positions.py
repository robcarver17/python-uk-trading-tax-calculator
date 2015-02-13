import pandas as pd
from utils import type_and_sense_check_arguments
from trades import THRESHOLD

class Position(object):
    """
    A position object contains our current position in something
    """

    def _possible_args(self):
        return self._required_columns()+self._optional_columns()
    
    def _required_columns(self):
        return ['Code',  'Position']

    def _optional_columns(self):
        return []


    def _type_check(self):
        arg_types=dict(Code=str,  Position=float)
        return arg_types

    
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

    
    def modify(self, **kwargs):

        modpositions=type_and_sense_check_arguments(self, kwargs, checkrequired=False)
        
        argsused=self.argsused

        for key in modpositions:
            setattr(self, key, modpositions[key])
            argsused.append(key)
            
        argsused=list(set(argsused))    
        setattr(self, 'argsused', argsused)

        
            
    def __repr__(self):
        ans=", ".join(["%s:%s" % (name, str(getattr(self, name))) for name in self.argsused])
        return ans


class PositionList(list):
    '''
    A PositionList object is a list of positions
    
    
    '''

    def as_dict(self):
        ans=dict([(x.Code, x.Position) for x in self])
        return ans

def tax_calc_dict_umatched_as_positions(taxcalc_dict):
    """
    Return a PositionList object containing the unmatched trades
    """
    result=PositionList()
    
    for code in taxcalc_dict.keys():
        position=taxcalc_dict[code].unmatched.final_position()
        result.append(Position(Code=code, Position=position))

    return result

def list_breaks(dict1, dict2):
    """
    Returns a dataframe of breaks
    """
    results=compare_position_dicts(dict1, dict2)
    ans=results[results.Break==True]
    ans.sort("Code")
    return ans

def not_matching_position(x, y):

    if abs(x-y)>THRESHOLD:
        return False

def compare_position_dicts(dict1, dict2):
    """
    Compare two position dicts to see if any break
    """
    
    codes1=dict1.keys()
    codes2=dict2.keys()
    joint_codes=list(set(codes1+codes2))
    
    pos1=[dict1.get(code,0) for code in joint_codes]
    pos2=[dict2.get(code,0) for code in joint_codes]
    any_break=[not_matching_position(pos1[idx], pos2[idx]) for idx in range(len(joint_codes))]

    results=pd.DataFrame(dict(Code=joint_codes, Position1=pos1, Position2=pos2, Break=any_break))
    
    return results

def compare_trades_and_positions(all_trades, all_positions):
    """
    Compares the final positions imputed from a list of trades, and a list of positions.
    
    Good sanity check
    """

    posdict1=all_trades.final_positions_as_dict()
    posdict2=all_positions.as_dict()
    
    return list_breaks(posdict1, posdict2)
    
