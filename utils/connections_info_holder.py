# -*- coding: utf-8 -*-
"""
filedesc: stores traceback on db connect
@author: Yura A
"""
from gevent import getcurrent
from functools import partial
from traceback import extract_stack, format_list

from noodles.utils.helpers import get_config


CONNECTIONS_INFO_HOLDER = {}
CONNECTIONS_COUNTER = {}
POOL_SIZES = {}
RAW_TRACEBACK = get_config('DEBUG_GREENLET_RAW_TRACEBACK', False)


def exhaust(shard_id):
    result = POOL_SIZES[shard_id] <= len(CONNECTIONS_INFO_HOLDER[shard_id]) + 2
    return result


def print_holder(req_greenlet_id, shard_id):
    slot = CONNECTIONS_INFO_HOLDER[shard_id]
    i = 1
    print('requested by greenlet_id', req_greenlet_id)
    for k, v in slot.items():
        (greenlet_id, tb, parallel) = v
        print(i, ',', 'shard#', shard_id, ' greenlet#', greenlet_id,)
        if parallel:
            print('\033[1;31mParallel shards execution!\033[1;m')
        print(''.join(format_list(tb)))
        i += 1
    print(shard_id, '>', '*' * 60)


def trace_conn_checkout(
        shard_id,
        dbapi_connection,
        connection_record,
        connection_proxy):
    greenlet = getcurrent()
    greenlet_id = id(greenlet)
    parrallel_exec = hasattr(greenlet, '_stack')
    stack = getattr(greenlet, '_stack') if parrallel_exec else extract_stack()
    if not RAW_TRACEBACK:
        stack = filter(lambda x: 'GameServer/src' in x[0], stack)
        stack = map(lambda x: (x[0].partition('GameServer/src')[2], x[1], x[2], x[3]), stack)
        stack = stack[:-1]
    connection_id = id(connection_record)
    CONNECTIONS_INFO_HOLDER[shard_id][connection_id] = (greenlet_id, stack, parrallel_exec)
    if exhaust(shard_id):
        print_holder(greenlet_id, shard_id)


def trace_conn_checkin(
        shard_id,
        dbapi_connection,
        connection_record):
    greenlet_id = getcurrent()
    connection_id = id(connection_record)
    if connection_id in CONNECTIONS_INFO_HOLDER[shard_id]:
        del CONNECTIONS_INFO_HOLDER[shard_id][connection_id]


_STORE_TRACE_FNS = {
    'checkin': trace_conn_checkin,
    'checkout': trace_conn_checkout
}


def hold_stack(action, pool_size, shard_id):
    """
    ** HOWTO
    from sqlalchemy import event  # using core events

    # create high-order listener functions with shard id and pool size
    on_checkin = hold_stack('checkin', _POOL_SIZE, shard_id)
    on_checkout = hold_stack('checkout', _POOL_SIZE, shard_id)

    # set listeners as usual
    event.listen(engine, 'checkin', on_checkin)
    event.listen(engine, 'checkout', on_checkout)
    """
    CONNECTIONS_INFO_HOLDER[shard_id] = {}
    POOL_SIZES[shard_id] = pool_size
    return partial(_STORE_TRACE_FNS[action], shard_id)


def conns_info():
    return CONNECTIONS_INFO_HOLDER


def count_conn_checkin(shard_id, *_, **__):
    CONNECTIONS_COUNTER[shard_id] -= 1


def count_conn_checkout(shard_id, *_, **__):
    CONNECTIONS_COUNTER[shard_id] += 1


_STORE_COUNTER_FNS = {
    'checkin': count_conn_checkin,
    'checkout': count_conn_checkout
}


def hold_count(action, shard_id):
    CONNECTIONS_COUNTER[shard_id] = 0
    return partial(_STORE_COUNTER_FNS[action], shard_id)


def conns_counters():
    return CONNECTIONS_COUNTER
