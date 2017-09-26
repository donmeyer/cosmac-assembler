#!/usr/bin/env python3
#


import cosmacasm



cosmacasm.verbose = 0	# 2 for noisy

cosmacasm.passNumber = 2	# For pass 1, some opcodes are not assembled, so we force pass 2 to allow testing the
							# assembleChunk() function.


failCount = 0



cosmacasm.addSymbolAddress( "A_BOOP", 32 )
cosmacasm.addSymbolAddress( "A_MICE", 0x1234 )

symECat = cosmacasm.addSymbolEquate( "E_CAT", "88" )
symPC = cosmacasm.addSymbolEquate( "PC", "8" )




print( "---- obtainTokenValue() ----")

def testObtainTokenValue(tests):
	global failCount
	for test in tests:
		what, v, ebytes = cosmacasm.obtainTokenValue( 0, test[0] )
		# print( test[0], ":", what, v, ebytes )
		if what != test[1]:
			failCount += 1
			print( "Failed: Type for '%s'. Expected %s but got %s" % ( test[0], test[1], what ) )
		else:
			if what == "sym":
				if v.value != test[2]:
					failCount += 1
					print( "Failed: Address for '%s'. Expected %d but got" % ( test[0], test[2] ), v )
			else:
				if v != test[2]:
					failCount += 1
					print( "Failed: Value for '%s'. Expected %d but got %d" % ( test[0], test[2], v ) )



# negativeTokenValueTests = [
# 	( "GG", "dec", 55 ),
# 	( "PC", "sym", 8 ),
# 	( "E_CAT", "sym", 88 )
# ]
#
# testObtainTokenValue( negativeTokenValueTests )


tokenValueTests = [
	( "55", "dec", 55 ),
	( "055H", "hex", 85 ),
	( "17H", "hex", 23 ),
	( "0FFH", "hex", 255 ),
	( "055AAH", "hex", 0x55AA ),

	( "A_BOOP", "sym", 32 ),
	( "E_CAT", "sym", 88 ),

	# Invalid formats
	( "FFH", None, None ),
	( "BEEP", None, None )	
]
	
testObtainTokenValue( tokenValueTests )




print( "---- calcExpression() ----")

# ( test-string, value, address-flag, literal-flag )
calcExpressionTests = [
	# Literal
	( "55", 55, False, True ),
	( "055H", 85, False, True ),
	#
	# Address
	( "A_BOOP", 32, True, False ),
	( "A_MICE", 0x1234, True, False ),
	#
	# Equate?
	( "E_CAT", 88, False, False ),
	#
	# Partial Address
	( "A.0(A_BOOP)", 32, True, False ),
	( "A.1(A_BOOP)", 0, True, False ),
	( "A.0(A_MICE)", 0x34, True, False ),
	( "A.1(A_MICE)", 0x12, True, False ),
	#
	# Address Calculations
	( "A_BOOP+1", 33, True, False ),
	( "A_BOOP + 1", 33, True, False ),
	( "A_BOOP - 10H", 16, True, False ),
	( "A_MICE + 10H", 0x1244, True, False ),
	#
	( "A.0(A_BOOP+1)", 33, True, False ),
	( "A.1(A_BOOP+256)", 1, True, False ),
	#
	# Not yet supported
	# ( "A.1(A_BOOP) + 3", 3, True, False )
	
	# Calculations with equates
	( "E_CAT + 2", 90, False, False ),
	( "E_CAT * 2", 176, False, False ),

	# Calculations with address and equate
	( "A_BOOP+E_CAT", 120, True, False ),
	
	#
	# Invalid formats
	( "FFH", None, False, False ),
	( "BEEP", None, False, False )	
]


calcExpressionTestsAlt = [
	( "LOW(A_MICE)", 0x34, True, False ),
	( "HIGH(A_MICE)", 0x12, True, False )
]

#   BSCR-8
#   ROMVAR + 1AH
#	A.0(BEEP)


def testCalcExpression( tests ):
	global failCount
	for test in tests:
		# Returns a tuple of ( value, addrFlag, litFlag, bytes ). Will return None if a value could not be obtained.
		v, aflag, lflag, ebytes = cosmacasm.calcExpression( 0, test[0] )
		# print( v, aflag, lflag, ebytes )
		if aflag != test[2]:
			failCount += 1
			print( "Failed: Address Flag for '%s'. Expected %d but got %d" % ( test[0], test[2], aflag ) )
		else:
			if lflag != test[3]:
				failCount += 1
				print( "Failed: Literal Flag for '%s'. Expected %d but got %d" % ( test[0], test[3], lflag ) )
			else:
				if v != test[1]:
					failCount += 1
					# print( "Failed: Type for '%s'. Expected %s but got %s" % ( test[0], test[1], what ) )
					print( "Failed: Value for '%s'. Expected %d but got %d" % ( test[0], test[1], v ) )

testCalcExpression( calcExpressionTests )

cosmacasm.altSyntax = True
testCalcExpression( calcExpressionTestsAlt )
cosmacasm.altSyntax = False


print( "---- Opcode Tests (should succeed) ----")

opcodeTests = [
	( "IDLE", b"\x00" ),
	( "IRX", b"\x60" ),
	( "SEX R1", b"\xE1" ),
	( "SEX 3", b"\xE3" ),
	( "SEX PC", b"\xE8" ),
	( "SEX PC+2", b"\xEA" ),
	( "LDI 74H", b"\xF8\x74" ),
	( "LDN R2", b"\x02" )
]


for test in opcodeTests:
	tbytes = bytearray( test[1] )
	try:
		addr, abytes = cosmacasm.assembleChunk( test[0] )
	except cosmacasm.Error as err:
		print( "*** caught an exception", err.message )
		failCount += 1
	else:
		if abytes != tbytes:
			print( "Failed: opcode '%s'." % test[0] )
			print( "Expected", tbytes )
			print(  "But got", abytes ) 
			print(  "with len", len(abytes) ) 
			failCount += 1





print( "---- Opcode Tests (should fail) ----")


try:
	addr, abytes = cosmacasm.assembleChunk( "LDN R0" )
except cosmacasm.Error as err:
	# This should thrown an exception since R0 cxannot be used for LDN
	pass
else:
	print( "Failed: 'LDN R0' should have throen an exception" )
	failCount += 1


try:
	addr, abytes = cosmacasm.assembleChunk( "SEX PC+8" )
except cosmacasm.Error as err:
	# This should thrown an exception since R0 cxannot be used for LDN
	pass
else:
	print( "Failed: 'SEX PC+8' should have throen an exception" )
	failCount += 1





print( "\nFailures: %d" % failCount)


# Returns a tuple of ( sym/hex/dec, value, bytes ). Will return None if a value could not be obtained.
# a, b, c = cosmacasm.obtainTokenValue( 0, "55" )
# print( a, b, c )
#
# a, b, c = cosmacasm.obtainTokenValue( 0, "055H" )
# print( a, b, c )
#
# a, b, c = cosmacasm.obtainTokenValue( 0, "055AAH" )
# print( a, b, c )
#
# a, b, c = cosmacasm.obtainTokenValue( 0, "BEEP" )
# print( a, b, c )
