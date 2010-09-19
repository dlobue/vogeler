import datetime, yaml

import couchdbkit as couch
from couchdbkit.loaders import FileSystemDocsLoader

from vogeler.exceptions import VogelerPersistenceException

class UnknownDatatype(Exception): pass

import logging

class null_handler(logging.Handler):
    def emit(self, record):
        pass

nh = null_handler()
logger = logging.getLogger('vogeler.db')
logger.addHandler(nh)

class SystemRecord(couch.Document):
    system_name = couch.StringProperty()
    created_at = couch.DateTimeProperty()
    updated_at = couch.DateTimeProperty()

class generic_transport(object):
    def connect(self, host, port):
        l = 'Opening connection to host %s on port %i' % (host, port)
        logger.debug(l)
        self._connect(host, port)

    def get_db(self, dbname):
        raise NotImplemented

    def drop_db(self, dbname):
        raise NotImplemented

    def get_record(self, record):
        raise NotImplemented


class mongo_transport(generic_transport):
    def _connect(self, host, port):
        self.server = pymongo.Connect(host, port)

    def get_db(self, dbname):
        self.db = db = self.server[dbname]
        return db

    def drop_db(self, dbname):
        return self.server.drop_database(dbname)

    def get_collection(self, cname):
        self.collection = collection = self.db[cname]
        return collection

    def get_record(self, record):
        return self.collection.get(record)

class couch_transport(generic_transport):
    db = None

    def _connect(self, host, port):
        connection_string = "http://%s:%s" % (host, port)
        self.server = couch.Server(uri=connection_string)

    def get_db(self, dbname):
        self.db = db = self.server.get_or_create_db(dbname)
        return db

    def drop_db(self, dbname):
        try: return self.server.delete_db(dbname)
        finally: self.db = None

    def get_record(self, record):
        return self.db.get(record)

class VogelerStore(object):

    def __init__(self, host, port, db, transport):
        self.dbname = db
        self.transport = transport(host, port)

    def create_db(self, dbname=None):
        if not dbname:
            dbname = self.dbname

        db = self.transport.get_db(dbname)
        self.db = db
        return db

    def drop_db(self, dbname=None):
        if not dbname:
            dbname = self.dbname

        self.transport.drop_db(dbname)

    def use_db(self, dbname=None):
        if not dbname:
            dbname = self.dbname

        self.db = self.transport.get_db(dbname)

    def create(self, node_name):
        node = SystemRecord.get_or_create(node_name)
        node.system_name = node_name
        node.created_at = datetime.datetime.utcnow()
        node.save()

    def get(self, node_name):
        node = self.db.get_record(node_name)
        return node

    def touch(self, node_name):
        node = self.get(node_name)
        node.updated_at = datetime.datetime.utcnow()
        node.save()

    def update(self, node_name, key, value, datatype):
        node = SystemRecord.get_or_create(node_name)

        try:
            datatype_method = getattr(self, '_update_%s' % datatype)
            node[key] = datatype_method(node, key, value)
        except AttributeError:
            raise UnknownDatatype("Don't know how to handle datatype '%r'" %
                                  datatype)

        node.updated_at = datetime.datetime.utcnow()
        node.save()

    def _update_output(self, node, key, value):
        v = [z.strip() for z in value.split("\n")]
        return v

    def _update_pylist(self, node, key, value):
        return value

    def _update_pydict(self, node, key, value):
        return value

    def _update_yaml(self, node, key, value):
        return value

    def _update_string(self, node, key, value):
        return value

    def _update_raw(self, node, key, value):
        return value


    def load_views(self, lp):
        self.loadpath = lp
        print "Loading design docs from %s" % lp
        loader = FileSystemDocsLoader(self.loadpath)
        loader.sync(self.db, verbose=True)
        print "Design docs loaded"
        return 0

# vim: set ts=4 et sw=4 sts=4 sta filetype=python :
