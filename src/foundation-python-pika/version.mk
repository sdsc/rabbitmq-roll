PKGROOT		   = usr
NAME               = foundation-python-pika
VERSION            = 0.10.0
RELEASE            = 0
TARBALL_POSTFIX    = tar.gz

SRC_SUBDIR         = pika

SOURCE_NAME        = pika
SOURCE_VERSION     = $(VERSION)
SOURCE_SUFFIX      = tar.gz
SOURCE_PKG         = $(SOURCE_NAME)-$(SOURCE_VERSION).$(SOURCE_SUFFIX)
SOURCE_DIR         = $(SOURCE_PKG:%.$(SOURCE_SUFFIX)=%)

TAR_GZ_PKGS           = $(SOURCE_PKG)
RPM.FILES	   = $(PY.ROCKS)/*
