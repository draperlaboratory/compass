#!/usr/bin/env python
# encoding: utf-8
"""Python client for OrientDB REST serivce"""

import urllib
import json

from compass.request import Request


RECORD_ID = '@rid'
ADMIN = ('admin', 'admin')
READER = ('reader', 'reader')
WRITER = ('writer', 'writer')


class CompassException(Exception):
    """General purpose Compass Exception Object"""
    pass


class BaseObject(object):
    """This is the base object for all Compass Objects"""
    data = {}
    rid = None
    _immutable = []

    def __init__(self, data):
        if data is None:
            data = {}

        self.data = data

    def save(self):
        """
        If an extending object has a save action,
        it will overwrite this method
        """
        pass
        
    def delete(self):
        """
        If an extending object has a delete action,
        it will overwrite this method
        """
        pass

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        if key in self._immutable:
            raise KeyError('%s is not editable' % (key))

        self.data[key] = value

    def __delitem__(self, key):
        if key in self._immutable:
            raise KeyError('%s is not editable' % (key))

        del self.data[key]


class Server(BaseObject):
    """This Object handles all Server-based interactions"""
    action = {
        'info': '%s/server',
        'disconnect': '%s/disconnect'
    }

    def __init__(self, url, username, password):
        super(Server, self).__init__(data=None)

        self.url = url
        self.username = username
        self.password = password
        self.request = Request(self.username, self.password)

    def info(self):
        """
        This method queries the server for all of the
        information related to it 
        """
        url = self.action['info'] % (self.url)
        response, content = self.request.get(url=url)

        if response.status == 200:
            self.data = json.loads(content)
            return
	elif response.status == 204:
	    return 
        else:
            raise CompassException(content)

        return self

    def disconnect(self):
        """Sends a disconnect request to the server"""
        url = self.action['disconnect'] % (self.url)
        self.request.get(url)

    def database(self, name, credentials=ADMIN, create=False, storage='memory'):
        """Sends a request the server for a database
        will both add new and query existing databases.
        
        Returns a Datase object
        """
        if create:
            url = Database.action['post'] % (self.url, name, storage)
            response, content = self.request.post(url=url, data=None)

            if response.status == 200:
                return self.database(name=name, credentials=ADMIN)
            else:
                raise CompassException(content)
        else:
            url = Database.action['get'] % (self.url, name)
            user, password = credentials
            request = Request(user, password)
            response, content = request.get(url=url)

            if response.status == 200:
                data = json.loads(content)
                return Database(self.url, name=name,
                                credentials=credentials, data=data).connect()
            else:
                raise CompassException(content)


class Database(BaseObject):
    """Database object"""
    action = {
        'connect': '%s/connect/%s',
        'get': '%s/database/%s',
        'post': '%s/database/%s/%s',
        'query': '%s/command/%s/%s/%s',
        'cluster': '%s/cluster/%s/%s'
    }

    def __init__(self, url, name, credentials, lang='sql', data=None):
        super(Database, self).__init__(data=None)

        self.url = url
        self.lang = lang
        self.name = name
        self.credentials = credentials
        self.request = Request(username=credentials[0],
                               password=credentials[1])

        if data is None:
            self.connect()
        else: 
            self.data = data

    def reload(self, callback=None):
        """This method will repopulate the 
        data property of for the Database object
        """
        url = self.action['get'] % (self.url, self.name)        
        response, content = self.request.get(url)

        if response.status == 200:
            self.data = json.loads(content)

            if callback is not None and hasattr(callback, '__call__'):
                callback()
        else:
            raise CompassException(content)

    def connect(self):
        """Creats a connection to the database"""
        url = self.action['connect'] % (self.url, self.name)        
        response, content = self.request.get(url)

        if response.status == 200:
            self.data = json.loads(content)
	elif response.status == 204:
	    pass
        else:
            raise CompassException(content)

        return self

    def cluster(self, class_name):
        """Queries the server for a Cluster object"""
        url = Cluster.action['get'] % (self.url, self.name, class_name)
        response, content = self.request.get(url)

        if response.status == 200:
            return Cluster(database=self, data=json.loads(content))
	elif response.status == 204:
	    pass
        else:
            raise CompassException(content)

    def klass(self, name, limit=20, create=False):
        """Sends a request the server for class information
        will both add new and query existing classes.
        
        Returns a Klass object
        """
        if create:
            url = Klass.action['post'] % (self.url, self.name, name)
            response, content = self.request.post(url, data={})

            if response.status == 201:
                return self.klass(name=name)
            else: 
                raise CompassException(content)
        else:
            url = Klass.action['get'] % (self.url, self.name, name, limit)
            response, content = self.request.get(url)

            if response.status == 200:
                data = json.loads(content)

                if data.has_key('result'):
                    data = data['result']
                else:
                    data = None;

                return Klass(database=self, name=name,
                    documents=data)
            else:
                raise CompassException(content)

    def query(self, query, klass=None):
        """Sends a reqeust to the server based on a query"""
        query = urllib.quote(query)
        url = self.action['query'] % (self.url, self.name, self.lang, query)
        response, content = self.request.post(url, data={})

        if response.status == 200:
            result = json.loads(content)
            
            if isinstance(klass, Klass):
                klass.define_documents(result['result'], reset=True)
            else:
                return Klass(database=self, documents=result['result'])
        else:
            raise CompassException(content)

    def document(self, rid=None, class_name=None, **data):
        if rid:
            rid = rid.replace("#", "", 1)
            url = Document.action['get'] % (self.url, self.name, rid)
            response, content = self.request.get(url)

            if response.status == 200:
                return Document(rid, json.loads(content), database=self)
            else:
                raise CompassException(content)            
        else:
            if class_name is not None:
                data['@class'] = class_name

            url = Document.action['post'] % (self.url, self.name)
            response, content = self.request.post(url, data=data)
	    content = json.loads(content)
	    rid = content[RECORD_ID]
	    rid = rid.replace("#", "", 1)
            if response.status == 201:
                return self.document(rid=rid, database=self)
            else:
                raise CompassException(content)


class Cluster(BaseObject):
    action = {
        'get': '%s/cluster/%s/%s'
    }
    
    def __init__(self, database, data):
        super(Cluster, self).__init__(data)
        self.database = database
                

class Klass(BaseObject):
    action = {
        'get': '%s/class/%s/%s/%s',
        'post': '%s/class/%s/%s'
    }
    
    def __init__(self, database, name=None, schema=None, documents=None):
        super(Klass, self).__init__(data=None)
        
        self.name = name
        self.database = database
        
        if schema is None:
            schema = {}
        
        self.schema = schema
        
        self.define_documents(documents)

    def define_documents(self, documents=None, reset=False):    
        if documents is None:
            documents = {}
            
        if reset:
            self.data = {}
            
        keys = self.data.keys()
        
        for data in documents:
            if data[RECORD_ID] not in keys:
                self.data[data[RECORD_ID]] = Document(data[RECORD_ID], 
                                                      data, klass=self)
    
    def query(self, query):
        return self.database.query(query=query, klass=self)

    def document(self, rid=None, **data):
        return self.database.document(rid=rid, class_name=self.name, **data)
        
    def property(self, name, create=True):
        if create and name not in self.schema:
            try:
                prop = KlassProperty(name=name, klass=self,
                                     callback=self._define_schema)
            except CompassException:
                raise
                
        elif name in self.schema:
            prop = self.schema[name]
            
            prop.delete()
            del self.schema[name]
                
    def _define_schema(self):
        for klass in self.database.data['classes']:
            if klass['name'] == self.name:                
                for prop in klass['properties']:
                    if klass['name'] not in self.schema:
                        self.schema[klass['name']] = KlassProperty(
                                                        name=prop['name'],
                                                        klass=self, data=prop)


class KlassProperty(BaseObject):
    action = {
        'post': '%s/property/%s/%s/%s',
        'delete': '%s/property/%s/%s/%s'
    }
    
    def __init__(self, name, klass, data=None, callback=None):
        super(KlassProperty, self).__init__(data=None)
        
        self.name = name
        self.klass = klass
        
        if callback is not None:
            self._create(callback=callback)
        
    def delete(self):
        url = self.action['delete'] % (self.klass.database.url, 
                                       self.klass.database.name, 
                                       self.klass.name, self.name)
        response, content = self.klass.database.request.delete(url)

        if response.status != 204:
            raise CompassException(content)
            
    def _create(self, callback):
        url = self.action['post'] % (self.klass.database.url, 
                                     self.klass.database.name, 
                                     self.klass.name, self.name)
        response, content = self.klass.database.request.post(url, data={})

        if response.status == 201:
            self.klass.database.reload(callback=callback)
        else:
            raise CompassException(content)
    

class Document(BaseObject):
    action = {
        'get': '%s/document/%s/%s',
        'post': '%s/document/%s',
        'put': '%s/document/%s',
        'delete': '%s/document/%s/%s'
    }
    _immutable = ['@rid']
    
    def __init__(self, rid, data, database=None, klass=None):
        super(Document, self).__init__(data)

        rid = rid.replace("#", "", 1)
        
        self.rid = rid
        self.database = database
        self.klass = klass
        
        if self.database is not None:
            self.db_url = self.database.url
            self.db_name = self.database.name
            self.db_request = self.database.request
        else:
            self.db_url = self.klass.database.url
            self.db_name = self.klass.database.name
            self.db_request = self.klass.database.request
        
    def save(self):
        url = self.action['put'] % (self.db_url, self.db_name)
        response, content = self.db_request.put(url=url, data=self.data)

        if response.status == 200:
            return self
        else:
            raise CompassException(content)
            
    def relate(self, field, document=None, rid=None, multiple=False):
        if document is not None:
            rid = document[RECORD_ID]
        
        if multiple:
            if isinstance(self[field], list):
                ids = self[field]
                
                if rid not in ids:
                    ids.append(rid)
                
                self[field] = ids
        else:
            self[field] = rid
            
        return self
        
    def delete(self):
        url = self.action['delete'] % (self.db_url, self.db_name, self.rid)
        response, content = self.db_request.delete(url=url)
        
        if response.status != 204:
            raise CompassException(content)
