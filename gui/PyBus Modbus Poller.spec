# -*- mode: python -*-

block_cipher = None


a = Analysis(['gui_mbpy.pyw'],
             pathex=['C:\\Users\\mteter\\PyBus\\gui'],
             binaries=[],
             datas=[('./resources/*', 'resources')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='PyBus Modbus Poller',
          debug=False,
          strip=False,
          upx=True,
          console=False , icon='resources\\Upenn16.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='PyBus Modbus Poller')
