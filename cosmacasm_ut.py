#!/usr/bin/env python
#


import cosmacasm


failCount = 0



cosmacasm.addSymbolAddress( "A_BOOP", 32 )
cosmacasm.addSymbolAddress( "A_MICE", 0x1234 )

sym = cosmacasm.addSymbolEquate( "E_CAT", "88" )
sym.resolve()



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



print( "---- obtainTokenValue() ----")

for test in tokenValueTests:
	what, v, ebytes = cosmacasm.obtainTokenValue( 0, test[0] )
	# print( what, v, ebytes )
	if what != test[1]:
		failCount += 1
		print( "Failed: Type for '%s'. Expected %s but got %s" % ( test[0], test[1], what ) )
	else:
		if what == "sym":
			if v.value != test[2]:
				failCount += 1
				print( "Failed: Address for '%s'. Expected %d but got %d" % ( test[0], test[2], v ) )
		else:
			if v != test[2]:
				failCount += 1
				print( "Failed: Value for '%s'. Expected %d but got %d" % ( test[0], test[2], v ) )

	
	
	

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
	# ( "A.0(A_BOOP)", 32, True, False ),
	# ( "A.1(A_BOOP)", 0, True, False ),
	# ( "A.0(A_MICE)", 0x34, True, False ),
	# ( "A.1(A_MICE)", 0x12, True, False ),
	#
	# Address Calculations
	( "A_BOOP+1", 33, True, False ),
	( "A_BOOP + 1", 33, True, False ),
	( "A_BOOP - 10H", 16, True, False ),
	( "A_MICE + 10H", 0x1244, True, False ),
	
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

#   BSCR-8
#   ROMVAR + 1AH
#	A.0(BEEP)


for test in calcExpressionTests:
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