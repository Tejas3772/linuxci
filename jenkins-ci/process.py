
import sys
import os
import argparse
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
from lib import bisect_lib as cb
# from lib import common_lib as cb
def fetch(sid,type):
    # print("1",path,"1")
    rrjson={}
    rjson=cb.read_json(cb.base_path+sid+'/'+sid+'.json')
    # print(rjson)
    att = str(type+'goodCommit')
    # print("rdf",rjson)
    if att in rjson:
        if rjson[att]:
            # print("COMMIT",rjson[att],"COMMIT")
            rrjson[att]=rjson[att]
        else:
            rrjson[att] = 'c664e16bb1ba1c8cf1d7ecf3df5fd83bbb8ac15a'
            cb.append_diff_json(cb.base_path+sid+'/'+sid+'.json',rrjson)
            # print("att preset but no value")
    else :
        # print("no att")

        rrjson[att] = 'c664e16bb1ba1c8cf1d7ecf3df5fd83bbb8ac15a'
        cb.append_diff_json(cb.base_path+sid+'/'+sid+'.json',rrjson)

    return rrjson[att]

def push(sid, goodcommit,type):
    gjson={}
    gjson[type+'goodCommit'] = goodcommit

    cb.append_diff_json(cb.base_path+sid+'/'+sid+'.json',gjson)
    return "UPDATED"
    
     


def process(*args):
    # print("process.py started")
    arg1=args[0]
    # print(type(arg1), "ARGS", arg1)
    sys.path.append(os.path.join(arg1))

    # print(sys.path)
    num = len(args)
    if num == 2:
        arg2=args[1]
        res = fetch(arg1,arg2)
    elif num ==3:
        arg2=args[1]
        arg3=args[2]
        res =push(arg1,arg2,arg3)
    else :
        raise ValueError("Arguments are not valid for good-commit")
    # print("prcoess.py end")
    return res


if __name__ == "__main__":
    argsi = sys.argv[1:]
    result = process(*argsi)
    print(result)
