#!/usr/bin/env python3

# Chunker
#
# This class is designed to support my Cosmac 1802 Assembler
#

import sys



class ChunkError(Exception): pass


class NoClosingQuoteError(ChunkError): pass



# Break a line of text into an array of "chunks", while stripping comments.
#
# A chunk is a collection of text that forms one assembly language or assembler statement.
# Chunks are delimited by semicolons, and in some cases colons.
# Leading and trailing whitesapce is left intact.
#
# Quote characters (tick) can be escaped with a backslash. Backslash can also be escaped with a backslash.
#
# Examples:
#	LABEL: GHI R2	   ==>	 "LABEL" and "GHI R2"
#	  PHI R2; PHI R3   ==>	 "	PHI R2" and "PHI R3"
#	DC 'let\'s'        ==>   "DC let\'s'"
#	DC 'foo \\'        ==>   "DC 'foo \\'"
#
#
# chunks - a list of chunks
#
class Chunker:
	def __init__( self, line, semicolonComments=False ):
		self.line = line
		self.semicolonComments = semicolonComments
		self.chunks = []
		
		while True:
			chk = self._nextChunk()
			if chk is None:
				break
			else:
				self.chunks.append(chk)
				
		
		
	def _nextChunk(self):
		t = ""
		inParen = False
		inQuote = False
	
		while len(self.line) > 0:
			c = self.line[0]
			self.line = self.line[1:]
		

			if inQuote:
				# Only look for closing quote and escapes
				if c == "'":
					inQuote = False
					t += c
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
					t += c
				continue
		
			if c == '.':
				if len(self.line) > 0 and self.line[0] == '.':
					# Two dots means comment, we are done parsing this line!
					self.line = ""
					break
				else:
					t += c
			elif c == ';':
				if self.semicolonComments == True:
					# In the alternate syntax, a semicolon is a comment character
					self.line = ""
					break
				else:
					# Chunk delimiter
					break
			elif c == ':':
				# Chunk delimiter
				break
			# elif c == ' ' or c == '\t':
			# 	# Space only matters if we are building a label
			# 	if self.firstColumn:
			# 		break;
				# else:
				# 	t += c
			elif c == "'":
				t += c
				inQuote = True
			else:
				t += c
	
		# All done with a token, or at least trying to generate a token.
		# Do some error checks.
	
		if inQuote:
			raise NoClosingQuoteError()
	
		t = t.strip()	# Leading and trailing whitespace never signifigant
		
		if len(t) > 0:
			return t
		else:
			return None




def chunkLine(line, sc=False):
	try:
		chunker = Chunker(line,sc)
		for tt in chunker.chunks:
			print( '"%s"' % tt)
	except NoClosingQuoteError:
		print( "*** No closing quote" )
		
		

lines = [
	
	" 9",
	" a b c	 d+7   (1*2)   'rats'  x(3)	  'oops'+2	  3+'beep boop'	  7'ouch'  '(mice)'	  ('a'+'b')",
	"FOO: GHI R6",
	"BAR GHI R6",
	" LDI 0FFH; SEX 7;SEX 9",
	" DC 7, 'WOW:', 8,9",
	" DC 'a;b'",
	" DC 'foo \\\\'",
	" DC 'let\\'s'",
	" a b c ..Rats Comment",
	" a b c ; LDI X",
	" a b c;GHI R0",
	"	LDI A.1(START); PHI R3",
	" BOOP equ 5+3",

	"a b ' ok then c"
]


altLines = [
	"a b c ; Comment",
	"a b c;Comment"
]



def main( argv ):

	for line in lines:
		print(line)
		print()
		chunkLine(line)
		print( "-"*80 )

	print( "-"*80 )
	print( "-----------	 Set Alt Syntax	 ----------------")
	print( "-"*80 )

	for line in altLines:
		print(line)
		print()
		chunkLine(line,True)
		print( "-"*80 )



if __name__ == '__main__':
	sys.exit( main(sys.argv) or 0 )


