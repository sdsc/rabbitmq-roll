PKGROOT		   = /opt/pycrypto
NAME               = foundation-python-pycrypto
VERSION            = 2.6.1
RELEASE            = 1
TARBALL_POSTFIX    = tar.gz

SRC_SUBDIR         = pycrypto

SOURCE_NAME        = pycrypto
SOURCE_VERSION     = $(VERSION)
SOURCE_SUFFIX      = tar.gz
SOURCE_PKG         = $(SOURCE_NAME)-$(SOURCE_VERSION).$(SOURCE_SUFFIX)
SOURCE_DIR         = $(SOURCE_PKG:%.$(SOURCE_SUFFIX)=%)

TAR_GZ_PKGS           = $(SOURCE_PKG)
