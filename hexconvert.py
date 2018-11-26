#!/usr/bin/env python3
#
# Hex Converter
#
# Copyright (c) 2018, Donald T. Meyer
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
#
# Convert hex files to and from various formats.
#
# Display information about hex files.
# *** Add ability to read and merge multiple files (i.e. make two 4k images into one 8k image)
#
# Raw Hex => Intel or Motorola
#   Starting address defaults to 0x0000. Can be set via options.
#
# Intel or Motorola => Raw Hex
#   Records placed at record address, with hex bytes being padded from 0x0000 as needed.
#   Offset can be set via options.
#   As in, if record starts at 0x2000 and an offset of 0x2000 is set, the first byte from
#   the record will be the first byte in the output hex file.
#   With no offset applied, the output file would start with 8k of 0xFF bytes followed by
#   the first byte from the first input record.
#
#-------------------------------------------
#

import os, sys, csv, datetime, time
import codecs
import argparse
import re
import string

import epromimage
from epromimage import EPROM

output_format = None
size = None
dump_hex = None


def process(src_filename,dest_filename):
    ftype, astart, aend, alen, __, __  = epromimage.scanfile( src_filename )
    print( "-- Source File --\nFull Span: 0x%04X - 0x%04X   Size: %6d   Type: %s" % (astart, aend, alen, ftype))

    if alen > size:
        print( "ERROR: The source file is too large to fit in the specified EPROM size of 0x%04X" % size )
        sys.exit( -1 )

    eprom = EPROM(size)
    eprom.readfile( src_filename )

    print( "\n-- EPROM Image --" )
    print(eprom)

    if dump_hex:
        print()
        print( eprom.as_hexdump() )

    # Write out the file in a new format
    if output_format == "hex":
        eprom.write_file_as_raw_hex( dest_filename )
    elif output_format == "intel":
        eprom.write_file_as_intel_hex( dest_filename )
    elif output_format == "mot":
        eprom.write_file_as_srecords( dest_filename )
    elif output_format == "bin":
        eprom.write_file_as_binary( dest_filename )



def main( argv=None ):
    """This is the main function, and entry point for the application."""
    global size, dump_hex, output_format

    description = """Input file is hex data in one of the supported formats.
    If an output format is specified but no destination filename is given, the output
    filename will be the input filename with the appropriate new extension.
    If no output format is given, displays a summary of the file."""

    exts = {"hex": "hex", "intel": "ihex",
            "mot": "s19", "bin": "bin"}  # Output formats

    parser = argparse.ArgumentParser(description=description)
    
    parser.add_argument( "-s", "--size",
                        action="store", type=int, default=0x2000,
                        help="Size of EPROM image. (default=8,192)" )
    
    parser.add_argument( "-f", "--format",
                        action="store", dest="output_format",
                        choices=exts.keys(),
                        metavar="FORMAT",
                        help="Format of output file. 'hex', 'intel', 'mot', 'bin'" )
    
    parser.add_argument( "-d", "--dump",
                        action="store_true", dest="dump_hex",
                        help="Hex Dump of the file" )

    parser.add_argument( "-o", "--destination",
                        action="store", dest="dest_name",
                        metavar="PATH",
                        help="Name of output file (optional)" )

    parser.add_argument("source", nargs="+",
                        type=argparse.FileType('r'),
                        metavar="INPUT-FILE")
    
    options = parser.parse_args(argv)
    
    # print( options )
    # logDebug( args )
    # print(options.source)

    # Set the global vars that the rest of the program will need.
    size = options.size
    output_format = options.output_format
    dump_hex = options.dump_hex

    # Get the filename
    filename = options.source[0].name
    options.source[0].close()

    if options.dest_name == None:
        if output_format != None:
            # generate a dest name
            ext = exts[output_format]
            dest = "out.%s" % ext
        else:
            dest = None
    else:
        # Use given dest name. Must have an output format.
        if output_format == None:
            print( "*** Destination name given but no output format specified!")
            sys.exit( -1 )

        dest = options.dest_name

    process( filename, dest )
    
    

if __name__ == '__main__':
    # sys.exit( main(["hexconvert", "epromimage-samples/bitload.hex", "-d"]) or 0 )
    # sys.exit( main(["hexconvert", "epromimage-samples/bitload.hex", "-d", "-f", "hex"]) or 0 )
    ##sys.exit( main(["hexconvert", "epromimage-test-out.ihex", "-d"]) or 0 )
    # sys.exit( main(["/Users/don/Documents/Electronics/Cosmac 1802/EPROM Images/27C64/FIG-FORTH 1.0.s19", "-d", "-f", "hex"]) or 0 )
    sys.exit( main() or 0 )
    

