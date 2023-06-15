#!/usr/bin/env python3
#
# 1802 Assembler
#
# Copyright (c) 2015, Donald T. Meyer
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
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


import os
import sys
import argparse
import re

import Chunker
import Parser


listingDest = None

hexDest = None

address = 0

passNumber = 1
lineNumber = 0        # The line number being processed
curLine = None        # Set to the full current line being processed

symbols = {}

BYTES_PER_LINE = 6

pgmImage = None        # Byte array (bytearray) storing the program image

conditionalStack = []    # stack of ConditionalBlock objects

okToEmitCode = True        # This is set by the if/else/endif statements as needed.


#
# Configuration variables
#
verbose = 1
sizeLimit = None
programBase = 0
displayFlag = False
altSyntax = False


# ----------------------------------------------------------------
# File read/write
# ----------------------------------------------------------------


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------


class Symbol:
    """
    name --
    type - "label", "equ"
    """

    def __init__(self, name, body=None, value=None):
        self.lineNumber = lineNumber
        self.name = name
        self.value = value
        self.body = body
        self.ebytes = None

        if body is not None:
            self.type = "equ"
        elif value is not None:
            # A value means this was created from a label, which is a 16-bit address.
            self.type = "label"
            self.ebytes = buildBytes(value, 2)
        else:
            bailout("Symbols must have a body or a value when created '%s'" % self.name)

    def __repr__(self):
        if self.value is None:
            v = "*UNRESOLVED*"
        else:
            v = "0x%04X" % self.value
        return "{ %16s  %4d  %5s  %8s  %s }" % \
            (self.name, self.lineNumber, self.type, v, self.body)

    # Returns true if symbol was resolved
    def resolve(self):
        logDebug("Resolving symbol %s" % self.name)
        if self.value is None:
            if self.body is None:
                bailout("Trying to resolve symbol '%s', but no body" % self.name)
            self.value, self.ebytes = calcExpression(self.lineNumber, self.body)    # FRAK
            if self.value is None:
                return False
        logDebug("Symbol '%s' resolved as %d - %s" % (self.name, self.value, self.ebytes))
        return True


class ConditionalBlock:
    """
    parentState - The state of the enclosing block. If false, this objects state is never set to true.
    state - boolean indicating whether the IF condition was true or not.
    """

    def __init__(self, parentState, state):
        self.parentState = parentState
        if parentState is True:
            self.state = state
        else:
            self.state = False
        self.condState = state
        self.block = "if"        # This can be "if" or "else" to indicate which portion of the conditional is currently being parsed.

    def __repr__(self):
        return "parent state=%d  original state=%d  state=%d  block=%s" % (self.parentState, self.condState, self.state, self.block)

    # Returns True if the state change was valid, False if not.
    def blockToElse(self):
        if self.block == "if":
            self.block == "else"
            if self.parentState is True:
                self.state = not self.state
            return True
        else:
            return False


class Error(Exception):
    """Exception raised for errors.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


#
# Value can be a number, or a string. If a string, it represents a symbol or equation that
# will need to be resolved after the first pass completes.
#
def addSymbol(sym):
    global symbols
    if sym.name in symbols:
        daddr = symbols[sym.name].lineNumber
        bailout("Line: %d   Duplicate symbol '%s'.  Original definition at line %d" % (lineNumber, sym.name, daddr))
    symbols[sym.name] = sym
    sym.resolve()   # We try here because some can be resolved, but this may fail, which is fine.
    # We do another resolve step after the first pass completes.


#
# An address from a label
#
# FOO
#      ..code...
#
def addSymbolLabel(name, value):
    sym = Symbol(name, value=value)
    addSymbol(sym)
    return sym


#
# Add an equate
#
# We just store the body in this call, it will be resolved after the first pass completes.
#
def addSymbolEquate(name, body):
    sym = Symbol(name, body=body)
    addSymbol(sym)
    return sym


def confirmSymbolAddress(name, value):
    sym = symbols[name]
    if value != sym.value:
        bailout("Line: %d   Label '%s' had different address in each pass.  Pass #1=0x%04X, Pass #2=0x%04X" % (lineNumber, name, sym.value, value))


#
# Resolve all of the symbols in the symbol table
#
def resolveSymbols():
    global symbols

    if verbose > 1:
        print("=========================== Resolve Symbols ==============================")
    elif verbose > 0:
        print("Resolve symbols...")

    lastFailCount = None
    while True:
        logDebug("Symbols resolution pass")
        failCount = 0
        for key in symbols:
            sym = symbols[key]
            success = sym.resolve()
            if success is False:
                failCount += 1

        if failCount == 0:
            break

        if lastFailCount is not None:
            if failCount >= lastFailCount:
                # This iteration through the table didn't improve. Do an error logging pass.
                for key in symbols:
                    sym = symbols[key]
                    if sym.value is None:
                        print("*** Line: %d  unable to resolve symbol '%s', expression is '%s'" % (sym.lineNumber, key, sym.body))
                sys.exit(-1)

        lastFailCount = failCount


def dumpSymbols():
    global symbols, listingDest
    listingDest.write("\n\n------------------- Symbols by Name ----------------------\n")
    keys = list(symbols.keys())
    keys.sort()
    for key in keys:
        listingDest.write("%16s : %s\n" % (key, symbols[key]))

    listingDest.write("\n\n")
    for key in keys:
        sym = symbols[key]
        if sym.type == "label":
            v = "%04X" % sym.value
            listingDest.write("%s : %s\n" % (key, v))


def buildBytes(value, numBytes):
    if numBytes == 1:
        if value > 0xFF:
            bailout("Value too high error (8-bits), line %d, value %d" % (lineNumber, value))
    elif numBytes == 2:
        if value > 0xFFFF:
            bailout("Value too high error (16-bits), line %d, value %d" % (lineNumber, value))
    else:
        bailout("Num bytes for conversion cannot exceed 2, line %d" % (lineNumber))

    ebytes = bytearray()
    if numBytes == 2:
        high = (value >> 8) & 0xFF
        ebytes.append(high)

    low = value & 0xFF
    ebytes.append(low)

    return ebytes


#
# Obtain the value for a single token.
#
# Returns a tuple of ( value, bytes ). Will return None if a value could not be obtained.
#
# Examples:
#   7EH
#   99
#   RATS
#   12AA55FFH
#   0AA12AA55FFH
#
def obtainTokenValue(token):
    logDebug("Obtaining token value of '%s'" % token)
    ebytes = bytearray()

    # Is this the "here" address?
    if token == "$":
        ebytes = buildBytes(address, 2)
        return (address, ebytes)

    # Look for a hexadecimal value. These can be very long.
    m = re.match(r'([0-9][0-9a-fA-F]*)H$', token)
    if m:
        # Hex value
        s = m.group(1)
        logDebug("Obtained hex value for '%s'" % s)

        # Convert to a sequence of bytes. (the DC directive needs this behavior)
        ss = s
        if len(s) & 1:
            # Odd might mean leading zero
            if s[0] == '0':
                # Remove the leading zero
                ss = s[1:]
            else:
                # Add a leading zero!
                ss = "0" + ss

        while len(ss) > 0:
            d = ss[:2]
            ebytes.append(int(d, 16))
            ss = ss[2:]

        return (int(s, 16), ebytes)

    # Look for a decimal value.
    m = re.match(r'([0-9]+)D?$', token)
    if m:
        # Always return just one byte because no real way to know how many bytes intended so at least be predictable?
        s = m.group(1)
        logDebug("Obtained dec value for '%s'" % s)
        v = int(s, 10)
        bc = 1
        if v > 0xFF:
            bc = 2
        return (v, buildBytes(v, bc))

    # Is it a Symbol?
    if token in symbols:
        logDebug("Obtained symbol value for token '%s'" % token)
        sym = symbols[token]
        return (sym.value, sym.ebytes)

    # If we get here, we failed to
    logDebug("Failed to obtain value for '%s'" % token)
    return (None, None)


#
# Parses a constant, symbol, or equation and returns the numeric value.
#
# Returns a tuple of ( value, ebytes ). Will return None if a value could not be obtained.
#
# If no value available, returns None.
# If any component was an address, the address flag will be true.
# If any component was a symbol, the literal flag will be false.
# Bytes is returned only if the the expression was a single hex token.
#
# Examples:
#   9
#   0FBH
#   14H
#   0FC00H
#   MICE
#   BSCR-8
#   ROMVAR + 1AH
#    A.0(BEEP)
#    MICE + HIGH START
#    MICE + HIGH START + 4
#
def calcExpression(lineNumber, body):
    logDebug("Calc expression '%s'" % body)
    parser = Parser.Parser(body)
    return evaluate(lineNumber, parser, 1)


#
#
#
def evaluate(lineNumber, parser, maxBytes):
    logDebug("+++ Evaluate '%s'" % parser.line)

    accumValue = None
    ebytes = None

    while True:
        v, ebytes = evalArg(lineNumber, parser, accumValue, maxBytes)
        if v is not None:
            logDebug("arg evaluated to %d - %s" % (v, ebytes))
            accumValue = v
            maxBytes = max(maxBytes, len(ebytes))
        else:
            break

    # recalculate the bytes
    if accumValue is not None:
        logDebug("Recalculate the byte array. Max bytes %d" % maxBytes)
        ebytes = buildBytes(accumValue, maxBytes)

    logDebug("--- Evaluate returning %s : %s" % (accumValue, ebytes))
    return (accumValue, ebytes)


# evalArg - Parse value, parenthesized expression, binary op, or unary op
#
# if accumValue is None:
#             value - store it
#             op - error
#             unary - evalArg
#             parens - eval subParser
#
# if accumValue is set:
#             value - error
#             op - parseValue
#             unary - parseValue
#             parens - error

def evalArg(lineNumber, parser, accumValue, maxBytes):
    s, parenthesized = parser.nextItem()
    logDebug("Parsed '%s'" % s)
    if s is None:
        # Finished
        return (None, None)

    if parenthesized:
        if accumValue is None:
            # Needs to be broken down further, recurse with the paren contents
            subParser = Parser.Parser(s)
            logDebug("calling evaluate for parenthesized expression '%s'" % s)
            value, ebytes = evaluate(lineNumber, subParser, maxBytes)
            if ebytes is not None:
                maxBytes = max(maxBytes, len(ebytes))
        else:
            bailout("Line: %d   Expected operator but found parenthesized expression '%s'" % (lineNumber, s))
    else:
        # Single atomic token

        # Check for single argument operators.
        # A.0, A.1, HIGH, LOW

        if altSyntax is True:
            ma = re.match(r'^(LOW|HIGH)$', s, re.IGNORECASE)
        else:
            ma = re.match(r'^A.([0-1])$', s)

        if ma is not None:
            # Unary Operator - Low or high byte of address
            logDebug("Get address byte")
            v, ebytes = evalArg(lineNumber, parser, accumValue, maxBytes)
            maxBytes = 1

            if altSyntax is True:
                lowByte = s.upper() == 'LOW'
            else:
                lowByte = ma.group(1) == '0'

            if lowByte is True:
                value = v & 0xFF
            else:
                value = (v >> 8) & 0xFF

        elif re.match(r'\s*([\-\+\*\/])', s) is not None:
            # Binary Operator

            if accumValue is None:
                bailout("Line: %d   Found binary operator '%s' but expected value or unary operator" % (lineNumber, s))
            else:
                v, ebytes = evaluate(lineNumber, parser, maxBytes)
                if v is None:
                    bailout("Line: %d   Bad argument for operator '%s'" % (lineNumber, s))

                logDebug("Adding %d to %d" % (v, accumValue))
                if s == '+':
                    value = accumValue + v
                if s == '-':
                    value = accumValue - v
                if s == '*':
                    value = accumValue * v
                if s == '/':
                    value = accumValue / v

                maxBytes = max(maxBytes, len(ebytes))
        else:
            # Not an operator, must be a value

            if accumValue is None:

                # A character constant?
                m = re.match(r"'(.)'", s)
                if m:
                    s = m.group(1)
                    chars = list(s)
                    value = ord(chars[0])
                    maxBytes = max(maxBytes, 1)
                else:

                    value, ebytes = obtainTokenValue(s)
                    logDebug("Token value is %s - %s" % (value, ebytes))
                    if value is None:
                        return (None, None)        # Could not obtain a value
                    maxBytes = max(maxBytes, len(ebytes))
            else:
                bailout("Line: %d   Expected operator but found value '%s'" % (lineNumber, s))

    # recalculate the bytes
    if value is not None:
        logDebug("Recalculate the byte array. Max bytes %d" % maxBytes)
        ebytes = buildBytes(value, maxBytes)

    logDebug("--- Evaluate returning %s : %s" % (value, ebytes))
    return (value, ebytes)


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------


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
def assembleDC(body):
    global address

    logDebug("Assemble DC '%s'" % body)

    startAddr = address

    bytes = bytearray()

    # Break up into chunks
    chunks = body.split(',')
    for chunk in chunks:
        chunk = chunk.strip()
        m = re.match(r"'(.+)'", chunk)
        if m:
            s = m.group(1)
            chars = list(s)
            for c in chars:
                bytes.append(ord(c))
        else:
            v, ebytes = calcExpression(lineNumber, chunk)   # FRAK
            # print( "Literal expression evaluated to %s %s" % ( v, ebytes ) )
            # logDebug( ebytes )
            if v is None:
                if passNumber == 1:
                    # Forward ref ok for 1st pass
                    v = 0
                    ebytes = b'\00\00'
                else:
                    bailout("Line: %d   Unresolved expression '%s'" % (lineNumber, chunk))
            if ebytes is not None:
                # Sequence of bytes
                bytes.extend(ebytes)

    address += len(bytes)
    return (startAddr, bytes)


def assembleLOAD(body):
    """Process the LOAD macro.
    Syntax is "LOAD Rn, <addr>
    """
    global address

    logDebug("Assemble LOAD '%s'" % body)

    startAddr = address
    bytes = bytearray()

    m = re.match(r"\s*R([0-9A-F])\s*,\s*(.+)\s*", body)
    if m:
        r = int(m.group(1), 16)
        exp = m.group(2)
        a, _ = calcExpression(lineNumber, exp)

        if a is None:
            if passNumber == 1:
                # Forward ref ok for 1st pass
                a = 0
            else:
                bailout("Line: %d   Unresolved expression '%s'" % (lineNumber, exp))

        bytes.append(0xF8)
        bytes.append(a // 256)
        bytes.append(0xB0 + r)

        bytes.append(0xF8)
        bytes.append(a % 256)
        bytes.append(0xA0 + r)
    else:
        bailout("Line: %d   Invalid LOAD '%s'" % (lineNumber, body))

    address += len(bytes)
    return (startAddr, bytes)


def parseRegister(arg):
    m = re.match(r'^R?([0-9A-F])', arg)
    if m is not None:
        return int(m.group(1), 16)
    else:
        if passNumber == 1:
            # symbols not resolved yet
            return 0
        v, __ = calcExpression(lineNumber, arg)
        # print( v, aflag, lflag, ebytes )
        if v is not None:
            if v < 0 or v > 15:
                bailout("Line: %d  Invalid register value %d for '%s'" % (lineNumber, v, arg))
            else:
                return v
        else:
            bailout("Line: %d  Invalid register '%s'" % (lineNumber, arg))


def assembleRegOp(opBase, arg, bytes):
    r = parseRegister(arg)
    bytes.append(opBase + r)


def assembleLoadN(opBase, arg, bytes):
    r = parseRegister(arg)
    if r == 0:
        bailout("Line: %d   Register for Load N operation cannot be zero" % lineNumber)
    bytes.append(opBase + r)


# Parses a value or an address. Address must use the A.0() or A.1() formats
def assembleImmediate(opBase, arg, bytes):
    if passNumber == 1:
        bytes.append(0)
        bytes.append(0)
        return

    v, __ = calcExpression(lineNumber, arg)
    if v is None:
        bailout("Line: %d   Invalid argument (immediate) '%s'" % (lineNumber, arg))
    elif v > 0xFF:
        bailout("Line: %d   Argument out of range, must be 0-255" % lineNumber)

    bytes.append(opBase)
    bytes.append(v)


# Takes an address argument and emits the LSB
# If the MSB differs from the immediate args address MSB, declare a branch range error
def assembleShortBranch(opBase, arg, bytes):
    if passNumber == 1:
        bytes.append(0)
        bytes.append(0)
        return

    v, __ = calcExpression(lineNumber, arg)    # FRAK
    if v is None:
        bailout("Line: %d   Invalid argument (short branch)" % lineNumber)
    logDebug("SB arg addr is 0x%04X" % (address + 1))
    a_page = (address + 1) >> 8 & 0xFF
    b_page = (v) >> 8 & 0xFF
    if a_page != b_page:
        bailout("Line: %d   Branch out of range" % lineNumber)
    bytes.append(opBase)
    bytes.append(v & 0xFF)


# Takes an address argument and emits the MSB and LSB
def assembleLongBranch(opBase, arg, bytes):
    if passNumber == 1:
        bytes.append(0)
        bytes.append(0)
        bytes.append(0)
        return

    v, __ = calcExpression(lineNumber, arg)    # FRAK
    if v is None:
        bailout("Line: %d   Invalid argument (long branch)" % lineNumber)
    bytes.append(opBase)
    bytes.append(v >> 8 & 0xFF)
    bytes.append(v & 0xFF)


# Parses an integer value 1-7
def assembleInputOutput(opBase, arg, bytes):
    m = re.match(r'^([0-7]$)', arg)
    if m:
        bytes.append(opBase + int(m.group(1), 10))
    else:
        bailout("Line: %d   IO port must be 1-7" % lineNumber)


#  mnemonic : [opcode], [func]
#  opcode may be a base opcode used by the func (e.g. DEC)
#  if no func, opcode used as-is
opTable = {
    "IDLE": (0x00, None),
    "LDN": (0x00, assembleLoadN),
    "INC": (0x10, assembleRegOp),
    "DEC": (0x20, assembleRegOp),

    "BR": (0x30, assembleShortBranch),
    "BQ": (0x31, assembleShortBranch),
    "BZ": (0x32, assembleShortBranch),
    "BDF": (0x33, assembleShortBranch),
    "BPZ": (0x33, assembleShortBranch),
    "BGE": (0x33, assembleShortBranch),
    "B1": (0x34, assembleShortBranch),
    "B2": (0x35, assembleShortBranch),
    "B3": (0x36, assembleShortBranch),
    "B4": (0x37, assembleShortBranch),
    "NBR": (0x38, None),
    "SKP": (0x38, None),
    "BNQ": (0x39, assembleShortBranch),
    "BNZ": (0x3A, assembleShortBranch),
    "BNF": (0x3B, assembleShortBranch),
    "BM": (0x3B, assembleShortBranch),
    "BL": (0x3B, assembleShortBranch),
    "BN1": (0x3C, assembleShortBranch),
    "BN2": (0x3D, assembleShortBranch),
    "BN3": (0x3E, assembleShortBranch),
    "BN4": (0x3F, assembleShortBranch),

    "LDA": (0x40, assembleRegOp),

    "STR": (0x50, assembleRegOp),

    "IRX": (0x60, None),

    "OUT": (0x60, assembleInputOutput),    # 61 - 67
    # 68 Reserved
    "INP": (0x68, assembleInputOutput),    # 69 - 6F

    "RET": (0x70, None),
    "DIS": (0x71, None),
    "LDXA": (0x72, None),
    "STXD": (0x73, None),
    "ADC": (0x74, None),
    "SDB": (0x75, None),
    "SHRC": (0x76, None),
    "RSHR": (0x76, None),
    "SMB": (0x77, None),
    "SAV": (0x78, None),
    "MARK": (0x79, None),
    "REQ": (0x7A, None),
    "SEQ": (0x7B, None),
    "ADCI": (0x7C, assembleImmediate),
    "SDBI": (0x7D, assembleImmediate),
    "SHLC": (0x7E, None),
    "RSHL": (0x7E, None),
    "SMBI": (0x7F, assembleImmediate),

    "GLO": (0x80, assembleRegOp),
    "GHI": (0x90, assembleRegOp),

    "PLO": (0xA0, assembleRegOp),
    "PHI": (0xB0, assembleRegOp),

    "LBR": (0xC0, assembleLongBranch),
    "LBQ": (0xC1, assembleLongBranch),
    "LBZ": (0xC2, assembleLongBranch),
    "LBDF": (0xC3, assembleLongBranch),
    "NOP": (0xC4, None),
    "LSNQ": (0xC5, None),
    "LSNZ": (0xC6, None),
    "LSNF": (0xC7, None),
    "LSKP": (0xC8, None),
    "NLBR": (0xC8, None),
    "LBNQ": (0xC9, assembleLongBranch),
    "LBNZ": (0xCA, assembleLongBranch),
    "LBNF": (0xCB, assembleLongBranch),
    "LSIE": (0xCC, None),
    "LSQ": (0xCD, None),
    "LSZ": (0xCE, None),
    "LSDF": (0xCF, None),

    "SEP": (0xD0, assembleRegOp),

    "SEX": (0xE0, assembleRegOp),

    "LDX": (0xF0, None),
    "OR": (0xF1, None),
    "AND": (0xF2, None),
    "XOR": (0xF3, None),
    "ADD": (0xF4, None),
    "SD": (0xF5, None),
    "SHR": (0xF6, None),
    "SM": (0xF7, None),
    "LDI": (0xF8, assembleImmediate),
    "ORI": (0xF9, assembleImmediate),
    "ANI": (0xFA, assembleImmediate),
    "XRI": (0xFB, assembleImmediate),
    "ADI": (0xFC, assembleImmediate),
    "SDI": (0xFD, assembleImmediate),
    "SHL": (0xFE, None),
    "SMI": (0xFF, assembleImmediate)
}


# Returns a tuple of starting address and a byte array of the machine code.
def assembleChunk(chunk):
    global address

    # Get the opcode and optional argument
    m = re.match(r'^(\w+)\s*(.*)', chunk)
    if m is None:
        bailout("Line: %d  Invalid line '%s'" % (lineNumber, chunk))

    bytes = bytearray()
    startAddr = address

    opcode = m.group(1)
    mnemonic = m.group(1)
    arg = m.group(2)
    logDebug("Chunk '%s'  opcode '%s'  arg '%s'" % (chunk, opcode, arg))

    if mnemonic in opTable:
        opbase, func = opTable[mnemonic]
        if func:
            logDebug("Calling opcode func {0}".format(func))
            func(opbase, arg, bytes)
        elif opbase is not None:
            logDebug("Appending opbase {0}".format(opbase))
            bytes.append(opbase)
        else:
            bailout("Internal error - invalid table for opcode '%s'" % mnemonic)
    else:
        bailout("Line: %d  Invalid mnemonic '%s'" % (lineNumber, chunk))

    address += len(bytes)
    return (startAddr, bytes)


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------

# Emit the results of a line of code.
#
# This will also deal with breaking the hex bytes flow to the next line if the width is too great.
#
def emitCode(startAddr, bytes):
    global pgmImage

    if startAddr < programBase:
        bailout("Data written to address 0x%04X below the program base of 0x%04X" % (startAddr, programBase))
    # Add bytes to the program image
    end = startAddr + len(bytes)
    pgmImage[startAddr:end] = bytes

    hexStr = ""
    overflow = False
    for byte in bytes:
        pair = "%02X" % byte
        hexStr += pair
        if len(hexStr) >= (BYTES_PER_LINE * 2):
            hexStr += ';'
            if overflow is False:
                emitListing("%04X %-14s %04d  %s" % (startAddr, hexStr, lineNumber, curLine))
                hexStr = ""
                overflow = True
            else:
                emitListing("%04X %s" % (startAddr, hexStr))
                hexStr = ""
            startAddr += BYTES_PER_LINE

    if hexStr != "":
        hexStr += ';'
        if overflow is False:
            emitListing("%04X %-14s %04d  %s" % (startAddr, hexStr, lineNumber, curLine))
        else:
            emitListing("%04X %s" % (startAddr, hexStr))


def processEquate(label, body):
    body = body.strip()

    if passNumber == 1:
        addSymbolEquate(label, body)
    emitNoCode()


def processOrigin(body):
    global address

    v, __ = calcExpression(lineNumber, body)
    if v is None:
        bailout("Line: %d  Unable to resolve origin address for '%s'" % (lineNumber, body))

    emitNoCode()
    address = v


def processPage():
    global address

    emitNoCode()

    if address & 0xFF != 0:
        # Adjust the address to the next 256-byte page start
        page = address >> 8 & 0xFF
        page += 1

        address = page << 8


def processIf(body):
    global okToEmitCode

    emitNoCode()

    v, __ = calcExpression(lineNumber, body)
    if v is None:
        bailout("Line: %d  Unable to resolve conditional expression for '%s'" % (lineNumber, body))
    c = ConditionalBlock(okToEmitCode, v != 0)
    conditionalStack.append(c)
    okToEmitCode = c.state
    logDebug("cblock %s" % c)
    logDebug("Ok to emit code = %d" % okToEmitCode)


def processElse():
    global okToEmitCode
    emitNoCode()
    if len(conditionalStack) < 1:
        bailout("Line: %d: Found a conditional block 'else' while not in a conditional block" % lineNumber)
    f = conditionalStack[-1].blockToElse()
    if f is False:
        bailout("Line: %d: Found a second conditional block 'else' while already in an else block" % lineNumber)
    okToEmitCode = conditionalStack[-1].state
    logDebug("cblock %s" % conditionalStack[0])
    logDebug("Ok to emit code = %d" % okToEmitCode)


def processEndif():
    global okToEmitCode
    emitNoCode()
    if len(conditionalStack) < 1:
        bailout("Line: %d: Found a conditional block 'end' while not in a conditional block" % lineNumber)

    conditionalStack.pop()
    if len(conditionalStack) > 0:
        okToEmitCode = conditionalStack[-1].state
        logDebug("cblock %s" % conditionalStack[0])
    else:
        okToEmitCode = True
    logDebug("Ok to emit code = %d" % okToEmitCode)


# Emit the contents of a source line that generated no code.
#
# This only emits text during pass 2, so it can be called during pass 1 with no ill effects.
#
def emitNoCode():
    if passNumber == 2:
        if curLine == "":
            emitListing("%04X ;              %04d" % (address, lineNumber))
        else:
            emitListing("%04X ;              %04d  %s" % (address, lineNumber, curLine))


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------

#
# Process a line of source
#
#
def processLine(line):
    global curLine

    # line = line.rstrip()    # remove trailing whitespace

    logDebug("------- Line '%s'" % line)

    curLine = line.rstrip()    # remove trailing whitespace, just because printing it on on the listing is silly.

    # Some statements are only valid in a single chunk per line scenario, such as equates.
    # FOO equ 0
    #
    # Some statements are only valid as the first chunk, such as equates and conditionals.

    # Equate?
    # Since equates are allowed to start in the first column, we have to test for them first to prevent
    # them from being treated as a label.
    m = re.match(r'^\s*(\w+)\s+EQU\s+(.+)', line, re.IGNORECASE)
    if m:
        # Line is an equate
        if not okToEmitCode:
            # No code emit also means don't process an equate
            emitNoCode()
            return

        label = m.group(1)
        body = m.group(2)
        logDebug("Equate: '%s'   body '%s'" % (label, body))
        # The remainder of the equate line (everything after the "equ") must be a single chunk.
        chunker = Chunker.Chunker(body, semicolonComments=altSyntax)
        logDebug("chunks: %s" % chunker.chunks)
        if len(chunker.chunks) != 1:
            bailout("Line: %d  Equate body parse failed" % lineNumber)
        logDebug("Equate: '%s'   value chunk '%s'" % (label, chunker.chunks[0]))
        processEquate(label, chunker.chunks[0])
        return

    # Label?
    m = re.match(r'^(\w+):?\s*(.*)', line)
    if m:
        # Line has a label
        if not okToEmitCode:
            # No code emit also means don't process an equate
            emitNoCode()
            return

        label = m.group(1)
        body = m.group(2)
        logDebug("Label: '%s'   remainder '%s'" % (label, body))
        if passNumber == 1:
            # Add it to the symbol table!
            addSymbolLabel(label, address)
        elif passNumber == 2:
            # Make sure the address matches, for sanity checking.
            confirmSymbolAddress(label, address)

        line = body   # Basically strip the label from the line, then it gets processed as usual.

    # We call this first off, even though in some cases we don't actually want things
    # chunked up (such as for equates)
    # This does get rid of comments, which is important.
    chunker = Chunker.Chunker(line, semicolonComments=altSyntax)

    if len(chunker.chunks) == 0:
        # No chunks or label, just an empty line. Or a label!
        emitNoCode()
        return

    firstChunk = True    # First chunk is special, it can be a directive.
    startAddr = None
    lineBytes = bytearray()

    for chunk in chunker.chunks:

        # Only the first chunk can be a directive.
        if firstChunk:
            firstChunk = False

            # Directive?
            if processDirective(chunk) is True:
                # Yes, was a directive. Continue with next chunk
                continue

        body = chunk

        logDebug("Body '%s'" % body)

        if altSyntax is True:
            m = re.match(r'^DB\s+(.*)', body)
        else:
            m = re.match(r'^DC\s+(.*)', body)

        if m:
            # Line is a DC directive
            body = m.group(1)
            addr, bytes = assembleDC(body)
            if startAddr is None:
                startAddr = addr
            lineBytes.extend(bytes)
        else:
            m = re.match(r'^LOAD\s+(.*)', body)
            if m:
                # Line is a LOAD macro
                body = m.group(1)
                addr, bytes = assembleLOAD(body)
                if startAddr is None:
                    startAddr = addr
                lineBytes.extend(bytes)
            else:
                # Looks like we have a normal statment, opcode style!
                addr, bytes = assembleChunk(body)
                if startAddr is None:
                    # Capture the address of the first instructions of the line.
                    # (We may acumulate more instructions in subsequent chunks.)
                    startAddr = addr
                lineBytes.extend(bytes)

    if passNumber == 2 and len(lineBytes) > 0:
        # This is the code emiting pass, and we have machine code to emit.
        emitCode(startAddr, lineBytes)


def processDirective(line):

    # IF?
    m = re.match(r'^IF\s+(.+)', line, re.IGNORECASE)
    if m:
        # Line is an IF directive
        body = m.group(1)
        logDebug("If: '%s'" % (body))
        processIf(body)
        return True

    # ELSE?
    m = re.match(r'^ELSE$', line, re.IGNORECASE)
    if m:
        # Line is an else directive
        logDebug("Else")
        processElse()
        return True

    # ENDI?
    m = re.match(r'^ENDI$', line, re.IGNORECASE)
    if m:
        # Line is an end if directive
        logDebug("End If")
        processEndif()
        return True

    if not okToEmitCode:
        emitNoCode()
        return True

    # - - - - - - - - - - - - - - - - -

    # Org?
    m = re.match(r'^ORG\s+(.*)', line, re.IGNORECASE)
    if m:
        # Line is an origin directive
        body = m.group(1)
        logDebug("Origin: '%s'" % (body))
        processOrigin(body)
        return True

    # PAGE?
    m = re.match(r'^PAGE(.*)', line, re.IGNORECASE)
    if m:
        # Line is a page directive
        logDebug("Page")
        processPage()
        return True

    # END?
    m = re.match(r'^END(.*)', line, re.IGNORECASE)
    if m:
        # Line is a END directive
        logDebug("End")
        emitNoCode()
        # TODO: Should ignore everything after this line?
        return True

    return False


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------


#
# First pass - create the symbol table
#
def firstPass(lines):
    global passNumber, lineNumber

    if verbose > 1:
        print("=========================== First Pass ==============================")
    elif verbose > 0:
        print("First Pass...")

    passNumber = 1
    lineNumber = 0
    for line in lines:
        lineNumber += 1
        processLine(line)


#
# Second pass - actual assembly and output.
#
# In this pass, we do the actual assembly since we now have the complete symbol table that was
# created in the first pass.
#
def secondPass(lines):
    global passNumber, lineNumber, address

    if verbose > 1:
        print("=========================== Second Pass ==============================")
    elif verbose > 0:
        print("Second Pass...")

    passNumber = 2
    lineNumber = 0
    address = 0
    for line in lines:
        lineNumber += 1
        processLine(line)


def assembleFile(src):
    global pgmImage

    lines = src.readlines()

    firstPass(lines)
    logVerbose("Last address used: 0x%04X" % (address - 1))

    if sizeLimit:
        if address >= sizeLimit + programBase:
            bailout("Program too large by %d bytes" % ((address - (sizeLimit + programBase))))

    # Set up a byte array to hold the assembled program image.
    pgmImage = bytearray()
    for _ in range(address):
        pgmImage.append(0xFF)    # pad byte

    resolveSymbols()
    # if verbose > 1:
    #     dumpSymbols()

    secondPass(lines)


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------

def process(src):
    global listingDest, hexDest

    rootname, __ = os.path.splitext(src.name)

    if displayFlag is True:
        listingDest = sys.stdout
        hexDest = sys.stdout
    else:
        listingFilename = rootname + ".lst"
        listingDest = open(listingFilename, 'w')
        hexFilename = rootname + ".hex"
        hexDest = open(hexFilename, 'w')

    assembleFile(src)

    src.close()

    writeHexFile()

    dumpSymbols()

    if listingDest:
        listingDest.close()

    if hexDest:
        hexDest.close()


def emitListing(text):
    global listingDest

    if listingDest:
        listingDest.write(text + "\n")


def writeHexFile():
    global hexDest, pgmImage

    text = dataToHexStrings(pgmImage)
    hexDest.write(text)


def dataToHexStrings(data):
    if programBase > 0:
        del data[:programBase]
    buf = ""
    bytes = 0
    for b in data:
        buf = buf + "%02X" % b
        bytes += 1
        if bytes >= 16:
            buf += "\n"
            bytes = 0

    return buf


# ----------------------------------------------------------------
#
# ----------------------------------------------------------------

def logVerbose(msg):
    if verbose > 0:
        print(msg)


def logDebug(msg):
    if verbose > 1:
        print(msg)


def logWarning(msg):
    if passNumber == 2:
        print("WARN: Line %d: %s" % (lineNumber, msg))


def bailout(msg):
    if __name__ == '__main__':
        print("*** %s" % msg)
        sys.exit(-1)
    else:
        raise Error(msg)


def auto_int(x):
    """Simple helper to allow parsing arguments in bases other than 10."""
    return int(x, 0)


def main(argv=None):
    global verbose, sizeLimit, programBase, displayFlag, altSyntax

    description = """Assemble 1802 source"""

    parser = argparse.ArgumentParser(description=description)

    parser.set_defaults(verbose=1)

    parser.add_argument("-a", "--altsyntax",
                        action="store_true", dest="altSyntax", default=False,
                        help="Alternate assembler syntax (; for comments)")

    parser.add_argument("-s", "--size",
                        action="store", type=auto_int, dest="size", default=None,
                        help="Maximum size of output. Error if this size is exceeded. (optional)")

    parser.add_argument("-b", "--base",
                        action="store", type=auto_int, dest="base", default=0,
                        help="Base offset of the program image. Default is 0x0000. (optional)")

    parser.add_argument("-d", "--display",
                        action="store_true", dest="display", default=False,
                        help="Display output on terminal. No files are produced.")

    parser.add_argument("-n", "--noaction",
                        action="store_true", dest="noaction", default=False,
                        help="Simulate the action")

    parser.add_argument("-q", "--quiet",
                        action="store_const", const=0, dest="verbose",
                        help="quiet")

    parser.add_argument("-v", "--verbose",
                        action="store_const", const=1, dest="verbose",
                        help="verbose [default]")

    parser.add_argument("--noisy",
                        action="store_const", const=2, dest="verbose",
                        help="noisy")

    parser.add_argument("source",
                        type=argparse.FileType('r'),
                        metavar="SOURCE-FILE")

    options = parser.parse_args(argv)

    verbose = options.verbose
    sizeLimit = options.size
    programBase = options.base
    displayFlag = options.display
    altSyntax = options.altSyntax

    logDebug(options)

    # Get the filename
    if options.source is not None:
        process(options.source)
    else:
        print("No file name given.")
        print(main.__doc__)
        sys.exit(1)


if __name__ == '__main__':
    # print(os.getcwd())
    # sys.exit( main(["cosmacasm", "--noisy", "assembler/test_src/test.src"]) or 0 )
    # sys.exit( main(["cosmacasm", "assembler/test_dc.src"]) or 0 )
    # sys.exit( main(["cosmacasm", "--noisy", "assembler/test/test_dc.src"]) or 0 )
    # sys.exit( main(["cosmacasm", "--noisy", "assembler/test/test_exp.src"]) or 0 )
    sys.exit(main() or 0)
