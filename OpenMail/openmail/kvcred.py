# TODO: should abstract out k-v operations and create a lowlevel module for Riak
#
import os

from zope.interface import implements, Interface, Attribute
from twisted.internet import defer
from twisted.python import failure, log
from twisted.cred import error, credentials, checkers
from twisted.internet import defer

from riakasaurus import riak


ANONYMOUS = ()


class AllowAnonymousAccess:
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = credentials.IAnonymous,

    def requestAvatarId(self, credentials):
        return defer.succeed(ANONYMOUS)


class RiakPasswordChecker:
    """
    A Riak key-value datastore credentials checker.
    """

    implements(checkers.ICredentialsChecker)

    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    riak_port = 8098
    cred_bucket = 'cred'

    def __init__(self):
        self.riakclient = riak.RiakClient()
        self.bucket = self.riakclient.bucket(self.cred_bucket)

    def _user_exists(self, username):
        d = self.bucket.get(username)
        d.addCallback(lambda obj: obj.exists())
        return d

    def _user_get(self, username):
        d = self.bucket.get(username)
        d.addCallback(lambda obj: obj.get_data())
        return d

    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def requestAvatarId(self, credentials):
        def _cbExists(res):
            def _cbGotUser(userdata):
                passwd = userdata.get('password')
                return defer.maybeDeferred(
                    credentials.checkPassword,
                    passwd.encode('ascii')).addCallback(self._cbPasswordMatch, str(credentials.username))
            if res:
                print "DEBUG: user DOES exist."
                d = self._user_get(credentials.username)
                d.addCallback(_cbGotUser)
                return d
            else:
                print "DEBUG: user %s DOES NOT exist." % str(credentials.username)
                return defer.fail(error.UnauthorizedLogin())
        d = self._user_exists(credentials.username)
        d.addCallback(_cbExists)
        return d
