#!/usr/bin/env python

import shlex
from optparse import OptionParser

class Tokenizer:
    """Basic tokenizer built on shlex"""
    def __init__(self, stream):
        self.lexer = shlex.shlex(stream)
        # tokenize newlines too
        self.lexer.whitespace=' \t\r'
        self.curr_token = ''

    def get_token(self):
        """Get the next token"""
        self.curr_token = self.lexer.get_token()
        return self.curr_token

    def current_token(self):
        """Get the actual token"""
        return self.curr_token

    def put_token(self, tok = None):
        """Pushback a given token to later use"""
        if tok == None:
            tok = self.curr_token
        self.lexer.pushback.append(tok)

    def get_file_name(self):
        return self.lexer.instream.name

    def get_lineno(self):
        return self.lexer.lineno 

    def at_nl(self):
        """Is the next token is a newline?"""
        return self.get_token() == '\n'

    def error(self, errstr):
        print("Error:%s:%d %s" % (self.get_file_name(), self.get_lineno(), errstr))

    def at_eof(self):
        return self.curr_token == ''

class Option:
    @staticmethod 
    def parse_string(tk, s):
        """Parse a string in quotes or apostrophe"""
        if s[0] != '\'' and s[0] != '\"':
            tk.error("String must start with an apostrophe or a quotation")
            tk.put_token()
            return ''

        plen = len(s)-1
        if s[plen] != '\'' and s[plen] != '\"':
            tk.error("String must end with an apostrophe or a quotation")
            tk.put_token()
            return ''

        return s.strip("\"\'")

    @staticmethod 
    def parse_type(tk, t, sym):
        tok = tk.get_token()
        if tok[0] == '\'' or tok[0] == '\"':
            tok = Option.parse_string(tk, tok)
            sym.set_type(t, tok)
        else:
            tk.put_token()

    @staticmethod 
    def parse_select(tk, sym):
        sym.add_select(tk.get_token())

    @staticmethod 
    def parse_help(tk, sym):
        while tk.current_token() != '\n':
            tk.get_token()

    @staticmethod 
    def parse_depends_on(tk, sym):
        if tk.get_token() == 'on':
            sym.add_dependency(tk.get_token())
        else:
            tk.error("Unexpected token after 'depends'")

    @staticmethod 
    def parse_default(tk, sym):
        tok = tk.get_token()
        if tok == 'y':
            sym.make_default()
        elif tok == 'n':
            sym.make_default(False)
        else:
            tk.error("You can only use 'y' or 'n' for default")

    @staticmethod 
    def parse_prompt(tk, sym):
        prompt = tk.get_token()
        sym.set_prompt(Option.parse_string(tk, prompt))

    @staticmethod 
    def parse(tk, sym):
        tok = tk.get_token()
        if tok == 'bool' or tok == 'tristate' or tok == 'string':
            Option.parse_type(tk, tok, sym)
        elif tok == 'select':
            Option.parse_select(tk, sym)
        elif tok == 'depends':
            Option.parse_depends_on(tk, sym)
        elif tok == 'default':
            Option.parse_default(tk, sym)
        elif tok == 'prompt':
            Option.parse_prompt(tk, sym)    
        elif tok == 'help' or tok == '--help--':
            Option.parse_help(tk, sym)
        elif tok == '\n':
            return 
        else:
            tk.put_token(tok)
            return False

        # shlex ignores the newline character if a comment is
        # parsed (we can't rely on \n)
        if not tk.at_nl():
            tk.put_token()
        return True

class Symbol:
    all_symbols = {}
    def __init__(self, tk, symbol, menu):
        self.symbol = symbol
        self.options = []
        self.selects = []

        self.depends_on = []
        self.prompt = None
        self.is_selected = False
        # enabled if every dependency met
        self.is_selectable = False
        self.is_default = False
        # other configs which depends on this symbol
        self.dependants = []
        self.type = None

        # For error reporting
        self.lineno = tk.get_lineno()
        self.defined_at = tk.get_file_name()
        if menu is Menu:
            self.parent = menu # the parent menu if any
            menu.add_symbol(self)
        else:
            self.parent = None

        Symbol.all_symbols[symbol] = self
        print(" | \tconfig \'%s\' " % self.symbol)

    def name(self):
        return self.symbol

    def set_prompt(self, prompt):
        self.prompt = prompt

    def get_prompt(self):
        return self.prompt

    def add_dependency(self, dep):
        self.depends_on.append(dep)

    def add_dependant(self, dep):
        self.dependants.append(dep)

    def add_select(self, symname):
        self.selects.append(symname)

    def get_selects(self):
        return self.selects

    def get_dependencies(self):
        return self.depends_on

    def has_dependencies(self):
        return self.depends_on != []

    def make_default(self, df = True):
        self.is_default = df

    def error(self, errstr):
        print("Error:%s:%d %s" % (self.defined_at, self.lineno, errstr))

    def resolve_dependencies(self):
        """Substitute config names with the objects themselves in depends_on"""
        new_deps = []
        for dep in self.depends_on:
            if dep == self.name:
                self.error("config \'%s\' cannot depends on itself" % self.name)
            nd = Symbol.get_symbol(dep)
            nd.add_dependant(self)
            new_deps.append(nd)
        self.depends_on = new_deps

    def resolve_selects(self):
        """Substitute config names with the objects themselves in the selects"""
        new_selects = []
        for sel in self.selects:
            if sel == self.name:
                self.error("config \'%s\' cannot select itself" % self.name)
            new_selects.append(Symbol.get_symbol(sel))
        self.selects = new_selects

    def make_selectable(self, sel = True):
        self.is_selectable = sel

    def deselect(self):
        self.is_selected = False

    def select(self):
        """Select a config and it's selects, if every dependency is staisfied"""
        for dep in self.depends_on:
            if not dep.is_selected:
                return
            
        for dep in self.dependants:
            dep.make_selectable()

        for dep in self.depends_on:
            if not dep.is_selected:
                return

        self.is_selected = True
        for sel in self.selects:
            if sel != None:
                sel.select()

    def set_type(self, t, prompt = None):
        self.type = t
        self.prompt = prompt

    def str(self):
        return "%s: \'%s\'" % (self.name, self.prompt)

    @staticmethod 
    def get_symbol(sym_name):
        try:
            return Symbol.all_symbols[sym_name]
        except KeyError:
            print("Error: Config \'%s\' cannot found" % sym_name)

    @staticmethod 
    def get_all_symbols():
        return Symbol.all_symbols

    @staticmethod 
    def parse(tk, parent):
        sym = Symbol(tk, tk.get_token(), parent)
        if tk.get_token() != '\n':
            tk.error("Unexpected token after config")
            tk.put_back()

        while tk.current_token() != 'config' and tk.current_token() != 'endmenu' and tk.current_token() != '':
            if not Option.parse(tk, sym):
                return sym
        return sym

class Menu:
    all_menus = []
    main_menu_name = ""
    def __init__(self, parent): 
        self.symbols = []
        self.prompt = ''
        if parent is Menu:
            self.parent = parent
        else:
            self.parent = None
        Menu.all_menus.append(self)

    def name(self):
        return self.name

    def set_prompt(self, prompt):
        self.prompt = prompt
        print(" + menu \"%s\"" % self.prompt)

    def get_symbols(self):
        return self.symbols

    def add_symbol(self, symbol):
        self.symbols.append(symbol)

    def has_symbol(self, sym_name):
        for sym in self.symbols:
            if sym.name() == sym_name:
                return true

    @staticmethod 
    def get_menus():
        return Menu.all_menus

    @staticmethod 
    def parse(tk, parent):
        m = Menu(parent)
        Option.parse_prompt(tk, m)
        if not tk.at_nl():
                tk.error("Unexpected token %s for a menu (should be a newline)" % tk.current_token())
                tk.put_token()

        while tk.current_token() != 'endmenu':
            parse(tk, m)
        return m
        
def parse(tk, parent):
    tok = tk.get_token()
    if tok == 'menu':
        Menu.parse(tk, parent)
    elif tok == 'source':
        fname = Option.parse_string(tk, tk.get_token())
        tk.get_token() 
        parse_file(fname, parent)
    elif tok == 'config':
        Symbol.parse(tk, parent)
    elif tok == 'mainmenu':
        tk.error("Unexpected mainmenu")
        tk.get_token()
        tk.get_token()
    elif tok == 'endmenu':
        return
    elif tok == '\n' or tok == '':
        return
    else:
        tk.error("Unknown token \'%s\'" % tok)

def parse_file(fname, parent):
    tk = Tokenizer(file(fname, 'rt'))
    if tk.get_token() == 'mainmenu':
        Menu.main_menu_name = Option.parse_string(tk, tk.get_token())
        if not tk.at_nl():
                tk.error("Unexpected token %s for a menu (should be a newline)" % tk.current_token())
                tk.put_token()
    else:
         tk.put_token()

    while tk.current_token() != '':
        parse(tk, parent)

def fix_dependencies_for(sym, deplist):
    for dep in deplist:
        if not dep.is_selected:
            dep.deselect()
            
def fix_dependencies():
    """If a dependency is not selected, deselect the dependants"""
    for name,sym in Symbol.get_all_symbols().iteritems():
        deps = sym.get_dependencies()
        if deps != []:
            fix_dependencies_for(sym, deps)            

def write_selected_to(fname):
    """Write all CONFIG_*s to 'fname' which selected"""
    f = file(fname, "wt")
    f.write("# Configuration \'%s\'\n\n" % Menu.main_menu_name)
    for name in Symbol.get_all_symbols():
        sym = Symbol.get_symbol(name)
        if sym.is_selected:
            sym.select()
            f.write("CONFIG_%s=y\n" % name)
    f.close()

def resolve_symbols():
    """Substitute all config names with the appropriate object"""
    for name,sym in Symbol.get_all_symbols().iteritems():
        sym.resolve_dependencies()
        sym.resolve_selects()

def select_configs(clist):
    """Select all configs from 'clist'"""
    for cname in clist:
        Symbol.get_symbol(cname).select()

def select_from(fname):
    st = Tokenizer(fname)
    sel = []
    while st.get_token() != '':
        st.append(st.current_token())
    select_configs(sel)

def select_defaults():
    for name,sym in Symbol.get_all_symbols().iteritems():
        if sym.is_default:
            sym.select()

def read_selects(fname):
    tk = Tokenizer(file(fname, 'rt'))
    sels = []
    while tk.get_token() != '':
        tok = tk.current_token()
        if tok == '\n' or tok == ',' or tok == ';':
            continue
        else:
            sels.append(tk.current_token().strip())
    return sels

### main()
opts = OptionParser("mini_kconfig.py [options] Kconfig")
opts.add_option("-d", "--no-defaults", dest="no_defaults", default=False, action="store_true",
                  help="don't include the default config symbols")
opts.add_option("-o", "--output",
                  dest="output", default=".config", help="The output file")
opts.add_option("-s", "--select",
                  dest="select", default="", help="A comma separated list of symbols to select")
opts.add_option("-S", "--select-from",
                  dest="select_from", default="", help="File enumerating the config symbols to select")
(options, args) = opts.parse_args()

if len(args) != 1:
    kfile = "Kconfig"
else:
    kfile = args[0]

parse_file(kfile, None)
resolve_symbols()
fix_dependencies()

if not options.no_defaults:
    select_defaults()

if options.select != "":
    select_configs(options.select.split(','))

if options.select_from != "":
    select_configs(read_selects(options.select_from))
write_selected_to(options.output)
