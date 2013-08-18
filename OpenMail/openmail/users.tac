# user management

import time
from twisted.application import internet, service
from twisted.web.server import Site
from twisted.internet import reactor, defer, ssl, task
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.python import log
from twisted.cred import portal
from twisted.web.guard import BasicCredentialFactory,HTTPAuthSessionWrapper
from openmail.mycred import PasswordDictChecker,HttpPasswordRealm

from klein import run, route, resource, Klein
from zope.interface import implements

from riakasaurus import riak

import myhtml  # for custom DSL
from openmail.testcss import mystyle2


# UI for adding / modifying users
formdefaults = {'login':'NONE'
                ,'name':'NONE'
                ,'password':'NONE'
                }
dsl = '''NewMailUser
login:CharField -> label:Login size:10 value:%(login)s
name:CharField -> label:Name size:25 value:%(name)s
password:PasswordField -> label:Password size:25 value:x
submit:SubmitField
'''

BUCKET = None
BUCKET_META = None

class MyUI(object):
    app = Klein()

    def __init__(self):
        self.init_stuff()

    def init_stuff(self):
        global BUCKET, BUCKET_META
        cli = riak.RiakClient()
        BUCKET = cli.bucket('cred')
	BUCKET_META = cli.bucket('mailmeta')
    
    @inlineCallbacks
    def getcred(self, key):
        obj = yield BUCKET.get(key)
        returnValue(obj.get_data())

    # testing out
    @app.route("/newUser/source", methods=['GET'])
    def newuser_source(self, request):
	import inspect
    	p = request.path
	base = p.split('/')[-2]  # take the second last
	print base
	fun = getattr(self, base.lower())
    	request.write('testing testing.<p>')
	request.write('<pre>')
	request.write(inspect.getsource(fun).replace('<','['))
	request.write('</pre>')


    # for creating new users
    @app.route("/newUser", methods=['GET'])
    def newuser(self, request):
        myform = myhtml.renderForm(myhtml.parse(dsl % formdefaults), action='/newUser', method='POST')
        header = '<html><head><title>new user</title>'+ '<style type="text/css" media="screen">'+ mystyle2 + '</style></head>'

        request.write(header + '<body><h3>New Email User</h3><div id="container">')

        form2 = str(myform).replace('NONE','').replace('_',' ').replace('<label>Login','<fieldset><legend>User info</legend><div class="fm-req"><label>Login')
        form2 = form2.replace('</form>','</div></div></form>')
        request.write(form2)
        request.write('</body></html>')

    @app.route("/newUser", methods=['POST'])
    @inlineCallbacks
    def newuser_post(self, request):
        a = request.args
        login = a.get('login')[0]
        name = a.get('name')[0]
        pw = a.get('password')[0]
        timestamp = int(time.time())
        if len(pw) < 8:
            request.write('<b>Password was too short! need min. 8 characters.</b>')
        else:
            data = {"name":name, "password":pw, "timestamp":timestamp}
            obj = BUCKET.new(login, data)
            yield obj.store()  # store to Riak
	    meta = BUCKET_META.new(login, {})
	    yield meta.store()
            print('saved new entry to users!')
            request.write('Added new user %s.' %(login))
        request.write('<p><a href="/viewUsers">Return.</a>')

    @app.route("/modifyUser/<string:login>", methods=['GET'])
    @inlineCallbacks
    def modifyuser(self, request, login):
        curdata = yield self.getcred(login)
        mod_dsl = dsl.replace('NewEmailUser','ModifyUser')
        d = curdata
        d.update({'login':login})
        myform = myhtml.renderForm(myhtml.parse(mod_dsl), action="/modifyUser", method="POST")
        header = '<html><head><title>new user</title>'+ '<style type="text/css" media="screen">'+ mystyle2 + '</style></head>'
        request.write(header + '<body><h3>Modify User</h3><div id="container">')
        form2 = str(myform).replace('NONE','').replace('<label>Login','<fieldset><legend>User info</legend><div class="fm-req"><label>Login')
        form2 = form2.replace('</form>','</div></div></form>')
        tmp = str(form2) % d
        request.write(tmp.encode('ascii'))
        request.write('</body></html>')

    @app.route("/modifyUser", methods=['POST'])
    @inlineCallbacks
    def modifyuser_post(self, request):
        a = request.args
        login = a.get('login', 'none')[0]
        data = yield self.getcred(login)
        name = a.get('name')[0]
        password = a.get('password')[0]
        # check!
        if len(password) < 8:
            request.write('<b>Password was too short! need min. 8 characters.</b>')
        else:
            data.update({"name":name, "password":password,"timestamp":int(time.time())})
            obj = BUCKET.new(login, data)
            yield obj.store()
            print('saved modified entry to users!')
            request.write('Modified user %s. ' % (login))
        request.write('<p><a href="/viewUsers">Return.</a>')

    @app.route("/viewUsers")
    @inlineCallbacks
    def viewusers(self, request):
        users = yield BUCKET.list_keys()
        fields = ['login', 'name', 'password']
        lst = ['<th>%s</th>'%x for x in fields]
        request.write('<table> %s ' % ''.join(lst))
        for i in users:
            user = yield self.getcred(i)
            print type(user)
            print user
            d = {}
            d['login'] = i
            d['name'] = user['name']
            d['password'] = '*****'  # do not show!
            s1 = '''<tr><td> <a href="/modifyUser/%(login)s">%(login)s</a> </td><td>
            %(name)s </td><td> %(password)s </td> </tr>'''%d
            request.write(s1.encode('ascii'))
        request.write('</table> <h3>Click on "login" to edit the fields of a specific user.</h3>')
        request.write('<h3>Click <a href="/newUser">here to create a new user.</a></h3>')

passwords = {"admin":CONFIG.adminui_passwd}

application = service.Application("my_ui")
myresource = MyUI().app.resource()
checker = PasswordDictChecker(passwords)
realm = HttpPasswordRealm(myresource)
p = portal.Portal(realm, [checker])
credentialFactory = BasicCredentialFactory("UI")
protected_resource = HTTPAuthSessionWrapper(p, [credentialFactory])
ctxt_factory = ssl.DefaultOpenSSLContextFactory('server.key', 'server.crt')
myService = internet.SSLServer(8002, Site(protected_resource), ctxt_factory)

myService.setServiceParent(application)
