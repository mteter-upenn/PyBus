#!/usr/bin/python3

import time
import select
import socket
import argparse
import csv
import os
import serial
import serial.tools.list_ports
# import sys
from mbpy import mbcrc  # from folder import file
from struct import pack, unpack
from datetime import datetime


# bandwidth checks for input variables:
def dev_bw(x):
    x = int(x)
    if x < 1 or x > 255:
        raise argparse.ArgumentTypeError("Device ID must be between [1, 255].")
    return x


def srt_bw(x):
    x = int(x)
    if x < 0 or x > 99990:
        raise argparse.ArgumentTypeError("Starting address must be in [0, 9999].")
    return x


def len_bw(x):
    x = int(x)
    if x < 1 or x > 9999:
        raise argparse.ArgumentTypeError("Length of addresses must be in [1, 9999].")
    return x


def wrt_bw(x):
    x = int(x)
    if x != (x & 0xFFFF):
        raise argparse.ArgumentTypeError('Value to write must be in [0, 65535]')
    return x


def to_bw(x):
    x = int(x)
    if x < 1 or x > 10000:
        raise argparse.ArgumentTypeError("Timeout should be less than 10000 ms.")
    return x


def fun_bw(x):
    x = int(x)
    if x not in (1, 2, 3, 4, 5, 6, 16):  # still need to add reading coils
        raise argparse.ArgumentTypeError("ILLEGAL MODBUS FUNCTION")
    return x


def printfunc(verb, i, rws, flg_lp, validi, pbl, p, opt='', msg=0):  # prints error messages and progress bar
    if verb is not None:
        if opt == 'to':
            print('Poll', i, 'timed out.', '\n'*rws, end='')
        elif opt == 'err':
            print('Modbus', msg, 'error', '\n'*rws, end='')
        elif opt == 'crc':
            print('CRC does not match for poll', i, ', transmission failure.', '\n'*rws, end='')

        if verb in (3, 4):
            if verb == 3:
                print('\x1b[2K', end='')

            if flg_lp:
                print('(', validi, ' / ', i, ')', sep='', end='\r')
            else:
                print('[', '='*((i*pbl)//p), ' '*(pbl - ((i*pbl)//p)), '] (', (i*100)//p, '%) (',
                      validi, ' / ', i, ')', sep='', end='\r')

            if verb == 4:
                print()


class ModbusData:
    def __init__(self, strt, lgth, bs, ws, pr, dtype, func):
        self.func = func

        if self.func == 1:
            self.strt = strt
        elif self.func in (2, 5):
            self.strt = strt + 10000
        elif self.func in (3, 6):
            self.strt = strt + 40000
        elif self.func == 4:
            self.strt = strt + 30000
        else:
            self.strt = strt

        self.lgth = lgth
        self.bs = bs
        self.ws = ws
        self.pr = pr
        self.dtype = dtype
        # self.pckt = []
        self.valarr = []

    def translate(self, pckt):
        # self.pckt = pckt
        self.valarr = []
        # self.pckt = []

        self.reg(pckt)

    def reg(self, pckt):
        i = self.strt
        regs = []

        if self.func in (1, 2):
            for bitCoils in pckt:
                for j in range(8):
                    self.valarr.append((bitCoils >> j) & 0x1)

                    if self.pr is not None:
                        if self.pr in (1, 3):
                            print('\x1b[2K', end='\r')
                        print(i, ":", self.valarr[-1])
                    i += 1
                    if i >= self.lgth + self.strt:
                        return

        if self.bs:
            pckt[::2], pckt[1::2] = pckt[1::2], pckt[::2]

        for bth, btl in zip(pckt[::2], pckt[1::2]):
            regs.append((bth << 8) | btl)

        if self.func in (5, 6):
            self.valarr = regs

            if self.pr is not None:
                if self.pr in (1, 3):
                    print('\x1b[2K', end='\r')
                print('Wrote', self.strt, ":", self.valarr[-1])
            return

        if self.dtype in one_byte_formats:  # ('uint8', 'sint8'):
            for r0 in regs:
                if self.dtype == 'uint8':
                    self.valarr.append(r0 >> 8)
                    self.valarr.append(r0 & 0xff)
                elif self.dtype == 'sint8':
                    self.valarr.append(unpack('b', pack('B', (r0 >> 8)))[0])
                    self.valarr.append(unpack('b', pack('B', (r0 & 0xff)))[0])

                if self.pr is not None:
                    if self.pr in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(i, "  :", self.valarr[-2])
                    print(i + .5, ":", self.valarr[-1])
                    i += 1
        elif self.dtype in two_byte_formats:      # ('bin', 'hex', 'ascii', 'uint16', 'sint16', 'sm1k16', 'sm10k16'):
            for r0 in regs:  # , self.pckt[2::4], self.pckt[3::4]):
                if self.dtype == 'bin':
                    # self.valarr.append(bin(r0))
                    self.valarr.append(r0)
                elif self.dtype == 'hex':
                    self.valarr.append(r0)
                elif self.dtype == 'ascii':
                    b1 = bytes([r0 >> 8])
                    b0 = bytes([r0 & 0xff])
                    # b1 = bytes([56])
                    # b0 = bytes([70])
                    self.valarr.append(b1.decode('ascii', 'ignore') + b0.decode('ascii', 'ignore'))
                    # self.valarr.append(chr(b1) + chr(b0))
                elif self.dtype == 'uint16':
                    self.valarr.append(r0)
                elif self.dtype == 'sint16':
                    self.valarr.append(unpack('h', pack('H', r0))[0])
                elif self.dtype in ('sm1k16', 'sm10k16'):
                    if r0 >> 15 == 1:
                        mplr = -1
                    else:
                        mplr = 1

                    self.valarr.append((r0 & 0x7fff) * mplr)

                if self.pr is not None:
                    if self.pr in (1, 3):
                        print('\x1b[2K', end='\r')
                    if self.dtype == 'bin':
                        # print(i, ":", format(self.valarr[-1], '#018b'))
                        print(i, ": 0b", format((self.valarr[-1] >> 8) & 0xff, '08b'),
                              format(self.valarr[-1] & 0xff, '08b'))
                        self.valarr[-1] = bin(self.valarr[-1])
                    elif self.dtype == 'hex':
                        print(i, ":", format(self.valarr[-1], '#06x'))
                        self.valarr[-1] = hex(self.valarr[-1])
                    else:
                        print(i, ":", self.valarr[-1])
                    i += 1
        elif self.dtype in four_byte_formats:  # ('float', 'uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32','sm10k32'):
            if self.ws:
                regs[::2], regs[1::2] = regs[1::2], regs[::2]

            for r0, r1 in zip(regs[::2], regs[1::2]):  # , self.pckt[2::4], self.pckt[3::4]):
                if self.dtype == 'uint32':
                    self.valarr.append((r1 << 16) | r0)
                elif self.dtype == 'sint32':
                    self.valarr.append(unpack('i', pack('I', (r1 << 16) | r0))[0])
                elif self.dtype == 'float':
                    self.valarr.append(unpack('f', pack('I', (r1 << 16) | r0))[0])
                elif self.dtype == 'um1k32':
                    self.valarr.append(r1 * 1000 + r0)
                elif self.dtype == 'sm1k32':
                    if (r1 >> 15) == 1:
                        r1 = (r1 & 0x7fff)
                        self.valarr.append((-1) * (r1 * 1000 + r0))
                    else:
                        self.valarr.append(r1 * 1000 + r0)
                elif self.dtype == 'um10k32':
                    self.valarr.append(r1 * 10000 + r0)
                elif self.dtype == 'sm10k32':
                    if (r1 >> 15) == 1:
                        r1 = (r1 & 0x7fff)
                        self.valarr.append((-1) * (r1 * 10000 + r0))
                    else:
                        self.valarr.append(r1 * 10000 + r0)

                if self.pr is not None:
                    if self.pr in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(i, ":", self.valarr[-1])
                    i += 2
        elif self.dtype in six_byte_formats:  # ('uint48', 'sint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48'):
            if self.ws:
                regs[::3], regs[2::3] = regs[2:3], regs[::3]

            for r0, r1, r2 in zip(regs[::3], regs[1::3], regs[2::3]):
                if self.dtype == 'uint48':
                    self.valarr.append((r2 << 32) | (r1 << 16) | r0)
                elif self.dtype == 'sint48':
                    pass
                    #self.valarr.append(unpack('uintle:48', pack('uintle:48', (r2 << 32) | (r1 << 16) | r0))[0])
                    #self.valarr.append(unpack('q', pack('Q', (0 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])
                elif self.dtype == 'um1k48':
                    self.valarr.append((r2 * (10 ** 6)) + (r1 * 1000) + r0)
                elif self.dtype == 'sm1k48':
                    if (r2 >> 15) == 1:
                        r2 = (r2 & 0x7fff)
                        self.valarr.append((-1) * ((r2 * (10**6)) + (r1 * 1000) + r0))
                    else:
                        self.valarr.append((r2 * (10**6)) + (r1 * 1000) + r0)
                elif self.dtype == 'um10k48':
                    self.valarr.append((r2 * (10**8)) + (r1 * 10000) + r0)
                elif self.dtype == 'sm10k48':
                    if (r2 >> 15) == 1:
                        r2 = (r2 & 0x7fff)
                        self.valarr.append((-1) * ((r2 * (10**8)) + (r1 * 10000) + r0))
                    else:
                        self.valarr.append((r2 * (10**8)) + (r1 * 10000) + r0)

                if self.pr is not None:
                    if self.pr in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(i, ":", self.valarr[-1])
                    i += 2
        else:  # ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'engy', 'dbl')
            if self.ws:
                regs[::4], regs[1::4], regs[2::4], regs[3::4] = regs[3::4], regs[2::4], regs[1::4], regs[::4]

            for r0, r1, r2, r3 in zip(regs[::4], regs[1::4], regs[2::4], regs[3::4]):
                if self.dtype == 'uint64':
                    self.valarr.append((r3 << 48) | (r2 << 32) | (r1 << 16) | r0)
                elif self.dtype == 'sint64':
                    self.valarr.append(unpack('q', pack('Q', (r3 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])
                elif self.dtype == 'um1k64':
                    self.valarr.append(r3 * (10 ** 9) + r2 * (10 ** 6) + r1 * 1000 + r0)
                elif self.dtype == 'sm1k64':
                    if (r3 >> 15) == 1:
                        r3 = (r3 & 0x7fff)
                        self.valarr.append((-1) * (r3 * (10 ** 9) + r2 * (10 ** 6) + r1 * 1000 + r0))
                    else:
                        self.valarr.append(r3 * (10 ** 9) + r2 * (10 ** 6) + r1 * 1000 + r0)
                elif self.dtype == 'um10k64':
                    self.valarr.append(r3 * (10 ** 12) + r2 * (10 ** 8) + r1 * 10000 + r0)
                elif self.dtype == 'sm10k64':
                    if (r3 >> 15) == 1:
                        r3 = (r3 & 0x7fff)
                        self.valarr.append((-1) * (r3 * (10 ** 12) + r2 * (10 ** 8) + r1 * 10000 + r0))
                    else:
                        self.valarr.append(r3 * (10 ** 12) + r2 * (10 ** 8) + r1 * 10000 + r0)
                elif self.dtype == 'engy':
                    # split r3 into engineering and mantissa bytes THIS WILL NOT HANDLE MANTISSA - DOCUMENTATION DOES
                    # NOT EXIST ON HOW TO HANDLE IT WITH THEIR UNITS

                    engr = unpack('b', pack('B', (r3 >> 8)))[0]
                    self.valarr.append(((r2 << 32) | (r1 << 16) | r0) * (10 ** engr))
                elif self.dtype == 'dbl':
                    self.valarr.append(unpack('d', pack('Q', (r3 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])

                if self.pr is not None:
                    if self.pr in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(i, ":", self.valarr[-1])
                    i += 4

    def dttm(self):
        self.valarr.insert(0, str(datetime.now()))


# list of type options
one_byte_formats = ('uint8', 'sint8')
two_byte_formats = ('uint16', 'sint16', 'sm1k16', 'sm10k16', 'bin', 'hex', 'ascii')
four_byte_formats = ('uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32', 'float')
six_byte_formats = ('uint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48')  # 'sint48' is not supported
eight_byte_formats = ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'dbl', 'engy')
# type_lst = ('bin', 'hex', 'ascii','uint8', 'sint8',
#             'uint16', 'sint16', 'uint32', 'sint32', 'uint48', 'sint48', 'uint64', 'sint64',
#             'sm1k16', 'um1k32', 'sm1k32', 'um1k48', 'sm1k48', 'um1k64', 'sm1k64',
#             'sm10k16', 'um10k32', 'sm10k32', 'um10k48', 'sm10k48', 'um10k64', 'sm10k64',
#             'float', 'dbl', 'engy')
type_lst = one_byte_formats + two_byte_formats + four_byte_formats + six_byte_formats + eight_byte_formats

# set flag to determine if from commandline or called function
flg_cl = False

# list possible errors
mberrs = {1: ('Err', 1, 'ILLEGAL FUNCTION'), 2: ('Err', 2, 'ILLEGAL DATA ADDRESS'),
          3: ('Err', 3, 'ILLEGAL DATA VALUE'), 4: ('Err', 4, 'SLAVE DEVICE FAILURE'), 5: ('Err', 5, 'ACKNOWLEDGE'),
          6: ('Err', 6, 'SLAVE DEVICE BUSY'), 7: ('Err', 7, 'NEGATIVE ACKNOWLEDGE'),
          8: ('Err', 8, 'MEMORY PARITY ERROR'), 10: ('Err', 10, 'GATEWAY PATH UNAVAILABLE'),
          11: ('Err', 11, 'GATEWAY TARGET DEVICE FAILED TO RESPOND'), 19: ('Err', 19, 'UNABLE TO MAKE TCP CONNECTION'),
          87: ('Err', 87, 'COMM ERROR'), 101: ('Err', 101, 'INVALID IP ADDRESS OR COM PORT'),
          102: ('Err', 102, 'INVALID DATA TYPE'), 103: ('Err', 103, 'INVALID REGISTER LOOKUP'),
          104: ('Err', 104, 'INVALID FILE NAME'), 105: ('Err', 105, 'UNABLE TO ACCESS CSV FILE'),
          106: ('Err', 106, 'UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER'),
          107: ('Err', 107, 'KEYBOARD INTERRUPT'), 108: ('Err', 108, 'UNEXPECTED TCP MESSAGE LENGTH'),
          109: ('Err', 109, 'UNEXPECTED MODBUS MESSAGE LENGTH'),
          110: ('Err', 110, 'UNEXPECTED MODBUS FUNCTION RETURNED'),
          111: ('Err', 111, 'UNEXPECTED MODBUS SLAVE DEVICE MESSAGE'),
          112: ('Err', 112, 'MULTIPLE POLLS FOR WRITE COMMAND'),
          113: ('Err', 113, 'CRC INCORRECT, DATA TRANSMISSION FAILURE'),
          224: ('Err', 224, 'GATEWAY: INVALID SLAVE ID'),
          225: ('Err', 225, 'GATEWAY: RETURNED FUNCTION DOES NOT MATCH'),
          226: ('Err', 226, 'GATEWAY: GATEWAY TIMEOUT'),
          227: ('Err', 227, 'GATEWAY: INVALID CRC'),
          228: ('Err', 228, 'GATEWAY: INVALID CLIENT')}  # ? don't know what i was thinking


# run script
def mb_poll(ip, dev, strt, lng, h=False, p=1, t='float', bs=False, ws=False, zbased=False, mb_to=1500, filename=None,
            verb=None, port=502, pdelay=1000, func=3):

    if h:
        print('Polls a modbus device through network.',
              '\nip:       The IP address of the gateway or the com port (comX)',
              '\ndev:      The id number of the desired device.',
              '\nstrt:     The address of the first register desired.',
              '\nlng:      The number of outputs to return (certain types will use 2 or 4 registers per output).',
              '\np:        The number of polls. Default is 1.',
              '\nt:        The desired type to be returned.',
              '\nbs:       Sets byteswap to true.  Default is Big Endian (False).',
              '\nws:       Sets wordswap to true.  Default is Little Endian (False).',
              '\nzbased:   Interprets starting address as 0-based value.  If not set then',
              '\n            setting srt=2 looks at 1 (second register).  If set then setting',
              '\n            srt=2 looks at 2 (third register) (Default is 1, else 0).',
              '\nmb_to:    Time in milliseconds to wait for reply message. Default is 1500.'
              '\nfilename: Generates csv file in current folder.',
              '\nverb:     Verbosity options. 1: Static display  2: Consecutive display  3: Static + progress bar '
              '\n              4: Consecutive + progress bar',
              '\nport      Set port to communicate over.  Default is 502.'
              '\npdelay    Delay in ms to let function sleep to retrieve reasonable data.  Default is 1000.')
        return

    cmpt = None
    wrt = None

    # ~ check that ip is valid
    if type(ip) == str:
        iparr = ip.split(".")

        if len(iparr) != 4:
            if len(iparr) == 1:
                comports = list(serial.tools.list_ports.comports())
                ip = ip.upper()

                for ports in comports:
                    if ip == ports[0]:
                        cmpt = int(ip[3:]) - 1
                        # print('cmpt', cmpt)
                        break
                else:
                    return mberrs[101]
            else:
                return mberrs[101]  # raise ValueError('Invalid IP address!')
        else:
            for ch in iparr:
                if int(ch) > 255 or int(ch) < 0:
                    return mberrs[101]  # raise ValueError('Invalid IP address!')

    # check certain things if called through script rather than commandline
    if not flg_cl:
        # check if device in correct interval
        dev = dev_bw(dev)

        # check if strt in correct interval
        strt = srt_bw(strt)

        mb_to = to_bw(mb_to)

        # check if type is part of allowable functions
        if t not in type_lst:
            return mberrs[102]  # raise ValueError('Please choose type from list: ' + str(type_lst))

        port = int(port)

        func = fun_bw(func)
        # if func not in (3, 4):
        #     return mberrs[1]  # illegal modbus function

    mb_to = mb_to / 1000  # convert from ms to s

    if func in (5, 6, 16):
        writemb = True
        pdelay = 0
    else:
        writemb = False
        # if pdelay == -1:
        #     if p == 1:
        #         pdelay = 0  # default delay for single poll
        #     else:
        #         pdelay = 1000  # default delay for multiple polls

        # pdelay = float(pdelay)

    # change lng to check for the requested number of registers
    if writemb:  # write to register/coil
        wrt = wrt_bw(lng)
        ret_lng = 8
    else:
        lng = len_bw(lng)  # check if lng is in correct interval

        if func in (1, 2):
            pass
        elif t in four_byte_formats:  # ('float', 'uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32'):
            lng *= 2
        elif t in six_byte_formats:  # ('uint48', 'sint48'):
            lng *= 3
        elif t in eight_byte_formats:  # ('mod30k', 'uint64', 'engy', 'dbl'):
            lng *= 4
        elif t in one_byte_formats:  # ('uint8', 'sint8'):
            lng = (lng + 1) // 2
        else:
            pass  # for single register formats

        if func in (1, 2):
            ret_lng = 5 + ((lng + 7) // 8)  # number of bytes converted from number of bits
        else:
            ret_lng = 5 + lng * 2  # number of bytes expected in return for com port

    # check if zero based and starting register will work
    strtz = strt - (not zbased)

    if strtz < 0:
        return mberrs[103]  # raise ValueError('Invalid register lookup.')

    # check if infinite polling
    if p != 1 and writemb:
        return mberrs[112]  # shouldn't have multiple polls for a write command
    else:
        if p < 1:  # poll forever
            print('Ctrl-C to exit.')
            flg_lp = True
            p = 1
        elif p == 1:  # single poll
            # pdelay = 0
            flg_lp = False
        else:  # multiple polls
            flg_lp = False

    # check filename for validity
    if filename is not None:
        farr = filename.split(".")

        if len(farr) == 1:
            fname = filename + '.csv'
        elif len(farr) == 2:
            fname = farr[0] + '.csv'
        else:
            return mberrs[104]
            # raise ValueError('Inappropriate name for file.')
    else:
        fname = None

    # check os to determine if there will be a problem with different print options
    if verb in (1, 3):
        if os.name == 'nt':  # if static print is called, this can't be implemented in windows, give other options
            if not flg_cl:
                verb = None  # not called from commandline, no guarantee to respond to input
            else:
                while verb in (1, 3):
                    verb = int(input('Please choose from [0, 2, 4] (blank, consecutive, cons + progress bar): '))

                if verb == 0:
                    verb = None
        else:
            if func in (1, 2):
                rws = lng + 1
            elif t in one_byte_formats:  # ('uint8', 'sint8'):
                rws = lng * 2 + 1
            elif t in two_byte_formats:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
                rws = lng + 1
            elif t in four_byte_formats:  # ('uint32', 'sint32', 'float', 'mod1k', 'mod10k'):
                rws = int(lng / 2 + 1)
            elif t in six_byte_formats:  # 'mod20k':
                rws = int(lng / 3 + 1)
            else:  # in eight_byte_formats:  # ('uint64', 'mod30k', 'engy', 'dbl')
                rws = int(lng / 4 + 1)
            print('\n'*(rws + 1), end='')
    else:
        rws = 2

    # set value for length of progress bar
    if verb in (3, 4):
        if os.name == 'nt':
            pbl = 65 - (2 * len(str(p)))  # 65 = 80 - 15
        else:
            rows, columns = os.popen('stty size', 'r').read().split()  # determine size of terminal
            pbl = int(columns) - 15 - (2 * len(str(p)))
    else:
        pbl = 0

    # vallst = 0
    mbdata = ModbusData(strt, lng, bs, ws, verb, t, func)

    if filename is not None:
        try:
            csvfile = open(fname, 'w', newline='')
        except IOError:
            return mberrs[105]
        else:
            fwriter = csv.writer(csvfile)
            if func in (1, 2):
                hdr = range(strtz, strtz + lng)
            elif t in one_byte_formats:  # ('uint8', 'sint8'):
                hdr = [x / 2 + strtz for x in range(0, lng * 2)]  # should work
            elif t in two_byte_formats:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
                hdr = range(strtz, strtz + lng)
            elif t in four_byte_formats:  # ('uint32', 'sint32', 'float', 'mod1k', 'mod10k'):
                hdr = range(strtz, strtz + lng)[::2]
            elif t in six_byte_formats:  # 'mod20k':
                hdr = range(strtz, strtz + lng)[::3]
            else:  # ('uint64', 'mod30k', 'engy', 'dbl')
                hdr = range(strtz, strtz + lng)[::4]
            hdr = list(hdr)
            hdr.insert(0, None)  # shifts columns to make room for dates
            fwriter.writerow(hdr)
    else:
        csvfile = None
        fwriter = None

    # timeout = 1
    # ~ #create packet here:
    if cmpt is not None:  # com port communication
        packet = bytearray(6)
        packet[0] = dev & 0xFF           # device address
        packet[1] = func & 0xFF          # function code
        packet[2] = (strtz >> 8) & 0xFF  # starting register high byte
        packet[3] = strtz & 0xFF         # starting register low byte
        if writemb:
            if func == 5:
                if wrt == 1:
                    packet[4] = 0xFF
                elif wrt == 0:
                    packet[4] = 0x00
                else:
                    return mberrs[3]

                packet[5] = 0x00
            else:
                packet[4] = (wrt >> 8) & 0xFF   # value to write to read high byte
                packet[5] = wrt & 0xFF          # value to write to read low byte

            pcktwrt = list(packet)
        else:
            packet[4] = (lng >> 8) & 0xFF   # starting length to read high byte
            packet[5] = lng & 0xFF          # starting length to read low byte

        packet.extend(mbcrc.calcbytearray(packet))
        # print(list(packet))
    else:  # TCP/IP communication
        if func == 16:
            # packet = bytearray(15)
            packet = bytearray(21)
        else:
            packet = bytearray(12)

        packet[5] = 6 & 0xFF
        packet[6] = dev & 0xFF
        packet[7] = func & 0xFF
        packet[8] = (strtz >> 8) & 0xFF  # HIGH starting register
        packet[9] = strtz & 0xFF  # LOW register
        if writemb:
            if func == 16:
                packet[5] = 15 & 0xFF
                packet[10] = 0 & 0xFF  # HIGH number of registers
                packet[11] = 4 & 0xFF  # LOW number of registers

                packet[12] = 8 & 0xFF  # number of bytes

                packet[13] = (59492 >> 8) & 0xFF  # should be wrt here, currently trying to set modbus map for siemens breaker
                packet[14] = 59492 & 0xFF

                packet[15] = (3 >> 8) & 0xFF
                packet[16] = 3 & 0xFF

                packet[17] = (8 >> 8) & 0xFF
                packet[18] = 8 & 0xFF

                packet[19] = (47368 >> 8) & 0xFF
                packet[20] = 47368 & 0xFF

                # packet[5] = 15 & 0xff
                # packet[10] = 0 & 0xff  # HIGH registers
                # packet[11] = 4 & 0xff
                # packet[12] = 8 & 0xff
                # packet[13] = (49202 >> 8) & 0xff # enter setup
                # packet[14] = 49202 & 0xff # enter setup
                # # packet[13] = (53299 >> 8) & 0xff # exit setup
                # # packet[14] = 53299 & 0xff # exit setup
                # packet[15] = 0
                # packet[16] = 3 & 0xff
                # packet[17] = 0
                # packet[18] = 2 & 0xff
                # packet[19] = (0 >> 8) & 0xff
                # packet[20] = 0 & 0xff

                print(list(packet))
            else:
                packet[10] = (wrt >> 8) & 0xFF
                packet[11] = wrt & 0xFF
                print(list(packet))

            pcktwrt = list(packet[6:])
        else:
            packet[10] = (lng >> 8) & 0xFF
            packet[11] = lng & 0xFF

    ser = None
    # print(list(packet))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
        conn.settimeout(mb_to)

        if cmpt is not None:  # COM port
            ser = serial.Serial(cmpt, timeout=mb_to, baudrate=9600)  # set up serial
        else:
            try:
                # print(port)
                conn.connect((ip, port))

            except socket.timeout:
                if verb is not None:
                    print('Connection could not be made with gateway.  Timed out after 5 seconds.')
                return mberrs[19]
            except socket.error:
                return mberrs[19]

            conn.setblocking(0)
        validi = 0

        i = 1
        skip = False
        # for i in range(1, p + 1):
        while i < p + 1:
            # print(conn)
            try:
                if cmpt is not None:  # COM port
                    ser.write(packet)  # send msg
                else:
                    # clear Rx buffer !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    conn.sendall(packet)  # send modbus request

                if verb in (1, 3):
                    print('\x1b[', rws + 1, 'F\x1b[2K', sep='', end='\r')

                if verb is not None:
                    print('\nPoll', i, 'at:', str(datetime.now()))

                start = time.time()

                if cmpt is not None:  # using com port!
                    packetbt = ser.read(ret_lng)  # need packetbt

                    if packetbt != []:

                        print(list(packetbt))
                        packetrec = list(packetbt[:-2])
                        
                        if mbcrc.calcbytearray(packetrec) != packetbt[-2:]:
                            mbdata.valarr = mberrs[113]

                            skip = True
                            printfunc(verb, i, rws, flg_lp, validi, pbl, p, 'crc')
                    else:
                        mbdata.valarr = mberrs[87]

                        skip = True
                        printfunc(verb, i, rws, flg_lp, validi, pbl, p, 'to')
                else:  # using ethernet!
                    inputs = select.select([conn], [], [], mb_to)[0]  # wait 5 s for conn to receive data in buffer

                    if inputs != []:
                        try:
                            # print('start')
                            packetbt = conn.recv(1024, )  # gives bytes type
                            # print(list(packetbt))
                        except socket.timeout:
                            print('to')
                            mbdata.valarr = mberrs[87]
                            break
                        except socket.error as r:
                            print(r)
                            mbdata.valarr = mberrs[87]
                            break

                        if len(packetbt) > 6:
                            if packetbt[0] >= 0:
                                pr_len = int.from_bytes(packetbt[4:6], byteorder='big')
                                # print(list(packetbt), '\n'*rws, end='')
                                if pr_len == (len(packetbt) - 6):
                                    packetrec = list(packetbt[6:])
                                    # print(packetrec)
                                else:
                                    mbdata.valarr = mberrs[108]  # UNEXPECTED MODBUS MESSAGE LENGTH
                                    try:
                                        print(packetbt.decode('ascii'), '\n'*rws, end='')
                                    except UnicodeDecodeError:
                                        print(list(packetbt), '\n'*rws, end='')
                                    skip = True
                            else:
                                if verb is not None:
                                    try:
                                        print(packetbt.decode('ascii'), '\n'*rws, end='')
                                    except UnicodeDecodeError:
                                        print(list(packetbt), '\n'*rws, end='')
                                mbdata.valarr = mberrs[106]  # UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER
                                break
                        else:  # TCP message <6
                            print('Partial TCP message returned of length', len(packetbt))

                            mbdata.valarr = mberrs[106]  # UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER
                            break
                    else:  # select timed out
                        mbdata.valarr = mberrs[87]
                        skip = True
                        printfunc(verb, i, rws, flg_lp, validi, pbl, p, 'to')

                if not skip:
                    if dev == packetrec[0] or packetrec[0] == 0:  # check modbus device
                        if packetrec[1] == func:  # check modbus function
                            if writemb:  # if write command, will have different checks
                                if pcktwrt == packetrec:
                                    # print('Wrote', wrt, 'to register', strt)
                                    # mbdata.valarr = [wrt]
                                    if func == 6:
                                        mbdata.translate(packetrec[4:])
                                    else:
                                        mbdata.translate((0, wrt))
                                    printfunc(verb, i, rws, flg_lp, validi, pbl, p)
                                else:
                                    print(packetrec)
                                    mbdata.valarr = mberrs[111]
                                    printfunc(verb, i, rws, flg_lp, validi, pbl, p, 'err', 111)
                            else:
                                if packetrec[2] == (len(packetrec) - 3):  # check length of modbus message
                                    # print("correct packet struct returned")
                                    # print(packetbt.decode('ascii'))
                                    mbdata.translate(packetrec[3:])

                                    if fwriter is not None:
                                        mbdata.dttm()
                                        fwriter.writerow(mbdata.valarr)

                                    validi += 1

                                    printfunc(verb, i, rws, flg_lp, validi, pbl, p)

                                else:
                                    mbdata.valarr = mberrs[109]  # UNEXPECTED MODBUS MESSAGE LENGTH
                        elif packetrec[1] == (func + 128) or packetrec[1] == 128:  # check for error return
                            if packetrec[2] in mberrs:
                                mbdata.valarr = mberrs[packetrec[2]]  # MODBUS ERROR RETURNED
                            else:
                                mbdata.valarr = ('Err', packetrec[2], 'UNKNOWN ERROR')

                            printfunc(verb, i, rws, flg_lp, validi, pbl, p, 'err', packetrec[2])
                        else:
                            mbdata.valarr = mberrs[110]  # UNEXPECTED MODBUS FUNCTION RETURNED
                            # print(packetrec)
                    else:
                        mbdata.valarr = mberrs[111]  # UNEXPECTED MODBUS SLAVE DEVICE MESSAGE
                        # print(packetrec)
                else:
                    skip = False

                i += 1
                if flg_lp:
                    p += 1

                # sleep for the rest of poll delay
                if i != p + 1:
                    time.sleep(max(0, start + pdelay / 1000 - time.time()))

            except KeyboardInterrupt:
                if not flg_lp:
                    mbdata.valarr = mberrs[107]
                break
            # end try
        # end while
    # end with

    if verb is not None:
        print()

    if fwriter is not None:
        csvfile.close()

    return mbdata.valarr


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Polls a modbus device through network.')

    parser.add_argument('ip', type=str, help='The IP address of the gateway or the comport (comX).')
    parser.add_argument('dev', type=dev_bw, help='The id number of the desired device.')
    parser.add_argument('srt', type=srt_bw, help='The address of the first register desired.')
    parser.add_argument('lng', type=int,
                        help='The number of registers to return (certain types will use 2 or 4 registers per output).')
    parser.add_argument('-p', '--poll', type=int, default=1, help='The number of polls. Default is 1.')
    parser.add_argument('-t', '--typ', type=str, default='float', choices=type_lst,
                        help='The desired type to be returned')
    parser.add_argument('-bs', '--byteswap', action='store_true', help='Sets byteswap to true.  Default is Big Endian.')
    parser.add_argument('-ws', '--wordswap', action='store_true',
                        help='Sets wordswap to true.  Default is Little Endian.')
    parser.add_argument('-0', '--zbased', action='store_true',
                        help='Interprets starting address as 0-based value.  If not set then setting srt=2 looks at 1 '
                             '(second register).  If set then setting srt=2 looks at 2 (third register).')
    parser.add_argument('-to', '--timeout', type=to_bw, default=1500,
                        help='Time in milliseconds to wait for reply message. Default is 1500.')
    parser.add_argument('-fl', '--file', type=str, help='Generates csv file in current folder.')
    parser.add_argument('-v', '--verbose', action='count',
                        help='Verbosity options. 1: Static display  2: Consecutive display  3: Static + progress bar '
                             '4: Consecutive + progress bar')
    parser.add_argument('-pt', '--port', type=int, default=502, help='Set port to communicate over.  Default is 502.')
    parser.add_argument('-pd', '--pdelay', type=int, default=1000,
                        help='Delay in ms to let function sleep to retrieve reasonable data.  Default is 1000.')
    parser.add_argument('-f', '--func', type=fun_bw, default=3,
                        help='Modbus function.  Only 3, 4, 5, and 6 are supported.')

    args = parser.parse_args()

    flg_cl = True
    testx = mb_poll(args.ip, args.dev, args.srt, args.lng, p=args.poll, t=args.typ, bs=args.byteswap, ws=args.wordswap,
                    zbased=args.zbased, mb_to=args.timeout, filename=args.file, verb=args.verbose, port=args.port,
                    pdelay=args.pdelay, func=args.func)

    print(testx)
