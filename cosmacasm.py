#!/usr/bin/env python
#
# 1802 Assembler
#
#
#
# ------------------------------------------
# Assemble 1802 source
#
# Produce hex file
# Produce listing
#
# ------------------------------------------
#


import os, sys, csv, datetime, time
import codecs
import optparse
import re
import StringIO
import string



listDest = None

hexDest = None

address = 0

passNumber = 1
lineNumber = 0

symbols = {}

BYTES_PER_LINE = 6



#----------------------------------------------------------------
# File read/write
#----------------------------------------------------------------





#----------------------------------------------------------------
#
#----------------------------------------------------------------


class Symbol:
	"""
	name --
	"""
	def __init__( self, name, type ):
		global lineNumber
		self.lineNumber = lineNumber
		self.name = name
		self.type = type
		self.value = None
		self.body = None
		self.expHadAddr = False

	def __repr__(self):
		if self.value == None:
			v = "*UNRESOLVED*"
		else:
			if self.type == "addr":
				v = "0x%04X" % self.value
			elif self.type == "equ":
				v = "%d" % self.value
			else:
				v = value
		return "{ %s  %d %s  %d  %s  %s }" % \
			( self.name, self.lineNumber, self.type, self.isAddr(), v, self.body )
				
	def isAddr( self ):
		if self.type == "addr" or self.expHadAddr == True:
			return True
		return False

	# Returns true if symbol was resolved
	def resolve( self ):
		if self.value == None:
			if self.body == None:
				bailout( "Trying to resolve symbol '%s', but no body" % self.name )
			what, self.value, ebytes = calcExpression( self.lineNumber, self.body, symRequired=False )
			if self.value == None:
				return False
			if what == "sym":
				self.expHadAddr = True
		return True
		

#
# Value can be a number, or a string. If a string, it represents a symbol or equation that
# will need to be resolved after the first pass completes.
#
def addSymbol( sym ):
	global symbols
	symbols[sym.name] = sym


#
# An address
#
# FOO
#      ..code...
#
def addSymbolAddress( name, value ):
	sym = Symbol( name, "addr" )
	sym.value = value
	addSymbol( sym )
	
	
	
#
# Add and equate
#
# We just store the body in this call, it will be resolved after the first pass completes.
#
def addSymbolEquate( name, body ):
	sym = Symbol( name, "equ" )
	sym.body = body
	addSymbol( sym )



#
# Resolve all of the symbols in the symbol table
#
def resolveSymbols():
	global symbols
	lastFailCount = None
	while 1:
		logDebug( "symbols resolution pass" )
		failCount = 0
		for key in symbols:
			sym = symbols[key]
			success = sym.resolve()
			if success == False:
				failCount += 1
				
		if failCount == 0:
			break
			
		if lastFailCount != None:
			if failCount >= lastFailCount:
				# This iteration through the table didn't improve. Do an error logging pass.
				for key in symbols:
					sym = symbols[key]
					if sym.value == None:
						print( "*** Line: %d  unable to resolve symbol '%s', expression is '%s'" % ( sym.lineNumber, key, sym.body ) )
				sys.exit( -1 )
			
		lastFailCount = failCount
		
	
		

def dumpSymbols( dest ):
	global symbols
	keys = symbols.keys()
	keys.sort()
	for key in keys:
		print( "%16s : %s" % ( key, symbols[key] ) )
	
	

#
# Obtain the value for a single token.
#
# Returns a tuple of ( sym/hex/dec, value, bytes ). Will return None if a value could not be obtained.
# 
# Examples:
#   7EH
#   99
#   RATS
#   12AA55FFH
#   0AA12AA55FFH
#
def obtainTokenValue( lineNumber, token ):
	global symbols

	# addrFlag = False
	
	m = re.match( r'([0-9][0-9a-fA-F]*)H$', token )
	if m:
		# Hex value
		s = m.group(1)
		logDebug( "Obtained hex value for '%s'" % s )
		
		# Convert to a sequence of bytes. (the DC directive needs this behavior)
		bytes = bytearray()
		ss = s
		if len(s) & 1:
			# Odd means leading zero
			if s[0] != '0':
				bailout( "Line: %d  Malformed hex value '%s'" % ( lineNumber, token ) )
			ss = s[1:]

		while len(ss) > 0:
			d = ss[:2]
			bytes.append( int(d,16) )
			ss = ss[2:]
		
		if len(s) <= 5:
			# An 8-bit or 16-bit value, also convert it to an integer
			return ( "hex", int(s,16), bytes )
		else:
			return ( "hex", None, bytes )
	
	m = re.match( r'([0-9]+)$', token )
	if m:
		# Decimal value
		s = m.group(1)
		logDebug( "Obtained dec value for '%s'" % s )
		return ( "dec", int(s,10), None )
	
	# Symbol?
	if symbols.has_key( token ):
		logDebug( "Obtained symbol value for token '%s'" % token )
		sym = symbols[token]
		# Even though I put the mechanisms in place to track an address 'type' through the system,
		# I think we treat any symbol as an address in reality.
		# return ( sym.value, sym.isAddr() )
		v = sym.value
		# if v == None and passNumber == 1:
		# 	return( "sym", 0, None )
		
		return ( "sym", v, None )

	# if passNumber == 1:
	# 	return( "sym", 0, None )

	return ( None, None, None )


#
# Parses a constant, symbol, or equation and returns the numeric value.
#
# Returns a tuple of ( sym/hex/dec, value, bytes ). Will return None if a value could not be obtained.
#
# If an address symbol is used, returns a flag indicating that, so an appropriate size can be used
# as neccessary.
#
# Examples:
#   9
#   0FBH
#   14H
#   0FC00H
#   MICE
#   BSCR-8
#   ROMVAR + 1AH
#
def calcExpression( lineNumber, body, symRequired=False ):
	value = None
	ebytes = None
	symFlag = False
	op = "new"
	
	while True:
		m = re.match( r'\W*(\w+)', body )
		if m:
			s = m.group(1)
			what, v, ebytes = obtainTokenValue( lineNumber, s )

			if what == None:
				logDebug( "calc expression operand '%s' had no value" % s )
				if symRequired == True:
					bailout( "Line: %d  Expression operand '%s' is undefined." % ( lineNumber, s ) )
					return ( None, None, None )		# Could not obtain a value
				else:
					what = "sym"
					v = 0

			if what == "sym" and v == None:
				logDebug( "calc expression sym operand had no value" )
				if symRequired == True:
					return ( what, None, None )		# Could not obtain a value
				else:
					logDebug( "but that's ok" )
					v = 0

			logDebug( "calc expression operand type=%s, operator is %s" % ( what, op ) )

			if what == "sym":
				symFlag = True	# based on a symbol, even if there is some math
				
			if op == "new":
				value = v
			elif op == "+":
				value += v
			elif op == "-":
				value -= v
			elif op == "*":
				value *= v
			elif op == "/":
				value /= v
			else:
				bailout( "Line: %d  Invalid equation op '%s'" % ( lineNumber, op ) )
			if value:
				logDebug( "Bingo '%s' %d %d = %d" % (s, m.start(), m.end(), value) )
			else:
				logDebug( "Bingo '%s' %d %d = %s" % (s, m.start(), m.end(), bytes) )
			body = body[m.end():]
			op = "idle"
			m = re.match( r'\W*([\-\+\*\/])', body )
			if m:
				# Found a valid math operator
				if ebytes:
					bailout( "Line: %d   Cannot do math on a hex sequence" % ( lineNumber ) )
				s = m.group(1)
				op = s
				logDebug( "Bango '%s' %d %d" % (s, m.start(), m.end()) )
				body = body[m.end():]
		else:
			break
			
	if op != "idle":
		bailout( "Line: %d   Missing argument after '%s' operator" % ( lineNumber, op ) )
		
	# what = "dec"	# sure, why not
	if symFlag:
		what = "sym"
	return ( what, value, ebytes )
	
	

#----------------------------------------------------------------
#
#----------------------------------------------------------------


#
# If a symbol is involved, return two bytes
# If not, return bytes that the values represent.
#
# I think we count the hex digits to determine how many bytes to generate...
#
# Examples:
#   DC RATS
#   DC NOOP-7
#   DC 085H, 'LIMI', 0D4H
#   DC 8
#
def assembleDC( body ):
	global address, lineNumber

	logDebug( "Assemble DC '%s'" % body )

	startAddr = address

	bytes = bytearray()
	
	# Break up into chunks
	chunks = body.split( ',' )
	for chunk in chunks:
		chunk = chunk.strip()
		m = re.match( r"'(\w+)'", chunk )
		if m:
			s = m.group(1)
			chars = list(s)
			for c in chars:
				bytes.append( c )
		else:
			if passNumber == 1:
				symRequired = False
			else:
				symRequired = True
			what, v, ebytes = calcExpression( lineNumber, chunk, symRequired=symRequired )
			# print( what, v, ebytes )
			if what == "sym":
				# if len(bytes) != 2:
				# 	bailout( "Internal error 7" )
				# bytes.extend( ebytes )
				high = v>>8 & 0xFF
				low = v & 0xFF
				bytes.append( high )
				bytes.append( low )
			else:
				if ebytes:
					# Sequence of bytes
					bytes.extend( ebytes )
				else:
					if v > 0xFF:
						bailout( "Value too high error, line %d, chunk '%s'" % ( lineNumber, chunk ) )
					bytes.append( v )

	address += len(bytes)
	return ( startAddr, bytes )
	
	
	
# Returns a tuple of starting address and a byte array of the machine code.
def assembleChunk( chunk ):
	if chunk[:3] == "DC ":
		return assembleDC( chunk[3:] )
	
	global address
	startAddr = address
	bytes = bytearray()
	bytes.append( 0x55 )
	bytes.append( 0xAA )
	address += len(bytes)
	return ( startAddr, bytes )



#----------------------------------------------------------------
#
#----------------------------------------------------------------

#
#
# This will also deal with breaking the hex bytes flow to the next line if the width is too great.
#
def emitCode( line, startAddr, bytes ):
	global lineNumber
	# TODO: implement line break feature
	hexStr = ""
	overflow = False
	for byte in bytes:
		pair = "%02X" % byte
		hexStr += pair
		if len(hexStr) >= (BYTES_PER_LINE * 2):
			hexStr += ';'
			if overflow == False:
				print( "%04X %-14s %04d  %s" % ( startAddr, hexStr, lineNumber, line ) )
				hexStr = ""
				overflow = True
			else:
				print( "%04X %-14s" % ( startAddr, hexStr ) )
				hexStr = ""
	if hexStr != "":
		hexStr += ';'
		if overflow == False:
			print( "%04X %-14s %04d  %s" % ( startAddr, hexStr, lineNumber, line ) )
		else:
			print( "%04X %-14s" % ( startAddr, hexStr ) )
				
	# print( "Code 0x%04X  %s --- %s" % ( startAddr, hexStr, line ) )
	


def processEquate( line, label, body ):
	global address, lineNumber
	
	# Strip comments. Comments begin with two periods.
	m = re.match( r'(.*?)\.\..*', body )
	if m:
		# print( "comment match" )
		body = m.group(1)
		body = body.rstrip()
	
	if passNumber == 1:
		addSymbolEquate( label, body )
	elif passNumber == 2:
		print( "%04X ;              %04d   %s" % (address, lineNumber, line) )



def processOrigin( line, body ):
	global address, lineNumber
	
	# Strip comments. Comments begin with two periods.
	m = re.match( r'(.*?)\.\..*', body )
	if m:
		# print( "comment match" )
		body = m.group(1)
		body = body.rstrip()
	
	
	what, v, ebytes = calcExpression( lineNumber, body, symRequired=True )
	if v == None:
		bailout( "LINE: %d  Unable to resolve origin address" % lineNumber )
	
	print( "%04X ;              %04d   %s" % (address, lineNumber, line) )
	address = v
	
	
	
def processNoCode( line, addr ):
	global lineNumber
	if passNumber == 2:
		print( "%04X ;              %04d  %s" % (addr, lineNumber, line) )
	
	
	
#----------------------------------------------------------------
#
#----------------------------------------------------------------


#
# Process a line of source
#
#
def processLine( line ):
	line = line.rstrip()	# remove trailing whitespace

	logDebug( "------- Line '%s'" % line )
	
	# Equate?
	m = re.match( r'^(\w+)\s+EQU\s+(.*)', line )
	if m:
		# Line is an equate
		label = m.group(1)
		body = m.group(2)
		logDebug( "Equate: '%s'   value chunk '%s'" % ( label, body ) )
		processEquate( line, label, body )
		return
		

	# Org?
	m = re.match( r'^\s+ORG\s+(.*)', line )
	if m:
		# Line is an origin directive
		body = m.group(1)
		logDebug( "Origin: '%s'" % ( body ) )
		processOrigin( line, body )
		return
		

	# Label?
	m = re.match( r'^(\w+)\s*(.*)', line )
	if m:
		# Line has a label
		label = m.group(1)
		body = m.group(2)
		logDebug( "Label: '%s'   remainder '%s'" % ( label, body ) )
		if passNumber == 1:
			# Add it to the symbol table!
			addSymbolAddress( label, address )
	else:
		body = line.lstrip()
		
	# Strip comments. Comments begin with two periods.
	m = re.match( r'(.*?)\.\..*', body )
	if m:
		# print( "comment match" )
		body = m.group(1)
		body = body.rstrip()
	
	if body == "":
		processNoCode( line, address )
		return
		
		
	logDebug( "Body '%s'" % body )
	
	# Split up sentences based on semicolons, assemble each sentance, and then concatenate all of
	# the produced machine code bytes to represent the result of the line.
	startAddr = None
	lineBytes = bytearray()
	chunks = body.split( ";" )
	for chunk in chunks:
		chunk = chunk.strip()
		logDebug( "Chunk: '%s'" % chunk )
		addr, bytes = assembleChunk( chunk )
		if startAddr == None:
			startAddr = addr
		lineBytes.extend( bytes )
		
	if passNumber == 2:
		emitCode( line, startAddr, lineBytes )
		
		# print( "Addr: 0x%04X" % addr )
		# print( "Bytes", bytes[0], bytes[1] )

	# m = re.match( r'.*?(\d+)\s*(\d+)/(\d+).*', line )
	# if m:
	# 	print "+++              Match '%s'  '%s'  '%s' for %s" % ( m.group(1), m.group(2), m.group(3), line )
	
	# m = re.findall( r'([a-fA-F0-9][a-fA-F0-9])', line )
	# for num in m:
	# 	b = string.atoi( num, 16 )


#----------------------------------------------------------------
#
#----------------------------------------------------------------


#
# First pass - create the symbol table
#
def firstPass( lines ):
	global passNumber, lineNumber
	logDebug( "=========================== First Pass ==============================")
	passNumber = 1
	lineNumber = 0
	for line in lines:
		lineNumber += 1
		processLine( line )

	

#
# Second pass - actual assembly and output.
#
# In this pass, we do the actual assembly since we now have the complete symbol table that was
# created in the first pass.
#
def secondPass( lines ):
	global passNumber, lineNumber, address
	logDebug( "=========================== Second Pass ==============================")
	passNumber = 2
	lineNumber = 0
	address = 0
	for line in lines:
		lineNumber += 1
		processLine( line )
	
	


def assembleFile( src ):
	lines = src.readlines()
	firstPass( lines )
	resolveSymbols()
	if options.verbose > 1:
		dumpSymbols( None )
	secondPass( lines )



#----------------------------------------------------------------
#
#----------------------------------------------------------------

def process( filename ):
	global listDest, hexDest
	
	src = open( filename, 'r' )

	listDest = open( "foo.lst", 'w' )

	hexDest = open( "foo.hex", 'w' )

	assembleFile( src )

	src.close()
	
	listDest.close()
	
	hexDest.close()
	
	

#----------------------------------------------------------------
#
#----------------------------------------------------------------


def logVerbose( msg ):
	if options.verbose > 0:
		print( msg )



def logDebug( msg ):
	if options.verbose > 1:
		print( msg )


def bailout( msg ):
	print( "*** %s" % msg )
	sys.exit( -1 )
	


def main( argv ):
	global options

	usage = """"%prog [options] <file>
	File is assembly source."""

	parser = optparse.OptionParser(usage=usage)
	
	parser.add_option( "-s", "--size",
						action="store", type="int", dest="size", default=None,
						help="Maximum size of output. Error if this size is exceeded. (optional)" )
	
	parser.add_option( "-o", "--output",
						action="store", type="string", dest="output", default=None,
						help="Output filename. (optional)" )
	
	parser.add_option( "-l", "--list",
						action="store_true", dest="list", default=False,
						help="Generate listing" )
	
	parser.add_option( "-n", "--noaction",
						action="store_true", dest="noaction", default=False,
						help="Simulate the action" )
	
	parser.add_option( "-q", "--quiet",
						action="store_const", const=0, dest="verbose",
						help="quiet" )
	
	parser.add_option( "-v", "--verbose",
						action="store_const", const=1, dest="verbose", default=1,
						help="verbose [default]" )
	
	parser.add_option( "--noisy",
						action="store_const", const=2, dest="verbose",
						help="noisy" )
	
	(options, args) = parser.parse_args(argv)
	
	logDebug( options )
	logDebug( args )

	# Get the filename
	if len(args) > 1:
		filename = args[1]
	else:
		print "No file name given."
		print main.__doc__
		sys.exit(1)

	process( filename )
	
	dumpSymbols( None )



if __name__ == '__main__':
	sys.exit( main(sys.argv) or 0 )

