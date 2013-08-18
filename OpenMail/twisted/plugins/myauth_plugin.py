from zope.interface import implements
from twisted import plugin
from twisted.cred.strcred import ICheckerFactory
from twisted.cred import credentials
from openmail.kvcred import RiakPasswordChecker

class RiakPasswordFactory(object):
    """
    A checker factory for a specialized API.
    """

    implements(ICheckerFactory, plugin.IPlugin)

    credentialInterfaces = (credentials.IUsernamePassword,credentials.IUsernameHashedPassword)

    # this tells AuthOptionsMixin how to find this factory.
    authType = "riak"

    argStringFormat = "A port number where Riak is listening."

    authHelp = """An authentication plugin that uses a Riak backend."""

    def generateChecker(self, argstring=""):
        argdict = dict()
        return RiakPasswordChecker()

theRiakPasswordFactory = RiakPasswordFactory()
