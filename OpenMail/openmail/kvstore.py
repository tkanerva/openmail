import json
import time
from hashlib import sha1
from twisted.internet import defer, reactor, task
from riakasaurus import riak

HEADER,BODY,META = range(3)

class RiakKV(object):
    def __init__(self):
        self.riakclient = riak.RiakClient()
        self.buckets = {}
        # TODO: change naming scheme of buckets to multi-app
        self.buckets[HEADER] = self.riakclient.bucket('mailheader')
        self.buckets[BODY] = self.riakclient.bucket('mailbody')
        self.buckets[META] = self.riakclient.bucket('mailmeta')

    @defer.inlineCallbacks
    def _get(self, bucket, key):
        print '_GET %s %s' % (bucket, key)
        if bucket == BODY:  # read as plain-text
            obj = yield self.buckets[bucket].get_binary(key)
        else:
            obj = yield self.buckets[bucket].get(key)
        if not obj.exists():  # should raise an exception or not?
            defer.returnValue(None)
            #raise KeyError
        data = obj.get_data()
        # TODO: need sibling handling
        defer.returnValue( data)

    @defer.inlineCallbacks
    def _put(self, bucket, key, val):
        print '_PUT %s %s' % (bucket,key)
        if bucket == BODY:  # write plain-text
            obj = self.buckets[bucket].new_binary(key, val, content_type='text/plain')
        else:
            obj = self.buckets[bucket].new(key, val)
        yield obj.store()  # TODO Error checking!

    @defer.inlineCallbacks
    def _delete(self, bucket, key):
        print '_DELETE %s %s' % (bucket,key)
        obj = yield self.buckets[bucket].get(key)
        ret = yield obj.delete()
        defer.returnValue(ret)

    def getmail(self, user, mailid):
        return self._get(BODY, mailid)  # should return a Deferred

    @defer.inlineCallbacks
    def new_message(self, user, contents):
        user = user.partition('@')[0]  # kludge, FIXME
        print "DEBUG: new_message to: ",user
        key = sha1(contents).hexdigest()
        r = yield self._put(BODY, key, contents)  # write BODY
        r = yield self.update_user_metadata(user, key, len(contents))

    @defer.inlineCallbacks
    def delete_messages(self, user, mailids):
        for key in mailids:
            try:
                res = yield self._delete(BODY, key)
            except KeyError:
                print "tried to delete mail %d, but failed." % mailids
        data = yield self.get_user_metadata(user)
        if not data:
            print "ERROR: could not get user metadata"
            res = False
        else:
            for i in mailids:  # after deleting the BODies, get rid of metadata
                del data[i]
            res = yield self.put_user_metadata(user, data)
        defer.returnValue(res)

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

    @defer.inlineCallbacks
    def list_messages(self, user):
        metadata = yield self.get_user_metadata(user)
        sizes = [metadata[k]['size'] for k in metadata]
        defer.returnValue(sizes)

    @defer.inlineCallbacks
    def has_key(self, key):
        res = yield self._get(META, key)
        defer.returnValue(False if not res else True)

    @defer.inlineCallbacks
    def new_user(self, name):
        res = yield self._put(META, name, {})
        
@defer.inlineCallbacks
def main(*args):
    # some test code
    mr = RiakKV()
    our_user = 'testiuseri'
    md = yield mr.get_user_metadata(our_user)
    mailid = md.keys()[0]
    ts = md[mailid]['timestamp']
    print 'MAILID:', mailid
    print 'SIZE:', md[mailid]['size']
    print 'TIMESTAMP:', time.asctime(time.gmtime(ts))
    mail = yield mr.getmail(our_user, mailid)
    print mail
    defer.returnValue( mail)

if __name__=='__main__':
    task.react(main, [])

