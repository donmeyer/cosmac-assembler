#!/bin/sh


../cosmacasm.py test.src

echo ----------------------------------------
echo Testing test hex
cmp --verbose test.hex reference/test.hex

echo ----------------------------------------
echo Testing test listing
cmp --verbose test.lst reference/test.lst

echo
echo Tests completed
