# Don's Cosmac Assembler



The output of the assembler is a hex file and a listing file.

By default the hex file is in a raw hex format.



    Usage: "cosmacasm.py [options] <file>
        File is assembly source.

    Options:
    -h, --help            show this help message and exit
    -a, --altsyntax       Alternate assembler syntax (; for comments)
    -s SIZE, --size=SIZE  Maximum size of output. Error if this size is exceeded. (optional)
    -b BASE, --base=BASE  Base offset of the program image. Default is 0x0000. (optional)
    -d, --display         Display output on terminal. No files are produced.
    -n, --noaction        Simulate the action
    -q, --quiet           quiet
    -v, --verbose         verbose [default]
    --noisy               noisy


### Program Base

For example, if there was an ORG 0100H directive at the start of the program, the emitted hex file would contain 256 0xFF bytes at the start if there was no --base argument used.
If the option --base=0x100 is used, the hex file will begin with code assembled at address 0x100, and there will be no "padding" before it.

In this scenario, attempting to assemble any code below the address of 0x100 will result in an error.

### Size Limit

The size limit option can be used to cause an error if the resulting code image is too large.

For example, if the program image is intended to fit into a 27C16 EPROM, setting the size limit to 2048 will give an error if the code size overflows.

The program base is taken into account, so the size should be the total size, not the highest address. For example, a base offset of 0x100 and a size limit of 0x100 will result in the highest possible valid address being 0x01FF.

---------------------------------------------------------------------------

# Assembler Syntax

### LOAD Macro

The LOAD macro syntax is "LOAD Rn, <addr>"

Expands to machine language for:
LDI A.1(addr); PHI Rn
LDI A.0(addr); PLO Rn


## Alternate Syntax

### Comments

For comments, it becomes ; versus ..
Comments are indicated by two consecutive periods.

    .. I am a comment

In the alternate syntax mode, comments are begun with a semicolon.

    ; Alternate comment!

### Constants

DC becomes DB.

### Register Bytes

A.0 and A.1 become LOW and HIGH
