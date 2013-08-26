
import time
from twisted.application import internet, service
from twisted.web.server import Site
from twisted.internet import reactor, defer, ssl, task
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.python import log
from twisted.cred import portal
from twisted.web.guard import BasicCredentialFactory,HTTPAuthSessionWrapper

from klein import run, route, resource, Klein
from zope.interface import implements

from riakasaurus import riak

import myhtml  # for custom DSL
from testcss import mystyle2


# UI for adding / modifying users
formdefaults = {'login':'NONE'
                ,'name':'NONE'
                ,'password':'NONE'
                }
dsl = '''NewMailUser
login:CharField -> label:Login size:10 readonly:readonly value:%(login)s
name:CharField -> label:Name size:25 value:%(name)s
password:PasswordField -> label:Password size:25 value:x
submit:SubmitField
'''





class MyWebMail(object):
    app = Klein()
    buckets = {}
    def __init__(self):
        self.init_stuff()

    def init_stuff(self):
        cli = riak.RiakClient()
        self.buckets['cred'] = cli.bucket('cred')
	self.buckets['mailmeta'] = cli.bucket('mailmeta')
	self.buckets['mailbody'] = cli.bucket('mailbody')

    @inlineCallbacks
    def getcred(self, key):
        obj = yield self.buckets['cred'].get(key)
        returnValue( obj.get_data())

    # user mgmt here.
    @app.route("/profile", methods=['GET'])
    @inlineCallbacks
    def modifyuser(self, request):
        login = request.getUser()
        curdata = yield self.getcred(login)
        mod_dsl = dsl.replace('NewEmailUser','ModifyUser')
        d = curdata
        d.update({'login':login})
        myform = myhtml.renderForm(myhtml.parse(mod_dsl), action="/profile", method="POST")
        header = '<html><head><title>new user</title>'+ '<style type="text/css" media="screen">'+ mystyle2 + '</style></head>'
        request.write(header + '<body><h3>Modify User</h3><div id="container">')
        form2 = str(myform).replace('NONE','').replace('<label>Login','<fieldset><legend>User info</legend><div class="fm-req"><label>Login')
        form2 = form2.replace('</form>','</div></div></form>')

        tmp = str(form2) % d
        request.write(tmp.encode('ascii'))
        request.write('</body></html>')


    @app.route("/profile", methods=['POST'])
    @inlineCallbacks
    def modifyuser_post(self, request):
        login = request.getUser()
        a = request.args
        data = yield self.getcred(login)
        name = a.get('name')[0]
        password = a.get('password')[0]
        # check!
        if len(password) < 8:
            request.write('<b>Password was too short! need min. 8 characters.</b>')
        else:
            data.update({"name":name, "password":password,"timestamp":int(time.time())})
            obj = self.buckets['cred'].new(login, data)
            yield obj.store()
            print('saved modified entry to users!')
            request.write('Modified user %s. ' % (login))
        request.write('<p><a href="/profile">Return.</a>')


    # webmail routes here.
    @app.route('/')
    def index(self, request):
        return 'it works...'

    @app.route('/search', methods=['GET'])
    def search(self, request):
        out = '''
<h2>full text search</h2>
<p>
type your search term(s) here:
<form action="/search" method="POST" >
<input type="TEXT" name="terms" value="hae..." />
<input type="SUBMIT" name="SUBMIT" />
</form>
'''
        request.write(out)

    @app.route('/search', methods=['POST'])
    @inlineCallbacks
    def do_search(self, request):
        import quopri, re
        a = request.args
        login = request.getUser()
        obj = yield self.buckets['mailmeta'].get(login)
        user_emails = obj.get_data().keys()
        terms = a.get('terms')[0]
        print 'TERMS:', terms
        res = yield self.buckets['mailbody'].search(terms)
        request.write('search found this:')
        r1 = re.compile(r".*Delivered-To:\s([a-zA-Z0-9.-]+)@.*?\n.*", re.DOTALL)  # is this all?
        for doc in res['docs']:
            data = doc['value']
            m = r1.match(data)
            if m.group(1) != login:
                continue  # this msg was not for this user, skip it.
            content_trans = 'Content-Transfer-Encoding: quoted-printable'
            if content_trans in data:
                headers, _, body = data.partition(content_trans)
            else:
                headers, body = data, ''
            out = headers.decode('ascii')  # headers should always be ascii-onl
            s = quopri.decodestring(body).decode('utf-8', errors='replace')
            print type(out),type(s)
            out = out + s
            out = out.encode('utf-8')
            request.write('<pre>' + out + '</pre>')

    @app.route('/showSess')
    def showSess(self, request):
        s =  request.getSession()
        print request.getUser()
        print 'DEBUG:', s.sessionNamespaces, dir(s.sessionNamespaces)
        return 'Session id is: ' + s.uid
    @app.route('/expireSess')
    def expSess(self, request):
        request.getSession().expire()
        return 'Session expired.'

    @app.route('/inbox')
    @defer.inlineCallbacks
    def inbox(self, request):
        user = request.getUser()
        obj = yield self.buckets['mailmeta'].get(user)
        data = obj.get_data()
        print 'DEBUG:',data,type(data)
        out1 = 'Num of mails: %d' % len(data)
        out2 = 'Total bytes used: %d' % sum([data[x]['size'] for x in data])
        request.write( '<p>'.join([out1,out2]).encode('ascii'))

        # list all mail headers

        for mailid in data:
            request.write('<p>')
            obj = yield self.buckets['mailbody'].get(mailid)
            body = obj.get_data()
            #print body, type(body)
            lst = body.split('\n')
            out = []
            for line in lst:
                if line.startswith('From:') or line.startswith('To:') or line.startswith('Subject:'):
                    out.append(line)
            request.write('<br>'.join(out))


