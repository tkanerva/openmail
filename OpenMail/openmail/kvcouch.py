import json
import time
from hashlib import sha1
from twisted.internet import defer, reactor, task
from riakasaurus import riak

import paisley 

HEADER,BODY,META = range(3)

class CouchKV(object):
    def __init__(self):
        self.db = paisley.CouchDB('localhost')
        self.buckets = {HEADER: "mailheader", BODY: "mailbody", META: "mailmeta}
        self.rev_cache = {}  # couch needs to keep track of revs
        d = self.db.listDB()
        def cb1(r):
            print(r.getResult())
        d.addCallback(cb1)

    @defer.inlineCallbacks
    def _get(self, bucket, key):
        # buckets are equal to databases in couch
        r = yield self.db.openDoc(self.buckets[bucket], key)
        self.rev_cache[key] = r.get('_rev')
        if bucket == BODY:
            r = r.get('data')
        defer.returnValue( r)

    @defer.inlineCallbacks
    def _put(self, bucket, key, val):
        # couch needs to have the rev id of current doc.
        rev = self.rev_cache[key]
        if bucket == BODY:
            val_ = {'data': val, '_rev':rev}
        else:
            val_ = val.update({'_rev':rev})
        r = yield self.db.saveDoc(self.buckets[bucket], val_, key)
        defer.returnValue( r)

    @defer.inlineCallbacks
    def _delete(self, bucket, key):
        # need the rev id!
        r = yield self.db.deleteDoc(self.buckets[bucket], val)

    @defer.inlineCallbacks
    def new_message(self, user, contents):
        user = user.partition('@')[0]  # kludge, FIXME
        print "DEBUG: new_message to: ",user
        key = sha1(contents).hexdigest()
        r = yield self._put(BODY, key, contents)
        r = yield self.update_user_metadata(user, key, len(contents))

    @defer.inlineCallbacks
    def get_user_metadata(self, user):
        try:
            data = yield self._get(META, user)
        except KeyError:
            data = None
        defer.returnValue(data)

    @defer.inlineCallbacks
    def put_user_metadata(self, user, data):
        try:
            res = yield self._put(META, user, data)
        except Exception:
            res = False
        defer.returnValue(res)

    @defer.inlineCallbacks
    def update_user_metadata(self, user, key, size):
        new = {key:{"timestamp":int(time.time()), "size":size}}
        try:
            data = yield self.get_user_metadata(user)
        except KeyError:
            print "error, ABORTING update_metadata"
        else:
            print "update OLD:",data,type(data)
            data.update(new)
            print "update NEW:",data
            res = yield self.put_user_metadata(user, data)
            defer.returnValue(res)
