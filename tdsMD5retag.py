#!/usr/bin/env python
#
# (Python version of my original bash script...)
#
# NOTE: tds=TimeDateStamp, my term for the yyyymmddhhmmss form.
#
# A filename in tds.md5 form looks like this:
#
#    yyyymmddhhmmss.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#
# ...where the x's represent the 32 hex digits of that file's MD5 sum.
#
# This script assumes that its commandline [or, alternatively, that
# its stdin, one per line] is a list of filenames in tds.md5 form and
# then, for each file in the list:
#
#  - Verifies that the file(s) in question actually exist
#
#  - Computes an MD5 digest for the file and verifies that it agrees
#    with what's represented in the MD5 portion of the filename, renaming
#    the file if necessary
#
#  - Ensures that the mtime/atime of the file's metadata agrees with
#    what's represented in the TDS portion of the filename.
#
# The MD5 portion of a file's name may be changed or its timestamp
# modified but neither the file's contents nor the tds portion of its
# name will ever be changed.
#
# NOTE: For backwards compatibility with previous (ancient, bash-coded)
# versions that didn't care about the MD5 stuff, a filename is permitted
# to be in simple tds form without any MD5 portion; an MD5 sum will
# be calculated and the file renamed to have the new canonical form.
#
# And, yes - I know that MD5 is now regarded as being insecure because
# various obscure flaws and exploits have been discovered, but that's
# not a concern here.  In fact, we would be honored to discover that
# we had one of those corner-cases and would show it off proudly...!
#

###############################################################################
#
import time
import sys
import os
import hashlib
import re
import glob

###############################################################################
# Defend against os.path.dirname's astonishing failure to report '.'  as
# the directory for filenames that have no explicit directory components.
#
def saneDirname( path ) :
    if path == '' :
        return None

    dir = os.path.dirname( path )
    if dir == '' :
        return '.'

    return dir

###############################################################################
# Change the mtime/atime of the specified file in accordance with the
# ymdhms argument which is assumed to be laid out as yyyymmddhhmms.
# Local timezone assumed.
#
def tdsTouch( ymdhms, fileName ) :
    try:
        tds = time.strptime(ymdhms, '%Y%m%d%H%M%S')
    except ValueError:
        sys.stderr.write("timestamp '%s' not in tds form(yyyymmddhhmmss)\n" % ymdhms)
        return False

    if not os.path.isfile(fileName) :
        sys.stderr.write("fileName '%s' invalid", fileName)
        return False

    epochSeconds = int(time.mktime(tds))

    try:                                 # Attempt 'touch' of specified file...
        os.utime(fileName, (epochSeconds, epochSeconds))
    except OSError as (errno, strerror):
        sys.stderr.write("Can't update %s(error:%s)\n" % (fileName, strerror) )
        return False

    return True

###############################################################################
#
def md5stringForFile( fileName ) :
    try :
        fd = open(fileName, "rb")
    except :
        sys.stderr.write( "Can't open '%s' in '%s' ?\n" % (fileName, os.getcwd() ) )
        return False

    m = hashlib.md5()
    m.update( fd.read() )
    return m.hexdigest()             # Hex representation of file's MD5 digest.

###############################################################################
#
def tdsMD5retagFunc( fileName ) :

    # Extract from the specified pathname the directory where
    # the specified file resides and attempt to stand there.
    #
    dir = saneDirname( fileName )                       # os.path.dirname() bug
    if not os.path.isdir( dir ) :
        sys.stderr.write( "No dir '%s' for file '%s' ?\n" % (dir, fileName) )
        return False

    try:
        os.chdir( dir )
    except ValueError:
        sys.stderr.write( "Can't chdir(%s) for '%s' ?\n" % (dir, fileName) )
        return False

    base = os.path.basename( fileName )
    if not os.path.isfile( base ) :
        sys.stderr.write( "No file '%s' for file '%s' in dir '%s' ?\n" % (base, fileName, dir) )
        return False

    # We require that the filename be laid out in tds.md5 format:
    #    yyyymmddhhmmss.md5xmd5xmd5xmd5xmd5xmd5xmd5xmd5x
    # ...specifying Year/Month/Day/Hour/Minute/Second followed
    # by the 32 hex characters of its MD5 sum.  For historical
    # purposes we allow filenames without the MD5 info, in which
    # case we contrive some temporary fake MD5 characters
    # and rename the file prior to recomputing the actual MD5 sum.
    #
    p = re.compile( '([0-9]{14})\.([0-9A-Fa-f]{32})$')
    m = p.match(base)
    if not m :
        p = re.compile( '([0-9]{14})()$')  # Legitimize refs to NULL 2nd group.
        m = p.match(base)
        if not m :
            sys.stderr.write( "Filename '%s' in dir '%s' not in tds.md5 (or even in old tds format)\n" % (base, dir) )
            return False

    # fileName in acceptable form, so isolate the TDS portion.
    #
    tds = m.group( 1 )

    # Existence of multiple files with same TDS not a good sign...
    # XXX_MIKE: To-Do - maybe offer a no-clobber option?
    #
    l = glob.glob( tds + '*' )
    if len(l) != 1 :
        sys.stderr.write( "Warning: multiple files with TDS %s in %s\n" % (tds, dir) )

    md5 = md5stringForFile(base)     # Hex representation of file's MD5 digest.
    if not md5 :
        return False

    proposed = tds + '.' + md5     # Now we know what the file SHOULD be named.

    if base != proposed :                               # Do we have to rename?
        if os.path.isfile( proposed ) :      # File already exists w/this name?
            md5p = md5stringForFile( proposed )
            if not md5p :
                return False
            if md5 == md5p :                 # Duplicate files, OK to toss one.
                sys.stderr.write( "%s has duplicate(%s) in '%s' = deleting\n" % (base, proposed, dir) )
                os.remove( proposed )
            else :                                            # Name collision.
                sys.stderr.write( "%s collides with mistagged %s in %s\n" % (base, proposed, dir) )
                return False

        try :
            os.rename( base, proposed )
        except:
            sys.stderr.write( "Can't rename '%s' as '%s' in '%s' ?\n" % (base, proposed, dir) )
            return False

    # OK - file now exists with correct name.  Force timestamp...
    #
    if not tdsTouch( tds, proposed ) :
        sys.stderr.write( "Can't tdsTouch(%s, %s) in %s ?\n" % (tds, proposed, dir) )
        return False

    if base != proposed :                        # Mention new name if changed.
        print "%s: %s -> %s" % (tds, m.group( 2 ), md5)

    return True

###############################################################################
# Functions defined, commence execution...
#
startDir = os.getcwd()

i = 1
while i < len(sys.argv) :
    os.chdir(startDir)     # Evaluate relative pathnames in the proper context.
    f = sys.argv[i]
    tdsMD5retagFunc(f.strip())
    i += 1

#for f in sys.stdin.readlines() :
#    os.chdir(startDir)    # Evaluate relative pathnames in the proper context.
#    tdsMD5retagFunc(f.strip())

exit(0)

