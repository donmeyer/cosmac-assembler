#!/usr/bin/env python3

# Parser
#
# This class is designed to support my Cosmac 1802 Assembler
#

import sys



class ParseError(Exception): pass


class NoClosingQuoteError(ParseError): pass

class MissingOpenParenError(ParseError): pass
class NoClosingParenError(ParseError): pass
class EmptyParenError(ParseError): pass




# Break a line of text into an array of text delimited by whitespace, operators, etc.
#
#
# Parenthesized expressions are retained as a single item.
#
#	'(rats)'  -->  '(rats)'
#	('a'+'b') -->  'a'+'b'
#
# Returns ( token, parenthesized )
#
# token - 
# parenthesized -
#
class Parser:
	def __init__( self, line ):
		self.line = line
						

	def nextItem(self):
		t = ""
		parenLevel = 0
		inQuote = False
		parenthesized = False
	
		while len(self.line) > 0:
			c = self.line[0]
			self.line = self.line[1:]
		
		
			if parenLevel > 0:
				# Only look for closing paren, another opening paren, or whitespace
				if c == ')':
					parenLevel -= 1
					if parenLevel == 0:
						if len(t) > 0:
							break
						else:
							raise EmptyParenError()
					else:
						t += c
						continue						
				elif c == '(':
					parenLevel += 1
					t += c
					continue						
				elif c == ' ':
					if len(t) > 0:
                        # trailing or internal whitespace, keep it
						t += c
					continue
				else:
					t += c
					continue
		
			if inQuote:
				# Only look for closing quote or escape character
				t += c
				if c == "'":
					inQuote = False
					break
				elif c == "\\":
					# backslash
					if len(self.line)>0:
						if self.line[0] == "\\":
							#Escaped backslash, leave alone and include second backslash
							t += c
							t += self.line[0]
							self.line = self.line[1:]
						elif self.line[0] == "'":
							# Escaped tick mark, leave alone
							t += c
							t += self.line[0]
							self.line = self.line[1:]
						else:
							# Maybe we should treat this as an error, but we don't?
							t += c
				else:
					continue
		
			if c == " " or c == '\t':
				if len(t) > 0:
					# trailing, we are done
					break
				else:
					# leading, ignore it
					pass
            # elif c == '.':
            #     if len(self.line) > 0 and self.line[0] == '.':
            #         # Two dots means comment
            #         self.line = ""
            #         break
            # elif c == ';':
            #     if self.semicolonComments == True:
            #         # In the alternate syntax, a semicolon is a comment character
            #         self.line = ""
            #         break
            #     else:
            #         if len(t) > 0:
            #             # Trailing, it is a delimiter. Leading we ignore it.
            #             break
            #         else:
            #             pass
			elif c == ',':
				if len(t) > 0:
					# Trailing, it is a delimiter. Leading we ignore it.
					break
				else:
					pass
			elif c == '(':
				if len(t) > 0:
					# Already accumulating an arg
					self.line = c + self.line	  # pushback
					break
				else:
					parenLevel = 1
					parenthesized = True
			elif c == ')':
				raise MissingOpenParenError()
				t += c
			elif c == "'":
				if len(t) > 0:
					# Already accumulating an arg
					self.line = c + self.line	  # pushback
					break
				else:
					inQuote = True
					t += c
			elif c == '+' or c == '-' or c == '*' or c == '/':
				if len(t) > 0:
					self.line = c + self.line	  # pushback
					break
				else:
					t = c
					break
			else:
				t += c
	
		# All done with an argument, or at least trying to generate an argument.
		# Do some error checks.
	
		if inQuote:
			raise NoClosingQuoteError()
	
		if parenLevel > 0:
			raise NoClosingParenError()
	
		if len(t) > 0:
			# print( "Parser next item:", t, parenthesized)
			return (t,parenthesized)
		else:
			return (None,None)




def parseLine(line):
	try:
		tok = Parser(line)
		while True:
			s,p = tok.nextItem()
			if s is None:
				break
			print(s)
	except MissingOpenParenError:
		print( "*** No open paren" )
	except EmptyParenError:
		print( "*** Empty parens" )
	except NoClosingParenError:
		print( "*** No closing paren" )
	except NoClosingQuoteError:
		print( "*** No closing quote" )
		
		
		
lines = [
	
	"9",
	"a b c	 d+7   (1*2)   'rats'  x(3)	  'oops'+2	  3+'beep boop'	  7'ouch'  '(mice)'   ('a'+'b')",
	"LDI 0FFH",
	"DC 7, 'WOW', 8,9",
	"FORWARD  EQU FAN + 1",
	"Upside  EQU (FAN* 1)",
	"DC 'a;b'",
	"a b (x*3 ) c",
	"a b ( x*3 ) c",
	"a b( x*3 )c",
    
	"DC 'foo \\\\'",
	"DC 'let\\'s'",

	"a b () c",
	"a b (  ) c",
	"a b ( ok then c",
	"a b ) ok then c)",
	"a b ' ok then c",
	
	"HIGH(BEEP)",
	"DC HIGH(BEEP_A+1)",
	"DC (HIGH(BEEP_A) + 1)"
]


def main( argv ):

	for line in lines:
		print(line)
		print()
		parseLine(line)
		print( "-"*80 )

	print( "-"*80 )
	print( "-----------	 Set Alt Syntax	 ----------------")
	print( "-"*80 )

	foo = [1,2]
	bar = foo
	bar.append(3)
	print(foo)
	print(bar)
	z = bar[1:]
	print(bar)
	print(z)


if __name__ == '__main__':
	sys.exit( main(sys.argv) or 0 )


