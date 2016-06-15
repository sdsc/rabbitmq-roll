PKGROOT		   = /opt/paramiko
NAME               = foundation-python-paramiko
VERSION            = 1.8.0
RELEASE            = 1
TARBALL_POSTFIX    = tar.gz

SRC_SUBDIR         = paramiko

SOURCE_NAME        = paramiko
SOURCE_VERSION     = $(VERSION)
SOURCE_SUFFIX      = tar.gz
SOURCE_PKG         = $(SOURCE_NAME)-$(SOURCE_VERSION).$(SOURCE_SUFFIX)
SOURCE_DIR         = $(SOURCE_PKG:%.$(SOURCE_SUFFIX)=%)

TAR_GZ_PKGS           = $(SOURCE_PKG)
