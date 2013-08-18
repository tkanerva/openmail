
from twisted.application import internet, service
from twisted.web.server import Site
from twisted.internet import reactor, defer, ssl, task
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.python import log
from twisted.cred import portal
from twisted.web.guard import BasicCredentialFactory,HTTPAuthSessionWrapper
from twisted.web.resource import Resource, IResource

from openmail.kvcred import RiakPasswordChecker

from klein import run, route, resource, Klein
from zope.interface import implements

from webmail import MyWebMail
from pop3server import POP3Protocol, POP3Factory, MailUserRealm

from openmail_config import CONFIG


class HttpPasswordRealm(object):
    implements(portal.IRealm)

    def __init__(self, myresource):
        self.myresource = myresource

    def requestAvatar(self, user, mind, *interfaces):
        if IResource in interfaces:
            # myresource is passed on regardless of user
            return (IResource, self.myresource, lambda: None)
        raise NotImplementedError()


application = service.Application("openmail")
myresource = MyWebMail().app.resource()
checker = RiakPasswordChecker()
realm = HttpPasswordRealm(myresource)
p = portal.Portal(realm, [checker])
credentialFactory = BasicCredentialFactory("OpenMail")
protected_resource = HTTPAuthSessionWrapper(p, [credentialFactory])
ctxt_factory = ssl.DefaultOpenSSLContextFactory('server.key', 'server.crt')
webService = internet.SSLServer(8001, Site(protected_resource), ctxt_factory)

webService.setServiceParent(application)

dataDir = CONFIG.datadir_pop
popFactory = POP3Factory()
popFactory.portal = portal.Portal(MailUserRealm(dataDir))
passwordChecker = RiakPasswordChecker()
popFactory.portal.registerChecker(passwordChecker)
popService = internet.TCPServer(8110, popFactory)

popService.setServiceParent(application)

