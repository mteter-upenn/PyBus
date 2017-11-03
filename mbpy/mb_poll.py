#!/usr/bin/python3

import time
import select
import socket
import argparse
import csv
import os
import serial
import serial.tools.list_ports
from math import log10
# import sys
from mbpy import mbcrc  # from folder import file
from struct import pack, unpack
from datetime import datetime


# bandwidth checks for input variables:
def device_bw(x):
    x = int(x)
    if x < 1 or x > 255:
        raise argparse.ArgumentTypeError("Device ID must be between [1, 255].")
    return x


def register_bw(x):
    x = int(x)
    if x < 0 or x > 99990:
        raise argparse.ArgumentTypeError("Starting address must be in [0, 9999].")
    return x


def num_regs_bw(x):
    x = int(x)
    if x < 1 or x > 9999:
        raise argparse.ArgumentTypeError("Length of addresses must be in [1, 9999].")
    return x


def write_reg_bw(x):
    x = int(x)
    if x != (x & 0xFFFF):
        raise argparse.ArgumentTypeError('Value to write must be in [0, 65535]')
    return x


def timeout_bw(x):
    x = int(x)
    if x < 1 or x > 10000:
        raise argparse.ArgumentTypeError("Timeout should be less than 10000 ms.")
    return x


def modbus_func_bw(x):
    x = int(x)
    if x not in (1, 2, 3, 4, 5, 6, 16):  # still need to add reading coils
        raise argparse.ArgumentTypeError("ILLEGAL MODBUS FUNCTION")
    return x


def print_errs_prog_bar(verbosity, poll_iter, row_len, b_poll_forever, valid_polls, prog_bar_cols, total_polls,
                        err_type='', modbus_err=0):  # prints error messages and progress bar
    if verbosity is not None:
        if err_type == 'to':
            print('Poll', poll_iter, 'timed out.', '\n' * row_len, end='')
        elif err_type == 'err':
            print('Modbus', modbus_err, 'error', '\n' * row_len, end='')
        elif err_type == 'crc':
            print('CRC does not match for poll', poll_iter, ', transmission failure.', '\n' * row_len, end='')

        if verbosity in (3, 4):
            if verbosity == 3:
                print('\x1b[2K', end='')

            if b_poll_forever:
                print('(', valid_polls, ' / ', poll_iter, ')', sep='', end='\r')
            else:
                print('[', '=' * ((poll_iter * prog_bar_cols) // total_polls), ' ' *
                      (prog_bar_cols - ((poll_iter * prog_bar_cols) // total_polls)), '] (',
                      (poll_iter * 100) // total_polls, '%) (', valid_polls, ' / ', poll_iter, ')', sep='', end='\r')

            if verbosity == 4:
                print()


class ModbusData:
    def __init__(self, start_reg, num_vals, byte_swap, word_swap, b_print, data_type, mb_func):
        self.mb_func = mb_func

        if data_type in four_byte_formats:  # ('uint32', 'sint32', 'float', 'mod10k'):
            regs_per_val = 2
        elif data_type in six_byte_formats:  # ('mod20k'):
            regs_per_val = 3
        elif data_type in eight_byte_formats:  # ('mod30k', 'uint64', 'engy', 'dbl')
            regs_per_val = 4
        else:  # data_type in two_byte_formats:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
            regs_per_val = 1

        last_reg = start_reg + num_vals * regs_per_val
        num_digits = max(int(log10(last_reg)) + 1, 4)

        if self.mb_func == 1:
            self.start_reg = start_reg
        elif self.mb_func in (2, 5):
            self.start_reg = start_reg + 1 * 10 ** num_digits
        elif self.mb_func in (3, 6):
            self.start_reg = start_reg + 4 * 10 ** num_digits
        elif self.mb_func == 4:
            self.start_reg = start_reg + 3 * 10 ** num_digits
        else:
            self.start_reg = start_reg

        self.num_vals = num_vals
        self.byte_swap = byte_swap
        self.word_swap = word_swap
        self.b_print = b_print
        self.data_type = data_type
        # self.pckt = []
        self._value_array = []

    def translate_regs_to_vals(self, recv_packet):
        # self.pckt = pckt
        self._value_array = []
        # self.pckt = []

    #     self.reg(pckt)
    #
    # def reg(self, pckt):
        iter_reg = self.start_reg
        raw_regs = []

        if self.byte_swap:
            recv_packet[::2], recv_packet[1::2] = recv_packet[1::2], recv_packet[::2]

        if self.mb_func in (1, 2):
            for bit_coil_byte in recv_packet:
                for bit_coil in range(8):
                    self._value_array.append((bit_coil_byte >> bit_coil) & 0x1)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print('\x1b[2K', end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
                    if iter_reg >= self.num_vals + self.start_reg:
                        return

        # merge bytes into register values
        for byte_high, byte_low in zip(recv_packet[::2], recv_packet[1::2]):
            raw_regs.append((byte_high << 8) | byte_low)

        if self.mb_func in (5, 6):
            self._value_array = raw_regs

            if self.b_print is not None:
                if self.b_print in (1, 3):
                    print('\x1b[2K', end='\r')
                print('Wrote', self.start_reg, ":", self._value_array[-1])
            return

        if self.data_type in one_byte_formats:  # ('uint8', 'sint8'):
            for r0 in raw_regs:
                if self.data_type == 'uint8':
                    self._value_array.append(r0 >> 8)
                    self._value_array.append(r0 & 0xff)
                elif self.data_type == 'sint8':
                    self._value_array.append(unpack('b', pack('B', (r0 >> 8)))[0])
                    self._value_array.append(unpack('b', pack('B', (r0 & 0xff)))[0])

                if self.b_print is not None:
                    if self.b_print in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(iter_reg, "  :", self._value_array[-2])
                    print(iter_reg + .5, ":", self._value_array[-1])
                    iter_reg += 1
        elif self.data_type in two_byte_formats:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16', 'sm1k16', 'sm10k16'):
            for r0 in raw_regs:  # , self.pckt[2::4], self.pckt[3::4]):
                if self.data_type == 'bin':
                    # self.valarr.append(bin(r0))
                    self._value_array.append(r0)
                elif self.data_type == 'hex':
                    self._value_array.append(r0)
                elif self.data_type == 'ascii':
                    b1 = bytes([r0 >> 8])
                    b0 = bytes([r0 & 0xff])
                    # b1 = bytes([56])
                    # b0 = bytes([70])
                    self._value_array.append(b1.decode('ascii', 'ignore') + b0.decode('ascii', 'ignore'))
                    # self.valarr.append(chr(b1) + chr(b0))
                elif self.data_type == 'uint16':
                    self._value_array.append(r0)
                elif self.data_type == 'sint16':
                    self._value_array.append(unpack('h', pack('H', r0))[0])
                elif self.data_type in ('sm1k16', 'sm10k16'):
                    if r0 >> 15 == 1:
                        sign_mplr = -1
                    else:
                        sign_mplr = 1

                    self._value_array.append((r0 & 0x7fff) * sign_mplr)

                if self.b_print is not None:
                    if self.b_print in (1, 3):
                        print('\x1b[2K', end='\r')
                    if self.data_type == 'bin':
                        # print(i, ":", format(self.valarr[-1], '#018b'))
                        print(iter_reg, ": 0b", format((self._value_array[-1] >> 8) & 0xff, '08b'),
                              format(self._value_array[-1] & 0xff, '08b'))
                        self._value_array[-1] = bin(self._value_array[-1])
                    elif self.data_type == 'hex':
                        print(iter_reg, ":", format(self._value_array[-1], '#06x'))
                        self._value_array[-1] = hex(self._value_array[-1])
                    else:
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
        elif self.data_type in four_byte_formats:
            # ('float', 'uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32','sm10k32'):
            if self.word_swap:
                raw_regs[::2], raw_regs[1::2] = raw_regs[1::2], raw_regs[::2]

            for r0, r1 in zip(raw_regs[::2], raw_regs[1::2]):  # , self.pckt[2::4], self.pckt[3::4]):
                if self.data_type == 'uint32':
                    self._value_array.append((r1 << 16) | r0)
                elif self.data_type == 'sint32':
                    self._value_array.append(unpack('i', pack('I', (r1 << 16) | r0))[0])
                elif self.data_type == 'float':
                    self._value_array.append(unpack('f', pack('I', (r1 << 16) | r0))[0])
                elif self.data_type == 'um1k32':
                    self._value_array.append(r1 * 1000 + r0)
                elif self.data_type == 'sm1k32':
                    if (r1 >> 15) == 1:
                        r1 = (r1 & 0x7fff)
                        self._value_array.append((-1) * (r1 * 1000 + r0))
                    else:
                        self._value_array.append(r1 * 1000 + r0)
                elif self.data_type == 'um10k32':
                    self._value_array.append(r1 * 10000 + r0)
                elif self.data_type == 'sm10k32':
                    if (r1 >> 15) == 1:
                        r1 = (r1 & 0x7fff)
                        self._value_array.append((-1) * (r1 * 10000 + r0))
                    else:
                        self._value_array.append(r1 * 10000 + r0)

                if self.b_print is not None:
                    if self.b_print in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 2
        elif self.data_type in six_byte_formats:  # ('uint48', 'sint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48'):
            if self.word_swap:
                raw_regs[::3], raw_regs[2::3] = raw_regs[2:3], raw_regs[::3]

            for r0, r1, r2 in zip(raw_regs[::3], raw_regs[1::3], raw_regs[2::3]):
                if self.data_type == 'uint48':
                    self._value_array.append((r2 << 32) | (r1 << 16) | r0)
                elif self.data_type == 'sint48':
                    pass
                    # self.valarr.append(unpack('uintle:48', pack('uintle:48', (r2 << 32) | (r1 << 16) | r0))[0])
                    # self.valarr.append(unpack('q', pack('Q', (0 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])
                elif self.data_type == 'um1k48':
                    self._value_array.append((r2 * (10 ** 6)) + (r1 * 1000) + r0)
                elif self.data_type == 'sm1k48':
                    if (r2 >> 15) == 1:
                        r2 = (r2 & 0x7fff)
                        self._value_array.append((-1) * ((r2 * (10 ** 6)) + (r1 * 1000) + r0))
                    else:
                        self._value_array.append((r2 * (10 ** 6)) + (r1 * 1000) + r0)
                elif self.data_type == 'um10k48':
                    self._value_array.append((r2 * (10 ** 8)) + (r1 * 10000) + r0)
                elif self.data_type == 'sm10k48':
                    if (r2 >> 15) == 1:
                        r2 = (r2 & 0x7fff)
                        self._value_array.append((-1) * ((r2 * (10 ** 8)) + (r1 * 10000) + r0))
                    else:
                        self._value_array.append((r2 * (10 ** 8)) + (r1 * 10000) + r0)

                if self.b_print is not None:
                    if self.b_print in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 2
        else:  # ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'engy', 'dbl')
            if self.word_swap:
                raw_regs[::4], raw_regs[1::4], raw_regs[2::4], raw_regs[3::4] = \
                    raw_regs[3::4], raw_regs[2::4], raw_regs[1::4], raw_regs[::4]

            for r0, r1, r2, r3 in zip(raw_regs[::4], raw_regs[1::4], raw_regs[2::4], raw_regs[3::4]):
                if self.data_type == 'uint64':
                    self._value_array.append((r3 << 48) | (r2 << 32) | (r1 << 16) | r0)
                elif self.data_type == 'sint64':
                    self._value_array.append(unpack('q', pack('Q', (r3 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])
                elif self.data_type == 'um1k64':
                    self._value_array.append(r3 * (10 ** 9) + r2 * (10 ** 6) + r1 * 1000 + r0)
                elif self.data_type == 'sm1k64':
                    if (r3 >> 15) == 1:
                        r3 = (r3 & 0x7fff)
                        self._value_array.append((-1) * (r3 * (10 ** 9) + r2 * (10 ** 6) + r1 * 1000 + r0))
                    else:
                        self._value_array.append(r3 * (10 ** 9) + r2 * (10 ** 6) + r1 * 1000 + r0)
                elif self.data_type == 'um10k64':
                    self._value_array.append(r3 * (10 ** 12) + r2 * (10 ** 8) + r1 * 10000 + r0)
                elif self.data_type == 'sm10k64':
                    if (r3 >> 15) == 1:
                        r3 = (r3 & 0x7fff)
                        self._value_array.append((-1) * (r3 * (10 ** 12) + r2 * (10 ** 8) + r1 * 10000 + r0))
                    else:
                        self._value_array.append(r3 * (10 ** 12) + r2 * (10 ** 8) + r1 * 10000 + r0)
                elif self.data_type == 'engy':
                    # split r3 into engineering and mantissa bytes THIS WILL NOT HANDLE MANTISSA - DOCUMENTATION DOES
                    # NOT EXIST ON HOW TO HANDLE IT WITH THEIR UNITS

                    engr = unpack('b', pack('B', (r3 >> 8)))[0]
                    self._value_array.append(((r2 << 32) | (r1 << 16) | r0) * (10 ** engr))
                elif self.data_type == 'dbl':
                    self._value_array.append(unpack('d', pack('Q', (r3 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])

                if self.b_print is not None:
                    if self.b_print in (1, 3):
                        print('\x1b[2K', end='\r')
                    print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 4

    def insert_datetime(self):
        self._value_array.insert(0, str(datetime.now()))

    def set_error(self, mb_err, opt_str=None):
        try:
            if opt_str is None:
                self._value_array = mb_err_dict[mb_err]
            else:
                self._value_array = mb_err_dict[mb_err] + tuple([opt_str])
        except KeyError:
            self._value_array = mb_err_dict[114]

    def get_value_array(self):
        return self._value_array


# list of type options
one_byte_formats = ('uint8', 'sint8')
two_byte_formats = ('uint16', 'sint16', 'sm1k16', 'sm10k16', 'bin', 'hex', 'ascii')
four_byte_formats = ('uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32', 'float')
six_byte_formats = ('uint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48')  # 'sint48' is not supported
eight_byte_formats = ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'dbl', 'engy')

data_type_list = one_byte_formats + two_byte_formats + four_byte_formats + six_byte_formats + eight_byte_formats

# set flag to determine if from commandline or called function
b_cmd_line = False

# list possible errors
mb_err_dict = {1: ('Err', 1, 'ILLEGAL FUNCTION'),
               2: ('Err', 2, 'ILLEGAL DATA ADDRESS'),
               3: ('Err', 3, 'ILLEGAL DATA VALUE'),
               4: ('Err', 4, 'SLAVE DEVICE FAILURE'),
               5: ('Err', 5, 'ACKNOWLEDGE'),
               6: ('Err', 6, 'SLAVE DEVICE BUSY'),
               7: ('Err', 7, 'NEGATIVE ACKNOWLEDGE'),
               8: ('Err', 8, 'MEMORY PARITY ERROR'),
               10: ('Err', 10, 'GATEWAY PATH UNAVAILABLE'),
               11: ('Err', 11, 'GATEWAY TARGET DEVICE FAILED TO RESPOND'),
               19: ('Err', 19, 'UNABLE TO MAKE TCP CONNECTION'),
               87: ('Err', 87, 'COMM ERROR'),
               101: ('Err', 101, 'INVALID IP ADDRESS OR COM PORT'),
               102: ('Err', 102, 'INVALID DATA TYPE'),
               103: ('Err', 103, 'INVALID REGISTER LOOKUP'),
               104: ('Err', 104, 'INVALID FILE NAME'),
               105: ('Err', 105, 'UNABLE TO ACCESS CSV FILE'),
               106: ('Err', 106, 'UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER'),
               107: ('Err', 107, 'KEYBOARD INTERRUPT'),
               108: ('Err', 108, 'UNEXPECTED TCP MESSAGE LENGTH'),
               109: ('Err', 109, 'UNEXPECTED MODBUS MESSAGE LENGTH'),
               110: ('Err', 110, 'UNEXPECTED MODBUS FUNCTION RETURNED'),
               111: ('Err', 111, 'UNEXPECTED MODBUS SLAVE DEVICE MESSAGE'),
               112: ('Err', 112, 'MULTIPLE POLLS FOR WRITE COMMAND'),
               113: ('Err', 113, 'CRC INCORRECT, DATA TRANSMISSION FAILURE'),
               114: ('Err', 114, 'UNEXPECTED ERROR NUMBER'),
               224: ('Err', 224, 'GATEWAY: INVALID SLAVE ID'),
               225: ('Err', 225, 'GATEWAY: RETURNED FUNCTION DOES NOT MATCH'),
               226: ('Err', 226, 'GATEWAY: GATEWAY TIMEOUT'),
               227: ('Err', 227, 'GATEWAY: INVALID CRC'),
               228: ('Err', 228, 'GATEWAY: INVALID CLIENT')}  # ? don't know what i was thinking


# run script
def mb_poll(ip, mb_id, start_reg, num_vals, b_help=False, num_polls=1, data_type='float', b_byteswap=False,
            b_wordswap=False, zero_based=False, mb_timeout=1500, file_name_input=None, verbosity=None, port=502,
            poll_delay=1000, mb_func=3):

    if b_help:
        print('Polls a modbus device through network.',
              '\nip:         The IP address of the gateway or the com port (comX)',
              '\nmb_id:      The id number of the desired device.',
              '\nstart_reg:  The address of the first register desired.',
              '\nnum_vals:   The number of outputs to return (certain types will use 2 or 4 registers per output).',
              '\nnum_polls:  The number of polls. Default is 1.',
              '\ndata_type:  The desired type to be returned.',
              '\nb_byteswap: Sets byteswap to true.  Default is Big Endian (False).',
              '\nb_wordswap: Sets wordswap to true.  Default is Little Endian (False).',
              '\nzero_based: Interprets starting address as 0-based value.  If not set then',
              '\n                setting srt=2 looks at 1 (second register).  If set then setting',
              '\n                srt=2 looks at 2 (third register) (Default is 1, else 0).',
              '\nmb_timeout: Time in milliseconds to wait for reply message. Default is 1500.'
              '\nfile_name:  Generates csv file in current folder.',
              '\nverbosity:  Verbosity options. 1: Static display  2: Consecutive display  3: Static + progress bar '
              '\n                4: Consecutive + progress bar',
              '\nport:       Set port to communicate over.  Default is 502.'
              '\npoll_delay: Delay in ms to let function sleep to retrieve reasonable data.  Default is 1000.'
              '\nmb_func:    Modbus function. Default is 3.'
              )
        return

    serial_port = None
    val_to_write = None

    # ~ check that ip is valid
    if type(ip) == str:
        ip_arr = ip.split(".")

        if len(ip_arr) != 4:
            if len(ip_arr) == 1:
                com_ports = list(serial.tools.list_ports.comports())
                ip = ip.upper()

                for ports in com_ports:
                    if ip == ports[0]:
                        serial_port = int(ip[3:]) - 1
                        # print('cmpt', cmpt)
                        break
                else:
                    return mb_err_dict[101]
            else:
                return mb_err_dict[101]  # raise ValueError('Invalid IP address!')
        else:
            for ch in ip_arr:
                if int(ch) > 255 or int(ch) < 0:
                    return mb_err_dict[101]  # raise ValueError('Invalid IP address!')

    # check certain things if called through script rather than commandline
    if not b_cmd_line:
        # check if device in correct interval
        mb_id = device_bw(mb_id)

        # check if strt in correct interval
        start_reg = register_bw(start_reg)

        mb_timeout = timeout_bw(mb_timeout)

        # check if type is part of allowable functions
        if data_type not in data_type_list:
            return mb_err_dict[102]  # raise ValueError('Please choose type from list: ' + str(type_lst))

        port = int(port)

        mb_func = modbus_func_bw(mb_func)
        # if func not in (3, 4):
        #     return mberrs[1]  # illegal modbus function

    mb_timeout = mb_timeout / 1000  # convert from ms to s

    if mb_func in (5, 6, 16):
        b_write_mb = True
        poll_delay = 0
    else:
        b_write_mb = False
        # if pdelay == -1:
        #     if p == 1:
        #         pdelay = 0  # default delay for single poll
        #     else:
        #         pdelay = 1000  # default delay for multiple polls

        # pdelay = float(pdelay)

    # change lng to check for the requested number of registers
    if b_write_mb:  # write to register/coil
        val_to_write = write_reg_bw(num_vals)
        exp_num_bytes_ret = 8
    else:
        num_vals = num_regs_bw(num_vals)  # check if lng is in correct interval

        if mb_func in (1, 2):
            pass
        elif data_type in four_byte_formats:  # ('float', 'uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32'):
            # num_vals *= 2
            num_regs = num_vals * 2
        elif data_type in six_byte_formats:  # ('uint48', 'sint48'):
            # num_vals *= 3
            num_regs = num_vals * 3
        elif data_type in eight_byte_formats:  # ('mod30k', 'uint64', 'engy', 'dbl'):
            # num_vals *= 4
            num_regs = num_vals * 4
        elif data_type in one_byte_formats:  # ('uint8', 'sint8'):
            # num_vals = (num_vals + 1) // 2
            num_regs = (num_vals + 1) // 2
        else:
            num_regs = num_vals

        if mb_func in (1, 2):
            exp_num_bytes_ret = 5 + ((num_regs + 7) // 8)  # number of bytes converted from number of bits
        else:
            exp_num_bytes_ret = 5 + num_regs * 2  # number of bytes expected in return for com port

    # check if zero based and starting register will work
    start_reg_zero = start_reg - (not zero_based)

    if start_reg_zero < 0:
        return mb_err_dict[103]  # raise ValueError('Invalid register lookup.')

    # check if infinite polling
    if num_polls != 1 and b_write_mb:
        return mb_err_dict[112]  # shouldn't have multiple polls for a write command
    else:
        if num_polls < 1:  # poll forever
            print('Ctrl-C to exit.')
            b_poll_forever = True
            num_polls = 1
        elif num_polls == 1:  # single poll
            # pdelay = 0
            b_poll_forever = False
        else:  # multiple polls
            b_poll_forever = False

    # check filename for validity
    if file_name_input is not None:
        if file_name_input.endswith('.csv'):
            file_name = file_name_input
        else:
            file_name = file_name_input + '.csv'

        # file_name_arr = file_name.split(".")
        #
        # if len(file_name_arr) == 1:
        #     fname = file_name + '.csv'
        # elif len(file_name_arr) == 2:
        #     fname = file_name_arr[0] + '.csv'
        # else:
        #     return mberrs[104]
            # raise ValueError('Inappropriate name for file.')
    else:
        file_name = None

    # check os to determine if there will be a problem with different print options
    if verbosity in (1, 3):
        if os.name == 'nt':  # if static print is called, this can't be implemented in windows, give other options
            if not b_cmd_line:
                verbosity = None  # not called from commandline, no guarantee to respond to input
            else:
                while verbosity in (1, 3):
                    verbosity = int(input('Please choose from [0, 2, 4] (blank, consecutive, cons + progress bar): '))

                if verbosity == 0:
                    verbosity = None
        else:
            num_prnt_rws = num_vals + 1
            # if mb_func in (1, 2):
            #     rws = num_vals + 1
            # elif data_type in one_byte_formats:  # ('uint8', 'sint8'):
            #     rws = num_vals * 2 + 1
            # elif data_type in two_byte_formats:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
            #     rws = num_vals + 1
            # elif data_type in four_byte_formats:  # ('uint32', 'sint32', 'float', 'mod1k', 'mod10k'):
            #     rws = int(num_vals / 2 + 1)
            # elif data_type in six_byte_formats:  # 'mod20k':
            #     rws = int(num_vals / 3 + 1)
            # else:  # in eight_byte_formats:  # ('uint64', 'mod30k', 'engy', 'dbl')
            #     rws = int(num_vals / 4 + 1)
            print('\n'*(num_prnt_rws + 1), end='')
    else:
        num_prnt_rws = 2

    # set value for length of progress bar
    if verbosity in (3, 4):
        if os.name == 'nt':
            prog_bar_len = 65 - (2 * len(str(num_polls)))  # 65 = 80 - 15
        else:
            rows, columns = os.popen('stty size', 'r').read().split()  # determine size of terminal
            prog_bar_len = int(columns) - 15 - (2 * len(str(num_polls)))
    else:
        prog_bar_len = 0

    # vallst = 0
    mb_data = ModbusData(start_reg, num_vals, b_byteswap, b_wordswap, verbosity, data_type, mb_func)

    if file_name_input is not None:
        try:
            csv_file = open(file_name, 'w', newline='')
        except IOError:
            return mb_err_dict[105]
        else:
            csv_file_wrtr = csv.writer(csv_file)
            if mb_func in (1, 2):
                csv_header = range(start_reg_zero, start_reg_zero + num_vals)
            elif data_type in one_byte_formats:  # ('uint8', 'sint8'):
                csv_header = [x / 2 + start_reg_zero for x in range(0, num_regs * 2)]  # should work
            elif data_type in two_byte_formats:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
                csv_header = range(start_reg_zero, start_reg_zero + num_regs)
            elif data_type in four_byte_formats:  # ('uint32', 'sint32', 'float', 'mod1k', 'mod10k'):
                csv_header = range(start_reg_zero, start_reg_zero + num_regs)[::2]
            elif data_type in six_byte_formats:  # 'mod20k':
                csv_header = range(start_reg_zero, start_reg_zero + num_regs)[::3]
            else:  # ('uint64', 'mod30k', 'engy', 'dbl')
                csv_header = range(start_reg_zero, start_reg_zero + num_regs)[::4]
            csv_header = list(csv_header)
            csv_header.insert(0, None)  # shifts columns to make room for dates
            csv_file_wrtr.writerow(csv_header)
    else:
        csv_file = None
        csv_file_wrtr = None

    # timeout = 1
    # ~ #create packet here:
    if serial_port is not None:  # com port communication
        req_packet = bytearray(6)
        req_packet[0] = mb_id & 0xFF           # device address
        req_packet[1] = mb_func & 0xFF          # function code
        req_packet[2] = (start_reg_zero >> 8) & 0xFF  # starting register high byte
        req_packet[3] = start_reg_zero & 0xFF         # starting register low byte
        if b_write_mb:
            if mb_func == 5:
                if val_to_write == 1:
                    req_packet[4] = 0xFF
                elif val_to_write == 0:
                    req_packet[4] = 0x00
                else:
                    return mb_err_dict[3]

                req_packet[5] = 0x00
            else:
                req_packet[4] = (val_to_write >> 8) & 0xFF   # value to write to read high byte
                req_packet[5] = val_to_write & 0xFF          # value to write to read low byte

            packet_write_list = list(req_packet)
        else:
            req_packet[4] = (num_regs >> 8) & 0xFF   # starting length to read high byte
            req_packet[5] = num_regs & 0xFF          # starting length to read low byte

        req_packet.extend(mbcrc.calcbytearray(req_packet))
        # print(list(packet))
    else:  # TCP/IP communication
        if mb_func == 16:
            # packet = bytearray(15)
            req_packet = bytearray(21)
        else:
            req_packet = bytearray(12)

        req_packet[5] = 6 & 0xFF
        req_packet[6] = mb_id & 0xFF
        req_packet[7] = mb_func & 0xFF
        req_packet[8] = (start_reg_zero >> 8) & 0xFF  # HIGH starting register
        req_packet[9] = start_reg_zero & 0xFF  # LOW register
        if b_write_mb:
            if mb_func == 16:
                req_packet[5] = 15 & 0xFF
                req_packet[10] = 0 & 0xFF  # HIGH number of registers
                req_packet[11] = 4 & 0xFF  # LOW number of registers

                req_packet[12] = 8 & 0xFF  # number of bytes

                # should be wrt here, currently trying to set modbus map for siemens breaker
                req_packet[13] = (59492 >> 8) & 0xFF
                req_packet[14] = 59492 & 0xFF

                req_packet[15] = (3 >> 8) & 0xFF
                req_packet[16] = 3 & 0xFF

                req_packet[17] = (8 >> 8) & 0xFF
                req_packet[18] = 8 & 0xFF

                req_packet[19] = (47368 >> 8) & 0xFF
                req_packet[20] = 47368 & 0xFF

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

                # print(list(packet))
            else:
                req_packet[10] = (val_to_write >> 8) & 0xFF
                req_packet[11] = val_to_write & 0xFF
                # print(list(packet))

            packet_write_list = list(req_packet[6:])
        else:
            req_packet[10] = (num_regs >> 8) & 0xFF
            req_packet[11] = num_regs & 0xFF

    serial_conn = None
    # print(list(packet))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_conn:
        tcp_conn.settimeout(mb_timeout)

        if serial_port is not None:  # COM port
            serial_conn = serial.Serial(serial_port, timeout=mb_timeout, baudrate=9600)  # set up serial
        else:
            try:
                # print(port)
                tcp_conn.connect((ip, port))

            except socket.timeout:
                if verbosity is not None:
                    print('Connection could not be made with gateway.  Timed out after 5 seconds.')
                return mb_err_dict[19]
            except socket.error:
                return mb_err_dict[19]

            tcp_conn.setblocking(0)
        valid_polls = 0

        cur_poll = 1
        b_conn_err = False
        # for i in range(1, p + 1):
        while cur_poll < num_polls + 1:
            # print(conn)
            try:
                if serial_port is not None:  # COM port
                    serial_conn.write(req_packet)  # send msg
                else:
                    # clear Rx buffer !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    tcp_conn.sendall(req_packet)  # send modbus request

                if verbosity in (1, 3):
                    print('\x1b[', num_prnt_rws + 1, 'F\x1b[2K', sep='', end='\r')

                if verbosity is not None:
                    print('\nPoll', cur_poll, 'at:', str(datetime.now()))

                poll_start_time = time.time()

                if serial_port is not None:  # using com port!
                    recv_packet_bytearr = serial_conn.read(exp_num_bytes_ret)  # need packetbt

                    if recv_packet_bytearr:  # recv_packet_bytearr != []:

                        # print(list(rec_packet_bytearr))
                        recv_packet = list(recv_packet_bytearr[:-2])
                        
                        if mbcrc.calcbytearray(recv_packet) != recv_packet_bytearr[-2:]:
                            mb_data.set_error(113)

                            b_conn_err = True
                            print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                                prog_bar_len, num_polls, 'crc')
                    else:
                        mb_data.set_error(87)

                        b_conn_err = True
                        print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                            prog_bar_len, num_polls, 'to')
                else:  # using ethernet!
                    select_inputs = select.select([tcp_conn], [], [], mb_timeout)[0]

                    if select_inputs:  # select_inputs != []:
                        try:
                            # print('start')
                            recv_packet_bytearr = tcp_conn.recv(1024, )  # gives bytes type
                            # print(list(packetbt))
                        except socket.timeout:
                            print('to')
                            mb_data.set_error(87)
                            break
                        except socket.error as r:
                            print(r)
                            mb_data.set_error(87)
                            break

                        if len(recv_packet_bytearr) > 6:
                            if recv_packet_bytearr[0] >= 0:
                                tcp_hdr_exp_len = int.from_bytes(recv_packet_bytearr[4:6], byteorder='big')
                                # print(list(packetbt), '\n'*rws, end='')
                                if tcp_hdr_exp_len == (len(recv_packet_bytearr) - 6):
                                    recv_packet = list(recv_packet_bytearr[6:])
                                    # print(packetrec)
                                else:
                                    mb_data.set_error(108)  # UNEXPECTED MODBUS MESSAGE LENGTH
                                    try:
                                        print(recv_packet_bytearr.decode('ascii'), '\n'*num_prnt_rws, end='')
                                    except UnicodeDecodeError:
                                        print(list(recv_packet_bytearr), '\n'*num_prnt_rws, end='')
                                    b_conn_err = True
                            else:
                                if verbosity is not None:
                                    try:
                                        print(recv_packet_bytearr.decode('ascii'), '\n'*num_prnt_rws, end='')
                                    except UnicodeDecodeError:
                                        print(list(recv_packet_bytearr), '\n'*num_prnt_rws, end='')
                                mb_data.set_error(106)  # UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER
                                break
                        else:  # TCP message <6
                            print('Partial TCP message returned of length', len(recv_packet_bytearr))

                            mb_data.set_error(106)  # UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER
                            break
                    else:  # select timed out
                        mb_data.set_error(87)
                        b_conn_err = True
                        print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                            prog_bar_len, num_polls, 'to')

                if not b_conn_err:
                    if mb_id == recv_packet[0] or recv_packet[0] == 0:  # check modbus device
                        if recv_packet[1] == mb_func:  # check modbus function
                            if b_write_mb:  # if write command, will have different checks
                                if packet_write_list == recv_packet:
                                    # print('Wrote', wrt, 'to register', strt)
                                    # mbdata.valarr = [wrt]
                                    if mb_func == 6:
                                        mb_data.translate_regs_to_vals(recv_packet[4:])
                                    else:
                                        mb_data.translate_regs_to_vals((0, val_to_write))
                                    print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                                        prog_bar_len, num_polls)
                                else:
                                    print(recv_packet)
                                    mb_data.set_error(111)
                                    print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                                        prog_bar_len, num_polls, 'err', 111)
                            else:
                                if recv_packet[2] == (len(recv_packet) - 3):  # check length of modbus message
                                    # print("correct packet struct returned")
                                    # print(packetbt.decode('ascii'))
                                    mb_data.translate_regs_to_vals(recv_packet[3:])

                                    if csv_file_wrtr is not None:
                                        mb_data.insert_datetime()
                                        csv_file_wrtr.writerow(mb_data.get_value_array())

                                    valid_polls += 1

                                    print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                                        prog_bar_len, num_polls)
                                else:
                                    mb_data.set_error(109)  # UNEXPECTED MODBUS MESSAGE LENGTH
                        elif recv_packet[1] == (mb_func + 128) or recv_packet[1] == 128:  # check for error return
                            if recv_packet[2] in mb_err_dict:
                                mb_data.set_error(recv_packet[2])  # MODBUS ERROR RETURNED
                            else:
                                mb_data.set_error(114, recv_packet[2])

                            print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                                prog_bar_len, num_polls, 'err', recv_packet[2])
                        else:
                            mb_data.set_error(110)  # UNEXPECTED MODBUS FUNCTION RETURNED
                            # print(packetrec)
                    else:
                        mb_data.set_error(111)  # UNEXPECTED MODBUS SLAVE DEVICE MESSAGE
                        # print(packetrec)
                else:
                    b_conn_err = False

                cur_poll += 1
                if b_poll_forever:
                    num_polls += 1

                # sleep for the rest of poll delay
                if cur_poll != num_polls + 1:
                    time.sleep(max(0, poll_start_time + poll_delay / 1000 - time.time()))

            except KeyboardInterrupt:
                if not b_poll_forever:
                    mb_data.set_error(107)
                break
            # end try
        # end while
    # end with

    if verbosity is not None:
        print()

    if csv_file_wrtr is not None:
        csv_file.close()

    return mb_data.get_value_array()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Polls a modbus device through network.')

    parser.add_argument('ip', type=str, help='The IP address of the gateway or the comport (comX).')
    parser.add_argument('dev', type=device_bw, help='The id number of the desired device.')
    parser.add_argument('srt', type=register_bw, help='The address of the first register desired.')
    parser.add_argument('lng', type=int,
                        help='The number of registers to return (certain types will use 2 or 4 registers per output).')
    parser.add_argument('-p', '--poll', type=int, default=1, help='The number of polls. Default is 1.')
    parser.add_argument('-t', '--typ', type=str, default='float', choices=data_type_list,
                        help='The desired type to be returned')
    parser.add_argument('-bs', '--byteswap', action='store_true', help='Sets byteswap to true.  Default is Big Endian.')
    parser.add_argument('-ws', '--wordswap', action='store_true',
                        help='Sets wordswap to true.  Default is Little Endian.')
    parser.add_argument('-0', '--zbased', action='store_true',
                        help='Interprets starting address as 0-based value.  If not set then setting srt=2 looks at 1 '
                             '(second register).  If set then setting srt=2 looks at 2 (third register).')
    parser.add_argument('-to', '--timeout', type=timeout_bw, default=1500,
                        help='Time in milliseconds to wait for reply message. Default is 1500.')
    parser.add_argument('-fl', '--file', type=str, help='Generates csv file in current folder.')
    parser.add_argument('-v', '--verbose', action='count',
                        help='Verbosity options. 1: Static display  2: Consecutive display  3: Static + progress bar '
                             '4: Consecutive + progress bar')
    parser.add_argument('-pt', '--port', type=int, default=502, help='Set port to communicate over.  Default is 502.')
    parser.add_argument('-pd', '--pdelay', type=int, default=1000,
                        help='Delay in ms to let function sleep to retrieve reasonable data.  Default is 1000.')
    parser.add_argument('-f', '--func', type=modbus_func_bw, default=3,
                        help='Modbus function.  Only 3, 4, 5, and 6 are supported.')

    args = parser.parse_args()

    b_cmd_line = True
    poll_results = mb_poll(args.ip, args.dev, args.srt, args.lng, num_polls=args.poll, data_type=args.typ,
                    b_byteswap=args.byteswap, b_wordswap=args.wordswap, zero_based=args.zbased, mb_timeout=args.timeout,
                    file_name_input=args.file, verbosity=args.verbose, port=args.port, poll_delay=args.pdelay,
                    mb_func=args.func)

    print(poll_results)
