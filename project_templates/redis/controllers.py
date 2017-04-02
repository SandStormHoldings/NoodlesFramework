# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import XResponse
import hashlib
from noodles.datastore import Model,Value
import redis

rc = redis.Redis(host='localhost')

seed = '1234'
writekey = seed


class Mdl(Model):
    RedisConn = rc
    #key = Value()

def index(request):
    return XResponse({'result':'hello, world.'})

def write(request):
    global writekey
    newkey = hashlib.md5(writekey.encode('utf-8'))
    writekey = newkey.hexdigest()
    m = Mdl()
    m.id = writekey
    m.save()
    return XResponse({'newkey':writekey,
                      'val':m.id})

def read(request):
    global writekey
    newkey = hashlib.md5(writekey.encode('utf-8'))
    nkhd = newkey.hexdigest()
    m = Mdl()
    m.get(nkhd)
    writekey = nkhd
    return XResponse({'read':newkey.hexdigest()})
    #m.get(
    
def clean(request):
    global rc,writekey,seed
    writekey=seed
    rc.flushall()
    return XResponse({'result':'ok',
                      'writekey':writekey})

def reset(request):
    global rc,writekey,seed
    writekey=seed
    return XResponse({'result':'ok',
                      'writekey':writekey})
