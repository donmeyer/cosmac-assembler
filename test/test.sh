#!/bin/sh


echo Compiling
../cosmacasm.py  --quiet test.src

echo ----------------------------------------
echo Testing test hex
cmp --verbose test.hex reference/test.hex

echo ----------------------------------------
echo Testing test listing
cmp test.lst reference/test.lst


echo ========================================
echo Compiling
../cosmacasm.py  --quiet test_dc.src

echo ----------------------------------------
echo Testing test_dc hex
cmp --verbose test_dc.hex reference/test_dc.hex

echo ----------------------------------------
echo Testing test_dc listing
cmp test_dc.lst reference/test_dc.lst


echo ========================================
echo Compiling
../cosmacasm.py  --quiet test_exp.src

echo ----------------------------------------
echo Testing test_exp hex
cmp --verbose test_exp.hex reference/test_exp.hex

echo ----------------------------------------
echo Testing test_exp listing
cmp test_exp.lst reference/test_exp.lst



echo ========================================
echo Compiling
../cosmacasm.py --quiet FIG_Forth.src

echo ----------------------------------------
echo Testing FIG hex
cmp FIG_Forth.hex reference/FIG_Forth.hex

echo ----------------------------------------
echo Testing FIG listing
cmp FIG_Forth.lst reference/FIG_Forth.lst


echo
echo Tests completed. If no warnings or errors above, then we passed!
