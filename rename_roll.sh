#!/bin/bash

# This script replaces all instances of the 'old' name of this roll template with
# a 'new' roll name. It changes file/directory names as well as the contents of
# the files inside this template roll.

usage () {
  echo "$(basename "$0") -n newname [-c curname] [-h] -- program to rename the roll template

where:
    -h  show this help text
    -n  where newname is the new name for the roll
    -c  where curname is the current name of the roll"
}

CURNAME=
NEWNAME=
options='hn:c:'
while getopts $options option
do
  case "$option" in
    c  ) CURNAME=$OPTARG;;
    n  ) NEWNAME=$OPTARG;;
    h  ) usage; exit;;
    \? ) printf "unknown option: -%s\n" "$OPTARG" >&2; usage >&2; exit 1;;
    :  ) printf "missing argument for -%s\n" "$OPTARG" >&2; usage >&2; exit 1;;
    *  ) printf "unimplemented optio: -%s\n" "$OPTARG" >&2; usage >&2; exit 1;;
  esac
done
shift $((OPTIND - 1))

# You 'must' supply a new roll name'
if [[ -z $NEWNAME ]]
then
  usage
  exit 1
fi

# If -c option is not specified determine it from graph file.
if [[ -z $CURNAME ]]
then
  CURNAME=$(basename `ls graphs/default/*.xml` | cut -d. -f1)
fi

echo "Renaming ${CURNAME} roll to ${NEWNAME}"
ROOT=$(pwd)

echo "   Changing directory names..."
DIRS=$(find . -depth -type d | grep $CURNAME)

for d in ${DIRS}
do
  if [ -d ${d} ]; then
    newd=$(echo ${d} | sed "s,\(.*\)"${CURNAME}"\(.*\),\1"${NEWNAME}"\2,g")
    mv ./${d} ./${newd};
  fi
done
cd ${ROOT}

echo "   Changing file names..."
FILES=$(find . -depth -type f | grep ${CURNAME})

for f in ${FILES}
do
  if [ -f ${f} ]; then
    newf=$(echo ${f} | sed "s,"${CURNAME}","${NEWNAME}",g");
    mv ./${f} ./${newf};
  fi
done
cd ${ROOT}

echo "   Changing file contents...."
FILES=`find . -depth -type f | egrep -v "rename_roll.sh"`

for f in ${FILES}
do
  sed -i "s,"${CURNAME}","${NEWNAME}",g" ./${f}
done
cd ${ROOT}

echo "   Removing .git directories..."
DIRS=$(find . -depth -type d -iname ".git")

for d in ${DIRS}
do
  if [ -d ${d} ]; then
    /bin/rm -rf ./${d};
  fi
done
cd ${ROOT}

cat << EOF

The following steps are now required after using ./rename_roll.sh...

  - Download or otherwise create src/${NEWNAME}/${NEWNAME}-1.0.tgz
  - Upload src/${NEWNAME}/${NEWNAME}-1.0.tgz to the DL.SERVER listed in 
    src/${NEWNAME}/pull.mk
  - Record size and git hash of src/${NEWNAME}/${NEWNAME}-1.0.tgz in 
    src/${NEWNAME}/binary_hashes per the instructions in src/${NEWNAME}/README.md

While not required, you should rename this directory ${NEWNAME}-roll to avoid confusion.

EOF

exit 0
