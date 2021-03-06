# Copyright 2018 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import json
from pathlib2 import Path

import blitzdb
from blitzdb import fields
import sqlalchemy
from traitlets import HasTraits, Instance, default


class AnnotationDB(HasTraits):
    """ An in-memory JSON database of object and function annotations.
    
    The class contains no Python-specific annotation logic. For that,
    see `flowgraph.kernel.trace.annotator`.
    """
    
    # Underlying in-memory database backend.
    _database = Instance(blitzdb.backends.base.Backend)
    
    def load_documents(self, notes):
        """ Load annotations from an iterable of JSON documents
        (JSON-able dictionaries).
        """
        for note in notes:
            if note['schema'] == 'annotation' and note['language'] == 'python':
                doc = Annotation(note)
                doc.pk = note['_id']
                self._database.save(doc)
    
    def load_file(self, filename):
        """ Load annotations from a JSON file.
        
        Typically annotations will be loaded from a remote database but this
        method is useful for local testing.
        """
        with Path(filename).open('r') as f:
            self.load_documents(json.load(f))

    def get(self, query):
        """ Get a single document matching the query.
        
        Returns the document or None if no document matches the query.
        Raises a LookupError if there are multiple matches.
        """
        notes = list(self.filter(query))
        if len(notes) > 1:
            raise LookupError("Multiple matches for query %r" % query)
        return notes[0] if notes else None
    
    def filter(self, query):
        """ Get all documents matching the query.
        
        Returns an iterable.
        """
        blitz_query = { key: query.pop(key) for key in list(query.keys())
                        if key in Annotation.fields.keys() or 
                           key.startswith('$') }
        blitz_result = self._database.filter(Annotation, blitz_query)
        return (doc.attributes for doc in blitz_result
                if self._query_json(query, doc.attributes))
    
    # Private interface
    
    def _query_json(self, query, obj):
        """ Recursively match a JSON query against a JSON object.
        """
        # XXX: This is a quick hack to work around the BlitzDB SQL backend's 
        # requirement that query fields be indexed and unstructured.
        # When BlitzDB is improved or replaced, this function should be deleted.
        if isinstance(query, dict):
            if not isinstance(obj, dict):
                return False
            for key in query.keys():
                if key.startswith('$'):
                    raise NotImplementedError("MongoDB operators not implemented")
                if not (key in obj and self._query_json(query[key], obj[key])):
                    return False
            return True
        else:
            return query == obj
    
    # Trait initializers
    
    @default('_database')
    def _database_default(self):
        """ Create SQL backend with in-memory SQLite database.
        """
        engine = sqlalchemy.create_engine('sqlite://') 
        backend = blitzdb.backends.sql.Backend(engine) 
        backend.register(Annotation)
        backend.init_schema()
        backend.create_schema()
        return backend


class Annotation(blitzdb.Document):
    """ Partial schema for annotation.
    
    Treat this class as an implementation detail of AnnotationDB.
    """
    # XXX: The BlitzDB SQL backend does not support changing the primary key.
    #class Meta(blitzdb.Document.Meta):
    #    primary_key = '_id'
    #
    #_id = fields.CharField(nullable=False, indexed=True)
    
    language = fields.CharField(nullable=False, indexed=True)
    package = fields.CharField(nullable=False, indexed=True)
    id = fields.CharField(nullable=False, indexed=True)
    kind = fields.EnumField(['type', 'function'], nullable=False, indexed=True)
    
    function = fields.CharField(nullable=True, indexed=True)
    method = fields.CharField(nullable=True, indexed=True)
