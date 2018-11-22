#!/usr/bin/env python3
#
# EPROM Image Class
#
# Copyright (c) 2017, Donald T. Meyer
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
# ------------------------------------------
#
# sudo pip3 install bincopy
#
#
# https://pypi.python.org/pypi/bincopy
#
#
# ------------------------------------------
# 
#
# ------------------------------------------
#

"""
API:

    readFile() add data from a Raw Hex, Intel Hex or S-Record file

    addBytes() add a byte array at a given address

    chunks() returns a list of tuples consisting of a start address and a byte array

    checksum() returns a checksum of the image

    writeFileAsRawHex() writes contents to a file in the Raw Hex format
    writeFileAsIntelHex() writes contents to a file in the Intel Hex format
    writeFileAsSRecords() writes contents to a file in the Motorola S-Record format

    asHexDump() returns a string with the EPROM contents as a human-readable hex dump
                Option for this to be full or sparse?
"""

import os, sys
import re
import string

import bincopy



class Error(Exception):
    """ Exception raised for errors.
    """
    pass


class EPROM:
    """ This class represents a virtual EPROM.

    Instance Variables:
        image - The bytearray image of the contents
    """
    def __init__( self, size, offset=0 ):
        """ The size is the size of the EPROM in bytes.
        
        The offset is the address in the memory map where the EPROM will be addressed.
        """
        if (size % 1024) != 0:
            print( "WARNING: An EPROM size should really be a multiple of 1024 bytes!" )
        if (offset % 1024) != 0:
            print( "WARNING: An EPROM offset should really be a multiple of 1024 bytes!" )
        self.offset = offset
        self.size = size
        self.image = bytearray(b'\xff') * size
        self.binfile = bincopy.BinFile()
        
        
    def __repr__(self):
        chunks = []
        chunks.append( "Size %d  Offset %d  Cksum: %04X" % (self.size, self.offset, self.checksum()) )
        for addr, data in self.binfile.segments:
            # print(seg)
            # chunks.append("Address Range 0x%04X - 0x%04X   Length: 0x%04X (%4d)" % (seg[0], seg[1]-1, len(seg[2]), len(seg[2])) )
            chunks.append("Address Range 0x%04X - 0x%04X   Length: 0x%04X (%4d)" % (addr, addr+len(data)-1, len(data), len(data)) )
        return '\n'.join(chunks)
        
        
    def __cmp__( self, other ):
        return self.image == other.image
        
        
    def checksum(self):
        cs = sum(self.image) & 0xFFFF
        return cs


    def chunks(self):
        """ This returns a chunk iterator. Chunks are tuples ( address, databytes )
        
        The chunk addresses are zero-based. As in, all addresses are relative to the first byte of the image.
        
        As in, if the image is a size of 256 bytes, the first address will be 0 and the last address will be 255 regardless of the offset.
        This is designed to support writing to an EPROM.
        """
        chunk_iter = ( (addr-self.offset,data) for addr,data in self.binfile.segments)
        return chunk_iter
    

    #----------------------------------------------------------------
    #   Data Import
    #----------------------------------------------------------------

    def add_bytes( self, addr, data ):
        """Add bytes to the EPROM image.
        
        An exception will be raised if a byte is written to twice.
        addr - Absolute address. The first legal address is the same as the EPRTOM offset.
        data - A byte array.
        """
        self.binfile.add_binary( data, addr )
        self._add_bytes_to_image( addr, data )


    def _add_bytes_to_image( self, addr, data ):
        """
        This adds the bytes in the bytearray 'data' to the image array.
        
        Address is absolute, not relative to the EPROM start. (unless the offset is zero of course)
        """
        if addr < self.offset:
            raise Error( "Cannot add bytes to the EPROM image at addr 0x%04X - it is less than the offset addr 0x%04X" % (addr,self.offset))
        start = addr - self.offset
        end = start + len(data)
        if end > self.size:
            raise Error( "Added bytes of length %d at addr 0x%04X would run past the end of the EPROM, whose size is %d" % (len(data), addr, self.size) )
        self.image[start:end] = data
    

    def readfile( self, filename ):
        """ Reads a hex file, adding it's contents to the EPROM.
        Valid file formats are Intel Hex, Motorola S-Records, Binary, and Raw Hex.
        
        Returns the file type as a string: "srecord", "hex", "intelhex", "binary"
        """
        # Step 1, what kind of file?
        ftype = _get_filetype( filename )
        
        # Step 2, read the file into the BinFile
        if ftype == "srecord":
            self.binfile.add_srec_file( filename )
        elif ftype == "binary":
            self.binfile.add_binary_file( filename )
        elif ftype == "intelhex":
            self.binfile.add_ihex_file( filename  )
        elif ftype == "hex":
            bb = _import_hex( filename )
            self.binfile.add_binary( bb )   
        else:
            raise Error( "Unknown file type for %s" % filename )
            
        # Step 3, Iterate through the BinFile addding the bytes to our full image.
        for addr,data in self.binfile.segments:
            self._add_bytes_to_image( addr, data )
        
        return ftype


    #----------------------------------------------------------------
    # Export
    #----------------------------------------------------------------

    def write_file_as_intel_hex(self,filename):
        dest = open( filename, 'w' )
        dest.write( self.binfile.as_ihex() )
        dest.close()


    def write_file_as_srecords(self,filename):
        dest = open( filename, 'w' )
        dest.write( self.binfile.as_srec() )
        dest.close()


    def write_file_as_raw_hex(self,filename):
        dest = open( filename, 'w' )
        data = self.binfile.as_binary()
        buf = self._data_to_hex_strings( data )
        dest.write( buf )
        dest.close()


    def write_file_as_binary(self,filename):
        dest = open( filename, 'w' )
        dest.write( self.binfile.as_binary() )
        dest.close()

    
    def as_hexdump(self):
        """ The addresses used by the hex dump are absolute. As in, the first byte of the EPROM would be the offset address."""
        # self.binfile.fill()
        hd = self.binfile.as_hexdump()
        return hd


    def _data_to_hex_strings( self, data ):
        buf = ""
        bytes = 0
        for b in data:
            buf = buf + "%02X" % b
            bytes += 1
            if bytes >= 16:
                buf += "\n"
                bytes = 0

        return buf


#----------------------------------------------------------------
# Support Functions
#----------------------------------------------------------------

def _get_filetype( filename ):
    """Returns "srecord", "hex", "intelhex", "binary", or None"""
    # m = re.search(".*\\.(.+)$", filename , re.S)
    # if m:
        # ext = m.group(1).lower()
    ext = os.path.splitext(filename)[1]
    if ext == ".s19":
        return "srecord"
    elif ext == ".bin":
        return "binary"
    elif ext == ".hex":
        # Hex can be raw hex or Interl hex. Take a look to find out.
        src = open( filename, 'r' )
        line = src.readline()
        src.close()
        if line[0] == ':':
            # Intel
            return "intelhex"
        else:
            return "hex"
    elif ext == ".ihex":
        return "intelhex"

    # TODO: implement this!
    # If we get here, need to look at the file contents to try and tell
    src = open( filename, 'r' )
    line = src.readline()
    src.close()

    return None


def _import_hex( filename ):
    """Returns a byte array of the files contents"""
    bb = bytearray()

    src = open( filename, 'r' )
    lines = src.readlines()
    src.close()

    for line in lines:
        line = line.strip()
        if len(line) == 0 or line[0] == '#':
            continue
        m = re.findall( r'([a-fA-F0-9][a-fA-F0-9])', line )
        for num in m:
            b = int( num, 16 )
            bb.append( b )
    
    return bb
    
    


def scanfile( filename ):
    """ Reads a hex file
    
    Valid file formats are Intel Hex, Motorola S-Records, Binary, and Raw Hex.
    
    Returns a tuple of file type, start address, end address, length, list of chunks, hexdump.
    The file type is a string: "srecord", "hex", "intelhex", "binary"
    Each chunk in the list is a tuple of start address, end address, and length
    """
    # Step 1, what kind of file?
    ftype = _get_filetype( filename )
    
    # Step 2, read the file into the BinFile
    binfile = bincopy.BinFile()
    
    if ftype == "srecord":
        binfile.add_srec_file( filename )
    elif ftype == "binary":
        binfile.add_binary_file( filename )
    elif ftype == "intelhex":
        binfile.add_ihex_file( filename  )
    elif ftype == "hex":
        bb = _import_hex( filename )
        binfile.add_binary( bb )    
    else:
        raise Error( "Unknown file type for %s" % filename )
        
    # Step 3, Iterate through the BinFile creating the chunk list
    chunks = []
    for addr,data in binfile.segments:
        sl = len(data)
        ss = addr
        se = ss + sl - 1
        chunk = ( ss, se, sl )
        chunks.append(chunk)
    
    astart = binfile.minimum_address
    aend = binfile.maximum_address - 1
    alen = aend - astart + 1
    
    hd = binfile.as_hexdump()
        
    return ( ftype, astart, aend, alen, chunks, hd )



#----------------------------------------------------------------
# Main (Unit Tests)
#----------------------------------------------------------------

def main( argv ):
    """This just does some simple unit testing"""
    
    print("A 16-byte EPROM image with 2 bytes starting at 0x0006")
    eprom = EPROM(16)
    print(eprom)
    eprom.add_bytes( 6, b'ab' )
    print(eprom)
    print( eprom.as_hexdump() )

    print( "------------------------------------------------")
    print("bitload.hex (Intel) in 512 byte EPROM image with 2 bytes added at 0x0100")    
    eprom = EPROM(512)
    eprom.readfile( "epromimage-samples/bitload.hex" )
    eprom.add_bytes( 256, b'ab' )
    print(eprom)
    print( eprom.as_hexdump() )
    print()
    for ch in eprom.chunks():
        print(ch)

    print( "------------------------------------------------")
    print("echo.hex (Raw) in 512 byte EPROM image")
    eprom = EPROM(512)
    eprom.readfile( "epromimage-samples/echo.hex" )
    print(eprom)
    print( eprom.as_hexdump() )
    print()
    for ch in eprom.chunks():
        print(ch)

    print( "------------------------------------------------")
    print("Idiot.hex (Intel) with an offset of 0x8000")
    eprom = EPROM(0x1000,0x8000)
    ftype, astart, aend, alen, chunks, __  = scanfile( "epromimage-samples/idiot.hex" )
    print( "Scanfile  File type: %s  Astart: %d  Aend: %d  Len: %d  Chunk count: %d" % (ftype, astart, aend, alen, len(chunks)) )
    eprom.readfile( "epromimage-samples/idiot.hex" )
    print(eprom)
    print( eprom.as_hexdump() )
    print()
    for ch in eprom.chunks():
        print(ch)


    print( "------------------------------------------------")
    print( "FIG-FORTH 1.0 file (Motorola) loaded into an EPROM and dumped.")
    eprom = EPROM(0x2000)
    eprom.readfile( "epromimage-samples/FIG-FORTH 1.0.s19" )
    # eprom.readfile( "/Users/don/Downloads/FIG-FORTH v1.6.hex" )
    print(eprom)
    # print( eprom.as_hexdump() )
    print()
    # for ch in eprom.chunks():
    #     print(ch)

    print( "------------------------------------------------")
    print("Two separate chunks in 512 byte EPROM image")
    eprom = EPROM(512)
    eprom.add_bytes( 0, b'ab' )
    eprom.add_bytes( 0x20, b'xyz' )
    print(eprom)
    print( eprom.as_hexdump() )
    eprom.write_file_as_intel_hex( "epromimage-test-out.ihex")
    eprom.write_file_as_srecords( "epromimage-test-out.s19")



if __name__ == '__main__':
    sys.exit( main(sys.argv) or 0 )
