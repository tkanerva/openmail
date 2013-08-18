import os
from twisted.mail import pop3, maildir
from twisted.cred import portal, checkers, credentials, error as credError
from twisted.internet import protocol, reactor, defer
from twisted.python import log
from zope.interface import implements
from openmail.kvmailbox import KVMailbox
from openmail.kvcred import RiakPasswordChecker


class UserInbox(KVMailbox):
    def __init__(self, foo):
        KVMailbox.__init__(self, foo)

class POP3Protocol(pop3.POP3):
    debug = True

    def sendLine(self, line):
        if self.debug: print "POP3 SERVER:", line
        pop3.POP3.sendLine(self, line.encode('ascii'))

    def lineReceived(self, line):
        if self.debug: print "POP3 CLIENT:", line
        pop3.POP3.lineReceived(self, line)

class POP3Factory(protocol.Factory):
    protocol = POP3Protocol
    portal = None

    def buildProtocol(self, address):
        p = self.protocol()
        p.portal = self.portal
        p.factory = self
        return p

class MailUserRealm(object):
    implements(portal.IRealm)
    
    avatarInterfaces = {
        pop3.IMailbox: UserInbox,
        }
    
    def __init__(self, baseDir):
        self.baseDir = baseDir

    def requestAvatar(self, avatarId, mind, *interfaces):
        username = avatarId
        for requestedInterface in interfaces:
            if requestedInterface in self.avatarInterfaces:
                userDir = os.path.join(self.baseDir, username)
                if not os.path.exists(userDir):
                    print "DEBUG: os.mkdir()"
                    os.mkdir(userDir)
            # return an instance of the correct class
            avatarClass = self.avatarInterfaces[requestedInterface]
            print avatarClass
            avatar = avatarClass(userDir)
            #d = avatar._build_indices()
            #d.addCallback(lambda _: avatar)
            logout = lambda: None
            return defer.succeed((requestedInterface, avatar, logout))
        raise KeyError("None of the requested interfaces are supported")

class CredentialsChecker(object):
    implements(checkers.ICredentialsChecker)

    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def __init__(self, passwords):
        """passwords: a dict-like object that maps user->pass"""

        self.passwords = passwords

    def requestAvatarId(self, credentials):
        username = credentials.username

        if username in self.passwords:
            realPassword = self.passwords[username]
            checking = defer.maybeDeferred(credentials.checkPassword, realPassword)
            # pass result of checkPassword and the username under auth, to self._checkedPassword
            checking.addCallback(self._checkedPassword, username)
            return checking
        else:
            raise credError.UnauthorizedLogin("No such user")


    def _checkedPassword(self, matched, username):
        if matched:
            # password was correct
            return username
        else:
            raise credError.UnauthorizedLogin("Bad password")


def main():
    import sys
    dataDir = sys.argv[1]
    log.startLogging(sys.stdout)
    factory = POP3Factory()
    factory.portal = portal.Portal(MailUserRealm(dataDir))
    passwordChecker = RiakPassword()
    factory.portal.registerChecker(passwordChecker)
    reactor.listenTCP(int(sys.argv[2]), factory)
    reactor.run()

if __name__=='__main__':
    main()


            
