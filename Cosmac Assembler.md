# Don's Cosmac Assembler



The output of the assembler is a hex file and a listing file.

By default the hex file is in a raw hex format.



    Usage: "cosmacasm.py [options] <file>
        File is assembly source.

    Options:
    -h, --help            show this help message and exit
    -a, --altsyntax       Alternate assembler syntax (; for comments)
    -s SIZE, --size=SIZE  Maximum size of output. Error if this size is
                            exceeded. (optional)
    -d, --display         Display output on terminal. No files are produced.
    -n, --noaction        Simulate the action
    -q, --quiet           quiet
    -v, --verbose         verbose [default]
    --noisy               noisy


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
