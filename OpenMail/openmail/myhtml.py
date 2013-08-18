from pyparsing import *

ParserElement.setDefaultWhitespaceChars('\t ')

def parse(input_string):
    def prop_to_dict(tokens):
        prop_dict = {}
        for token in tokens:
            prop_dict[token.property_key] = token.property_value
        return prop_dict

    word = Word(alphas+'_')
    newline = Suppress('\n')  # ignore this as a token
    colon = Suppress(':')
    arrow = Suppress('->')
    key = word.setResultsName('property_key')  # name this
    value = Word(alphas + alphas8bit + nums + '_@.+()%').setResultsName('property_value')  # and this
    field_property = Group(key + colon + value).setResultsName('field_property')
    field_type = oneOf('CharField EmailField PasswordField SubmitField').setResultsName('field_type')
    field_name = word.setResultsName('field_name')
    field = Group(field_name + colon + field_type
                  + Optional(arrow + OneOrMore(field_property)).setParseAction(prop_to_dict)
                  + newline).setResultsName('form_field')
    form_name = word.setResultsName('form_name')
    form = form_name + newline + OneOrMore(field).setResultsName('fields')
    return form.parseString(input_string)

class HtmlElement(object):
    default_attrs = {}
    tag = "unknown tag"  # default
    def __init__(self, *args, **kw):
        self.attributes = kw
        self.attributes.update(self.default_attrs)
        self.children = args
    def __str__(self):
        "render as HTML"
        attribute_html = ' '.join(["{}='{}'".format(name, value) for name,value in self.attributes.items()])
        if not self.children:
            return "<{} {}/>".format(self.tag, attribute_html)
        else:
            children_html = "".join([str(child) for child in self.children])
            return "<{} {}>{}</{}>".format(self.tag, attribute_html, children_html, self.tag)
        
class Form(HtmlElement):
    tag = 'form'
    def __init__(self, *args, **kw):
        # limit ourselves to latin-1 charset
        HtmlElement.__init__(self, *args, **kw)
        self.attributes['accept-charset'] = 'ISO-8859-1'

class Input(HtmlElement):
    tag = 'input'

    def __init__(self, *args, **kw):
        HtmlElement.__init__(self, *args, **kw)
        self.label = self.attributes['label'] if 'label' in self.attributes else self.attributes['name']
        if 'label' in self.attributes:
            del self.attributes['label']

    def __str__(self):
        label_html = '<label>{}</label>'.format(self.label)
        return label_html + HtmlElement.__str__(self) + '<br/>\n'

class CharField(Input):
    default_attrs = {'type':'text'}

class EmailField(CharField):
    pass  # the same as CharField for now

class PasswordField(Input):
    default_attrs = {'type':'password'}

class SubmitField(Input):
    default_attrs = {'type':'submit'}
    def __str__(self):
        return HtmlElement.__str__(self) + '<br/>\n'  # override this, w/o label

def renderForm(form, *args, **kw):
    field_dict = {'CharField': CharField, 'EmailField': EmailField, 'PasswordField': PasswordField, 'SubmitField':SubmitField}
    # now, create the field classes
    fields = [field_dict[field.field_type](name=field.field_name, **field[2]) for field in form.fields]
    return Form(*fields, id=form.form_name.lower(), **kw )
