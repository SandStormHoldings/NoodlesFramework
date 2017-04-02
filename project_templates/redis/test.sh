#!/bin/bash
ITEMS=10000
CONC=$1
echo 'cleaning' &&
    curl 'http://127.0.0.1:8090/clean' &&
    echo 'writing' &&
    ab -c$CONC -n$ITEMS 'http://127.0.0.1:8090/write' &&
    echo 'checking' &&
    echo 'keys *mdls*' | redis-cli  | wc -l &&
    echo 'resetting' &&  
    curl 'http://127.0.0.1:8090/reset' &&
    echo 'reading' &&
    ab -c$CONC -n$ITEMS 'http://127.0.0.1:8090/read' &&
    echo 'done'
