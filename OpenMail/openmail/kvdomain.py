# class for IDomain implementations

import os
import StringIO
from twisted.internet import interfaces, defer, reactor
from twisted.cred import portal, credentials, checkers
from twisted.cred.error import UnauthorizedLogin
from twisted.mail import mail
from twisted.mail import pop3
from twisted.mail.maildir import AbstractMaildirDomain, StringListMailbox, DirdbmDatabase
from zope.interface import implementer
from openmail.kvcred import RiakPasswordChecker
from openmail.kvmailbox import KVMailbox
from openmail.kvstore import RiakKV

INTERNAL_ERROR = '''\
From: Twisted.mail Internals
Subject: An Error Occurred

  An internal server error has occurred. Please contact the
  server administrator.
'''

class KVdirMessage(mail.FileMessage):
    size = None

    def __init__(self, address, fp, *a, **kw):
        header = "Delivered-To: %s\n" % address
        fp.write(header)
        self.address = address
        self.size = len(header)
        self.finalName = a[1]
        print self.finalName
        self.kv = RiakKV()
        mail.FileMessage.__init__(self, fp, *a, **kw)
        
    def lineReceived(self, line):
        mail.FileMessage.lineReceived(self, line)
        self.size += len(line)+1

    def eomReceived(self):
        # got the entire msg, now stash it into k-v store
        contents = self.fp.getvalue()  # from StringIO
        self.fp.close()
        # write contents to k-v store
        self.kv.new_message(self.address, contents)
        return defer.succeed(self.finalName)

    def connectionLost(self):
        self.fp.close()

def _generateMaildirName():
    import time
    return 'foo%d' % int(time.time())

@implementer(portal.IRealm)
class KVDomain(AbstractMaildirDomain):
    """
    A Maildir Domain where membership is checked from k-v store
    """

    portal = None
    _credcheckers = None

    def __init__(self, service, root, postmaster=0):
        """
        Initialize.

        The first argument is where the Domain directory is rooted.
        The second is whether non-existing addresses are simply
        forwarded to postmaster instead of outright bounce

        The directory structure of a MailddirDirdbmDomain is:

        /passwd <-- a dirdbm file
        /USER/{cur,new,del} <-- each user has these three directories
        """
        AbstractMaildirDomain.__init__(self, service, root)

        self.db = RiakKV()
        self.postmaster = postmaster
        self._credcheckers = [ RiakPasswordChecker() ]


    # override this from AbstractMaildirDomain
    def startMessage(self, user):
        """
        Save a message for the given C{user}.
        """
        if isinstance(user, str):
            name, domain = user.split('@', 1)
        else:
            name, domain = user.dest.local, user.dest.domain
        username = self.userDirectory(name)
        dir = '/dev/shm/test/%s' % username
        fname = _generateMaildirName()
        filename = os.path.join(dir, 'tmp', fname)
        fp = StringIO.StringIO()
        return KVdirMessage('%s@%s' % (name, domain), fp, filename,
                              os.path.join(dir, 'new', fname))


    def userDirectory(self, name):
        """Get the directory for a user

        If the user exists in the dirdbm file, return the directory
        os.path.join(root, name), creating it if necessary.
        Otherwise, returns postmaster's mailbox instead if bounces
        go to postmaster, otherwise return None
        """
        if not self.db.has_key(name):
            
            #if not self.postmaster:
            #    return None
            #name = 'postmaster'
            self.db.new_user(name)
        return name  # ok

    ##
    ## IDomain
    ##
    def addUser(self, user, password):
        self.db.add_user(user)

    def getCredentialsCheckers(self):
        if self._credcheckers is None:
            self._credcheckers = [DirdbmDatabase(self.dbm)]
        return self._credcheckers

    ##
    ## IRealm
    ##
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pop3.IMailbox not in interfaces:
            raise NotImplementedError("No interface")
        if avatarId == checkers.ANONYMOUS:
            mbox = StringListMailbox([INTERNAL_ERROR])
        else:
            mbox = KVMailbox('/'+avatarId)

        return (
            pop3.IMailbox,
            mbox,
            lambda: None
        )

