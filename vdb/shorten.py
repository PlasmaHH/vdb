#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.color
import vdb.config
import vdb.subcommands


import re
import gdb
import os
from collections.abc import Iterable

color_shorten = vdb.config.parameter("vdb-shorten-colors-templates", "#f60", gdb_type = vdb.config.PARAM_COLOUR)



class namespace:

	def __init__(self,name,parent=None):
		self.name = name
		self.parent = parent

	def __str__(self):
		ret = self.name
		if( self.parent ):
			ret = self.parent.__str__() + "::" + ret
		return ret

class type_or_function:
	def __init__(self):
		self.namespace=None
		self.name="{{placeholder for name}}"
		self.template_parameters=[]
		self.subobject=None
		self.parameters=[]
		self.shortens = {}
		self.suppress_templates = False
		self.suppress_paramters = False

	def add_tail( self, subob ):
		if( self.subobject ):
			self.subobject.add_tail(subob)
		else:
			self.subobject = subob
	
	def shorten( self, name ):
		for old,new in self.shortens.items():
			name = name.replace(old,new)
		return name

	def add_ns( self, ns ):
		if( len(ns) > 0 ):
			ns=namespace(ns)
			ns.parent = self.namespace
			self.namespace = ns

	def add_param( self, par ):
		self.parameters.append(par)

	def add_template( self, tpar ):
		if( len(tpar.name) > 0 ):
			self.template_parameters.append(tpar)

	def dump( self, level = 0 ):
		indent(level,"ns : " + str(self.namespace))
		indent(level,"name : " + self.name)
		indent(level,"template parameters[{}]".format(len(self.template_parameters)))
		for t in self.template_parameters:
			t.dump(level+1)
		indent(level,"parameters[{}]".format(len(self.parameters)))
		if( self.subobject is not None ):
			indent(level,"Subobject")
			self.subobject.dump(level+1)

	def fold_templates( self, shortlist ):
		if( isinstance(shortlist,Iterable) and not isinstance(shortlist,str) ):
			for s in shortlist:
				self.fold_templates(s)
		else:
			if( self.subobject is not None ):
				self.subobject.fold_templates(shortlist)
			if( len(self.template_parameters ) ):
				for tp in self.template_parameters:
					tp.fold_templates(shortlist)
			if( len(self.parameters) ):
				for p in self.parameters:
					p.fold_templates(shortlist)
			if( self.name == shortlist ):
				self.suppress_templates = True

	def add_shorten( self, fro, to = None ):
		if( to is None ):
			for f,t in fro.items():
				self.add_shorten(f,t)
		else:
			if( self.subobject is not None ):
				self.subobject.add_shorten(fro,to)
			if( len(self.template_parameters ) ):
				for tp in self.template_parameters:
					tp.add_shorten(fro,to)
			if( len(self.parameters) ):
				for p in self.parameters:
					p.add_shorten(fro,to)
			self.shortens[fro] = to

				

	def __str__(self):
		if( len(self.name) == 0 ):
			return ""
		ret = ""
		if( self.namespace is not None ):
			ret += str(self.namespace) + "::"
		ret += self.name
		ret = self.shorten(ret)
		if( len(self.template_parameters) ):
			if( self.suppress_templates ):
				ret += vdb.color.color("<…>",color_shorten.value)
			else:
				ret += "<"
				first=True
				for t in self.template_parameters:
					if( first ):
						first = False
					else:
						ret += ","
					ts = str(t)
					if( len(ts) == 0 ):
						print("Template parameter of length 0")
					ret += ts
				ret += ">"
		if( self.subobject is not None ):
			if( len(self.subobject.name) != 0 ):
				ret += "::" 
			ret += str(self.subobject)

		if( self.subobject is not None ):
			if( len(self.subobject.parameters) ):
				ret += "("
				first = True
				for par in self.subobject.parameters:
					if( first ):
						first = False
					else:
						ret += ","
					ret += str(par)
				ret += ")"
		return ret



def parse_fragment( frag, obj, level = 0 ):
#	indent(level,"Parsing fragment '{}'",frag[:50])
	sofar = ""

	i = -1
	while i < len(frag)-1:
#		print("len(frag) = '%s'" % len(frag) )
#		print("i = '%s'" % i )
		i += 1
#		print("i = '%s'" % i )
#		indent(level,"frag[%s] = '%s'" % (i,frag[i]) )
		s=frag[i]
		if( s == " "):
			continue
		if( s == "(" ):
			obj.name = sofar
			while True:
				ct = type_or_function()
				i += 1
				i += parse_fragment( frag[i:], ct, level+1 ) 
#				indent(level,"param {}",ct)
#				print("frag[i:] = '%s'" % frag[i:] )
#				print("frag[i+1:] = '%s'" % frag[i+1:] )
				obj.add_param(ct)
				if( frag[i] == ")" ):
					return i+1
			continue
		if( s == ")" ):
			obj.name = sofar
			return i
		if( s == ":" ):
			obj.add_ns( sofar )
			sofar = ""
			continue
		if( s == "," ):
			obj.name = sofar
			return i
		if( s == "<" ):
			obj.name = sofar
			sofar = ""
			while True:
#				indent(level,"obj = '%s'" % obj )
				ct = type_or_function()
				i += parse_fragment( frag[i+1:], ct,level+1 )
#				indent(level,"ct = '%s'" % ct )
				obj.add_template( ct )
				i+=1
#				print("i = '%s'" % i )
#				print("len(frag) = '%s'" % len(frag) )
				if( i+1 == len(frag) ):
					return i
#				indent(level,"T frag[%s] = '%s'" % (i,frag[i]) )
				if( frag[i] == "," ):
					continue
				if( frag[i] == ">" ):
					if( frag[i+1] == ":" ):
						sub = type_or_function()
						obj.subobject = sub
						obj = sub
						break
					else:
						return i
			continue
		if( s == ">" ):
			obj.name = sofar
#			print("i = '%s'" % i )
			return i
#		indent(level,"{} += {}".format(sofar,s))

		sofar += s
	if( len(sofar) > 0 ):
		obj.name =sofar
	return i




def parse_function( fun ):
#	print("fun = '%s'" % fun )
	func = type_or_function()
	rest = fun
	sub = func
	while len(rest) > 0:
		i = parse_fragment( rest , sub )
#		print("sub = '%s'" % sub )
#		print("rest = '%s'" % rest )
#		print("i = '%s'" % i )
		if( i == len(rest) ):
			break
		i += 1
		rest = rest[i:]
#		print("rest = '%s'" % rest )
#		print("i = '%s'" % i )
		if( len(rest) > 0 ):
			sub0 = type_or_function()
			sub.add_tail(sub0)
			sub = sub0
	sf = str(func)
	s0 = sf.replace(" ","")
	s1 = fun.replace(" ","")
	if( s0 != s1 ):
#		func.dump()
		print("Recreating the function signature leads a difference (%s,%s)" % (len(s0),len(s1)))
		print("fun = '%s'" % fun )
		cnt = 0
		d0 = ""
		d1 = ""
		for i in range(0,len(s0)):
			if( s0[i] != s1[i] ):
				d0 = s0[i-10:i+40]
				d1 = s1[i-10:i+40]
				break
		print("Found   :" + d0)
		print("Expected:" + d1)

#	func.dump()
	return func







def template_fold(fname,template):
	start = fname.find(template)
	if( start == -1 ):
		return fname
	start += len(template)
	prefix=fname[0:start]
#	print("start = '%s'" % start )
#	print("fname = '%s'" % fname )
#	print("prefix = '%s'" % prefix )
	level = 0
	for i in range(start,len(fname)):
		if( fname[i] == "<" ):
			level+=1
		elif( fname[i] == ">" ):
			level-=1
		if( level == 0 ):
			suffix=fname[i+1:]
			suffix=template_fold(suffix,template)
			fname = prefix + vdb.color.color("<…>",color_shorten.value) + suffix
			break
	return fname




shortens = { 
		"(anonymous namespace)": "(anon)",
		}

def add_shorten( f, t ):
    shortens[f] = t

def add_shorten_v( argv ):
    if( len(argv) != 2 ):
        print("add_shorten expects exactly 2 arguments, %s given" % len(argv) )
    else:
        f=argv[0]
        t=argv[1]
        add_shorten(f,t)
        print(f'Added shorten from "{f}" to "{t}"')

def show_shorten( args ):
    print("Configured shortens are:")
    mlen=0
    for s,t in shortens.items():
        mlen = max(mlen,len(s))

    mlen += 2
    for s,t in shortens.items():
        xs="'"+s+"'"
        print(f"{xs:<{mlen}} => '{t}'")


vdb.subcommands.add_subcommand( "add_shorten", add_shorten_v )
vdb.subcommands.add_subcommand( [ "show", "shorten" ], show_shorten )




foldables = [ 
	"feedconfig::condition_base",
	"dissected_message",
	"parser_base",
	"symbol_context",
	"intermediate_symbol",
	"buffered_write_device",
		]

def function(fname):
	feedconfig = fname.find("vwd::mdps::feedconfig")
	for old,new in shortens.items():
		fname = fname.replace(old,new)
	for fold in foldables:
		fname = template_fold(fname,fold)
	if( feedconfig != 0 ):
		fname = template_fold(fname,"boost::variant")
	if( fname.endswith(")") or fname.endswith(") const") ):
#		print("fname = '%s'" % fname )
		oppos = fname.rfind("(")
		if( oppos != -1 ):
			fname = fname[0:oppos] # + color("(...)","#ff6611")
	return fname

class ArgVal():

	def __init__( self, sym, val ):
#		print("sym = '%s'" % sym )
#		print("val = '%s'" % val )
		self.sym = sym
		self.val = val

	def symbol(self):
		return self.sym

	def value(self):
		return self.val

HOME=os.environ["HOME"]
def path(fpath):
	fpath = fpath.replace(HOME,"~")
	return fpath


# vim: tabstop=4 shiftwidth=4 expandtab ft=python
