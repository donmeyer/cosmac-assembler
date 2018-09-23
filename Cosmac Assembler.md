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

## Assembler Syntax


### Comments

Comments are indicated by two consecutive periods.

    .. I am a comment


In the alternate syntax mode, comments are begun with a semicolon.

    ; Alternate comment!



