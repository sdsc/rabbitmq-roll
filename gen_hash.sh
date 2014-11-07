#!/bin/bash
# Generates a 'binary_hashes' entry for supplied object(s)

for OBJ in "$@"
do

  OBJ_BASENAME=`basename ${OBJ}`
  OBJ_DIRNAME=`dirname ${OBJ}`

  if [ -f ${OBJ} ]; then
    OBJ_SIZE=`ls -l $OBJ | awk '{print $5}'`
    OBJ_HASH=`git hash-object -t blob $OBJ`
    OBJ_NAME=${OBJ}
    printf "%15d  %40s  %s\n" $OBJ_SIZE $OBJ_HASH $OBJ_NAME
  fi
  
done
