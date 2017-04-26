import datetime
import sys

from sqlalchemy import create_engine, MetaData


now = datetime.datetime.now

echo = True
db = create_engine('mysql://root@localhost/backlog', echo=echo)
dbs = {'db': db}
meta = MetaData()

# aspect_tbl = Table('aspect',meta
#                  ,Column('name',Unicode(32),primary_key=True,unique=True))
# class Aspect(object): pass
# mapper(Aspect,aspect_tbl)


# create tables
if __name__ == '__main__' \
        and len(sys.argv) > 1 and sys.argv[1] == 'create_all':

    for dbn, db in dbs.items():
        print('creating & dropping all tables on %s' % dbn)
        meta.drop_all(db)
        meta.create_all(db)
