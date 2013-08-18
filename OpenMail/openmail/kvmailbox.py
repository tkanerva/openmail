# key-value mailbox
#

import StringIO
from hashlib import md5
from twisted.internet import defer
from twisted.mail import pop3
from zope.interface import implements
from kvstore import RiakKV


class UserNotFoundError(Exception):
    pass

class KVMailbox(object):
    """ a mailbox that uses a key-value store """

    implements(pop3.IMailbox)

    def __init__(self, foo):
        self.kv = RiakKV()
        self.user = foo.split('/')[-1]  # pass the user in question
        self.metadata = {}
        self.deleteQueue = []
        return self._build_indices()

    def _build_indices(self):
        """build indices at start-up time"""
        d = self.kv.get_user_metadata(self.user)
        def _cb1(r):
            print 'DEBUG: callback invoked, metadata set'
            self.metadata = r
        d.addCallback(_cb1)
        return d

    def listMessages(self, i=None):
        """Return the length of the message at the given offset, or a list of all
        message lengths."""
        print "DEBUGGING: len=%d" % len(self.metadata)
        if i is not None:
            d = self.kv.list_messages(self.user)
            def cb_list(r):
                return r[i]  # only the requested item
            d.addCallback(cb_list)
            return d
        else:
            d = self.kv.list_messages(self.user)
            return d

    def _map_meta_to_idx(self, user):
        """create a mapping between POP3 request values [1..n] and message hash, sorted by timestamp"""
        def _gotMeta(metadata):
            stamps = sorted([k for k in metadata], key=lambda x: metadata[x]['timestamp'])
            mapping = enumerate(stamps)
            return dict(mapping)
        return _gotMeta(self.metadata)
        
    def getMessage(self, i):
        """ Return an in-memory file-like object for the message content at the given offset """
        mapping = self._map_meta_to_idx(self.user)
        def _got_mapping(mapping):
            mailId = mapping[i]
            d2 = self.kv.getmail('test', mailId)  # FIXME: user is not used.
            def _got_content(content):
                if content == None:
                    return StringIO.StringIO("From: system@localhost\nTo: user\nSubject: debug\n\ndebug: empty mail.")  # for hunting down the persistent metadata update bug
                if isinstance(content, unicode):
                    content = content.encode('ascii')  # kludge, FIXME
                return StringIO.StringIO(content)
            d2.addCallback(_got_content)
            return d2
        return _got_mapping(mapping)

    def getUidl(self, i):
        mapping = self._map_meta_to_idx(self.user)
        return mapping[i].encode('ascii')

    def _getUidl(self, i):
        print "getUidl for user:",self.user
        d = self._map_meta_to_idx(self.user)
        def _got_mapping(mapping):
            if not mapping:
                return defer.fail(UserNotFoundError)
            return mapping[i]
        d.addCallback(_got_mapping)
        return d

    def _deleteMsgs(self, lst):
        print "DEBUG: scheduled to delete %d msgs " % len(lst)
        if lst:
            d = self.kv.delete_messages(self.user, lst)
        else:
            d = defer.Deferred()
        return d

    def _deleteMsgMeta(self, i):
        mapping = self._map_meta_to_idx(self.user)
        try:
            del self.metadata[mapping[i]]
        except KeyError:
            print "cannot delete from metadata: %s does not exist in mapping." % i

    def deleteMessage(self, i):
        print "deleteMessage for user %s: %d" % (self.user,i)
        mapping = self._map_meta_to_idx(self.user)
        self.deleteQueue.append(mapping[i])

    def undeleteMessages(self):
        pass

    def sync(self):
        print "DEBUG: client called SYNC."
        print "queue: %s" % self.deleteQueue
        lst = []
        d = self._deleteMsgs(self.deleteQueue)
        lst.append(d)
        #self._deleteMsgMeta(item)  # we really don't need this; as it's just a cache for this session
        self.deleteQueue = []
        return defer.DeferredList(lst)
