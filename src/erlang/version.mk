NAME		= erlang
VERSION		= 18.2
RELEASE		= 1
PKGROOT		= /usr
DIRNAME		= otp_src_$(VERSION)
TARNAME		= $(DIRNAME).tar.gz
RPM.FILES	= \
$(PKGROOT)/bin/*\n\
$(PKGROOT)/lib64/*
