#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Created by: python.exe -m py2exe -W setup.py gui_mbpy.pyw
# Run to create executable: python setup_gui_exe.py py2exe   <-----------------------------------
from distutils.core import setup
import os
import py2exe

class Target(object):
    '''Target is the baseclass for all executables that are created.
    It defines properties that are shared by all of them.
    '''
    def __init__(self, **kw):
        self.__dict__.update(kw)

        # the VersionInfo resource, uncomment and fill in those items
        # that make sense:
        
        # The 'version' attribute MUST be defined, otherwise no versioninfo will be built:
        self.version = "1.1.3"
        
        self.company_name = "University of Pennsylvania FRES"
        # self.copyright = "Copyright Company Name © 2013"
        # self.legal_copyright = "Copyright Company Name © 2013"
        # self.legal_trademark = ""
        self.product_version = "1.1.3"
        self.product_name = "PyBus Modbus Scanner"

        self.private_build = "foo"
        self.special_build = "bar"

    def copy(self):
        return Target(**self.__dict__)

    def __setitem__(self, name, value):
        self.__dict__[name] = value

RT_BITMAP = 2
RT_MANIFEST = 24

# A manifest which specifies the executionlevel
# and windows common-controls library version 6

manifest_template = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity
    version="5.0.0.0"
    processorArchitecture="*"
    name="%(prog)s"
    type="win32"
  />
  <description>%(prog)s</description>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel
            level="%(level)s"
            uiAccess="false">
        </requestedExecutionLevel>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <dependency>
    <dependentAssembly>
        <assemblyIdentity
            type="win32"
            name="Microsoft.Windows.Common-Controls"
            version="6.0.0.0"
            processorArchitecture="*"
            publicKeyToken="6595b64144ccf1df"
            language="*"
        />
    </dependentAssembly>
  </dependency>
</assembly>
'''



gui_mbpy = Target(
    # We can extend or override the VersionInfo of the base class:
    # version = "1.0",
    # file_description = "File Description",
    # comments = "Some Comments",
    # internal_name = "spam",

    script="gui_mbpy.pyw", # path of the main script

    # Allows to specify the basename of the executable, if different from 'gui_mbpy'
    dest_base = "PyBus Modbus Scanner",

    # Icon resources:[(resource_id, path to .ico file), ...]
    # icon_resources=[(1, r"gui_mbpy.ico")]
    # icon_resources = [(1, r"resources/favicon.ico")],
	icon_resources = [(1, r"resources/Upenn16.ico")],
	
    other_resources = [(RT_MANIFEST, 1, (manifest_template % dict(prog="gui_mbpy", level="asInvoker")).encode("utf-8")),
    # for bitmap resources, the first 14 bytes must be skipped when reading the file:
    #                    (RT_BITMAP, 1, open("bitmap.bmp", "rb").read()[14:]),
                      ]
    )


# ``zipfile`` and ``bundle_files`` options explained:
# ===================================================
#
# zipfile is the Python runtime library for your exe/dll-files; it
# contains in a ziparchive the modules needed as compiled bytecode.
#
# If 'zipfile=None' is used, the runtime library is appended to the
# exe/dll-files (which will then grow quite large), otherwise the
# zipfile option should be set to a pathname relative to the exe/dll
# files, and a library-file shared by all executables will be created.
#
# The py2exe runtime *can* use extension module by directly importing
# the from a zip-archive - without the need to unpack them to the file
# system.  The bundle_files option specifies where the extension modules,
# the python dll itself, and other needed dlls are put.
#
# bundle_files == 3:
#     Extension modules, the Python dll and other needed dlls are
#     copied into the directory where the zipfile or the exe/dll files
#     are created, and loaded in the normal way.
#
# bundle_files == 2:
#     Extension modules are put into the library ziparchive and loaded
#     from it directly.
#     The Python dll and any other needed dlls are copied into the
#     directory where the zipfile or the exe/dll files are created,
#     and loaded in the normal way.
#
# bundle_files == 1:
#     Extension modules and the Python dll are put into the zipfile or
#     the exe/dll files, and everything is loaded without unpacking to
#     the file system.  This does not work for some dlls, so use with
#     caution.
#
# bundle_files == 0:
#     Extension modules, the Python dll, and other needed dlls are put
#     into the zipfile or the exe/dll files, and everything is loaded
#     without unpacking to the file system.  This does not work for
#     some dlls, so use with caution.


py2exe_options = dict(
    packages = [],
##    excludes = "tof_specials Tkinter".split(),
##    ignores = "dotblas gnosis.xml.pickle.parsers._cexpat mx.DateTime".split(),
##    dll_excludes = "MSVCP90.dll mswsock.dll powrprof.dll".split(),
    optimize=0,
    compressed=False, # uncompressed may or may not have a faster startup
    bundle_files=2,
    dist_dir='PyBus Modbus Scanner',
    )


# Some options can be overridden by command line options...
icopath = os.getcwd() + '/resources/Upenn16.ico'
mydatafiles = [('resources', [icopath])]

setup(name="name",
      # console based executables
      # console=[gui_mbpy],

      # windows subsystem executables (no console)
      windows=[gui_mbpy],

      # py2exe options
      data_files=mydatafiles,
      zipfile=None,
      options={"py2exe": py2exe_options},
      )

