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
# On pass 1 we usually don't care about the actual values of symbols, or even if they exist yet.
# There are two exceptions to this rule:
#  1) Declared constants ("DC"), where
#  2) Origin statements
#
# For declared constants ("DC"), we assume any symbol is an address. ** true???


import os, sys, csv, datetime, time
import codecs
import optparse
import re
import StringIO
import string



listingDest = None

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

	if options.verbose > 1:
		print( "=========================== Resolve Symbols ==============================")
	elif options.verbose > 0:
		print "Resolve symbols..."
		
	lastFailCount = None
	while 1:
		logDebug( "Symbols resolution pass" )
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
						reportError( "*** Line: %d  unable to resolve symbol '%s', expression is '%s'" % ( sym.lineNumber, key, sym.body ) )
				sys.exit( -1 )
			
		lastFailCount = failCount
		
	
		

def dumpSymbols():
	global symbols, listingDest
	print>>listingDest, "\n\n------------------- Symbols by Name ----------------------"
	keys = symbols.keys()
	keys.sort()
	for key in keys:
		print>>listingDest, "%16s : %s" % ( key, symbols[key] )
	
	

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
	
	
	
def parseRegister( arg ):
	m = re.match( r'^R([0-9A-F])', arg )
	if m:
		return int(m.group(1),16)
	else:
		bailout( "Line: %d  Invalid register '%s'" % (lineNumber, arg) )		
	

	
def assembleRegOp( opBase, arg, bytes ):
	r = parseRegister( arg )
	bytes.append( opBase + r )


# Parses a value or an address. Address must use the A.0() or A.1() formats
def assembleImmediate( opBase, arg, bytes ):
	# TODO: parse immaeidta
	bytes.append( opBase  )


# Takes an address argument and emits the LSB
# If the MSB differs from the immediate args address MSB, declare a branch range error
def assembleShortBranch( opBase, arg, bytes ):
	# TODO: parse immaeidta
	bytes.append( opBase  )


# Takes an address argument and emits the MSB and LSB
def assembleLongBranch( opBase, arg, bytes ):
	# TODO: parse immaeidta
	bytes.append( opBase  )


# Parses an integer value 1-7
def assembleOutput( opBase, arg, bytes ):
	# TODO: parse immaeidta
	bytes.append( opBase  )
	
	
# Parses an integer value 1-7
def assembleInput( opBase, arg, bytes ):
	# TODO: parse immaeidta
	bytes.append( opBase  )
	
	
	
#  mnemonic : [opcode], [func]
#  opcode may be a base opcode used by the func (e.g. DEC)
#  if no func, opcode used as-is
opTable = {	"LDN" :   ( 0x00, assembleRegOp ),
			
			"INC" :   ( 0x10, assembleRegOp ),
			"DEC" :   ( 0x20, assembleRegOp ),
			
			"BR" :    ( 0x30, assembleShortBranch ),
			"BQ" :    ( 0x31, assembleShortBranch ),
			"BZ" :    ( 0x32, assembleShortBranch ),
			"BDF" :   ( 0x33, assembleShortBranch ),
			"BPZ" :   ( 0x33, assembleShortBranch ),
			"BGE" :   ( 0x33, assembleShortBranch ),
			"B1" :    ( 0x34, assembleShortBranch ),
			"B2" :    ( 0x35, assembleShortBranch ),
			"B3" :    ( 0x36, assembleShortBranch ),
			"B4" :    ( 0x37, assembleShortBranch ),
			"NBR" :   ( 0x38, None ),
			"SKP" :   ( 0x38, None ),
			"BNQ" :   ( 0x39, assembleShortBranch ),
			"BNZ" :   ( 0x3A, assembleShortBranch ),
			"BNF" :   ( 0x3B, assembleShortBranch ),
			"BM" :    ( 0x3B, assembleShortBranch ),
			"BL" :    ( 0x3B, assembleShortBranch ),
			"BN1" :   ( 0x3C, assembleShortBranch ),
			"BN2" :   ( 0x3D, assembleShortBranch ),
			"BN3" :   ( 0x3E, assembleShortBranch ),
			"BN4" :   ( 0x3F, assembleShortBranch ),
			
			"LDA" :   ( 0x40, assembleRegOp ),
			
			"STR" :   ( 0x50, assembleRegOp ),

			"IRX" :   ( 0x60, None ),

			"OUT" :   ( 0x60, assembleOutput ),		# 61 - 67
													# 68 Reserved
			"IN" :    ( 0x68, assembleOutput ),		# 69 - 6F

			"RET" :   ( 0x70, None ),
			"DIS" :   ( 0x71, None ),
			"LDXA" :  ( 0x72, None ),
			"STXD" :  ( 0x73, None ),
			"ADC" :   ( 0x74, None ),
			"SDB" :   ( 0x75, None ),
			"SHRC" :  ( 0x76, None ),
			"RSHR" :  ( 0x76, None ),
			"SMB" :   ( 0x77, None ),
			"MARK" :  ( 0x79, None ),
			"REQ" :   ( 0x7A, None ),
			"SEQ" :   ( 0x7B, None ),
			"SDBI" :  ( 0x7D, assembleImmediate ),
			"SHLC" :  ( 0x7E, None ),
			"RSHL" :  ( 0x7E, None ),
			"SMBI" :  ( 0x7F, assembleImmediate ),
			
			"GLO" :   ( 0x80, assembleRegOp ),
			"GHI" :   ( 0x90, assembleRegOp ),
			
			"PLO" :   ( 0xA0, assembleRegOp ),
			"PHI" :   ( 0xB0, assembleRegOp ),

			"LBR" :   ( 0xC0, assembleLongBranch ),
			"LBQ" :   ( 0xC1, assembleLongBranch ),
			"LBZ" :   ( 0xC2, assembleLongBranch ),
			"LBDF" :  ( 0xC3, assembleLongBranch ),
			"NOP" :   ( 0xC4, None ),
			"LSNQ" :  ( 0xC5, None ),
			"LSNZ" :  ( 0xC6, None ),
			"LSNF" :  ( 0xC7, None ),
			"LSKP" :  ( 0xC8, None ),
			"NLBR" :  ( 0xC8, None ),
			"LBNQ" :  ( 0xC9, assembleLongBranch ),
			"LBNZ" :  ( 0xCA, assembleLongBranch ),
			"LBNF" :  ( 0xCB, assembleLongBranch ),
			"LSIE" :  ( 0xCC, None ),
			"LSQ" :   ( 0xCD, None ),
			"LSZ" :   ( 0xCE, None ),
			"LSDF" :  ( 0xCF, None ),

			"SEP" :   ( 0xD0, assembleRegOp ),
			
			"SEX" :   ( 0xE0, assembleRegOp ),

			"LDX" :   ( 0xF0, None ),
			"OR" :    ( 0xF1, None ),
			"AND" :   ( 0xF2, None ),
			"XOR" :   ( 0xF3, None ),
			"ADD" :   ( 0xF4, None ),
			"SD" :    ( 0xF5, None ),
			"SHR" :   ( 0xF6, None ),
			"LDI" :   ( 0xF8, assembleImmediate ),
			"ORI" :   ( 0xF9, assembleImmediate ),
			"ANI" :   ( 0xFA, assembleImmediate ),
			"XRI" :   ( 0xFB, assembleImmediate ),
			"ADI" :   ( 0xFC, assembleImmediate ),
			"SDI" :   ( 0xFD, assembleImmediate ),
			"SHL" :   ( 0xFE, None ),
			"SMI" :   ( 0xFF, assembleImmediate )
}


# Returns a tuple of starting address and a byte array of the machine code.
def assembleChunk( chunk ):
	global address
	
	# Get the opcode and optional argument
	m = re.match( r'^(\w+)\s*(.*)', chunk )
	if m == None:
		bailout( "Line: %d  Invalid line '%s'" % (lineNumber, chunk) )		

	bytes = bytearray()
	startAddr = address
		
	opcode = m.group(1)
	mnemonic = m.group(1)
	arg = m.group(2)
	logDebug( "Chunk   opcode '%s'  arg '%s'" % ( opcode, arg ) )

	if opcode == "DC":
		return assembleDC( arg )
	else:
		if opTable.has_key( mnemonic ):
			opbase, func = opTable[mnemonic]
			if func:
				func( opbase, arg, bytes )
			elif opbase:
				bytes.append( opbase )	
		else:
			bailout( "Line: %d  Invalid mnemonic '%s'" % ( lineNumber, chunk ) )
				
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
				emitListing( "%04X %-14s %04d  %s" % ( startAddr, hexStr, lineNumber, line ) )
				hexStr = ""
				overflow = True
			else:
				emitListing( "%04X %-14s" % ( startAddr, hexStr ) )
				hexStr = ""
	if hexStr != "":
		hexStr += ';'
		if overflow == False:
			emitListing( "%04X %-14s %04d  %s" % ( startAddr, hexStr, lineNumber, line ) )
		else:
			emitListing( "%04X %-14s" % ( startAddr, hexStr ) )
				
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
		emitListing( "%04X ;              %04d   %s" % (address, lineNumber, line) )



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
	
	if passNumber == 2:
		emitListing( "%04X ;              %04d   %s" % (address, lineNumber, line) )
	address = v
	
	
	
def processNoCode( line, addr ):
	global lineNumber
	if passNumber == 2:
		emitListing( "%04X ;              %04d  %s" % (addr, lineNumber, line) )
	
	
	
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

	if options.verbose > 1:
		print( "=========================== First Pass ==============================")
	elif options.verbose > 0:
		print "First Pass..."

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
	
	if options.verbose > 1:
		print( "=========================== Second Pass ==============================")
	elif options.verbose > 0:
		print "Second Pass..."
	
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
		dumpSymbols()
	secondPass( lines )



#----------------------------------------------------------------
#
#----------------------------------------------------------------

def process( filename ):
	global listDest, hexDest
	
	src = open( filename, 'r' )

	assembleFile( src )

	src.close()
		
	
	
def emitListing( text ):
	global listingDest
	
	if listingDest:
		print>>listingDest, text



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
	global options, listingDest, hexDest

	usage = """"%prog [options] <file>
	File is assembly source."""

	parser = optparse.OptionParser(usage=usage)
	
	parser.add_option( "-s", "--size",
						action="store", type="int", dest="size", default=None,
						help="Maximum size of output. Error if this size is exceeded. (optional)" )
	
	parser.add_option( "-d", "--display",
						action="store_true", dest="display", default=False,
						help="Display output on terminal. No files are produced." )
	
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

	rootname, ext = os.path.splitext( filename )
	
	if options.display == True:
		listingDest = sys.stdout
		hexDest = sys.stdout
	else:
		listingFilename = rootname + ".lst"
		listingDest = open( listingFilename, 'w' )
		hexFilename = rootname + ".hex"
		hexDest = open( hexFilename, 'w' )

	process( filename )
	
	dumpSymbols()

	if listingDest:
		listingDest.close()
	
	if hexDest:
		hexDest.close()



if __name__ == '__main__':
	sys.exit( main(sys.argv) or 0 )

