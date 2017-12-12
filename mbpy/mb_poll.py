#!/usr/bin/python3

import time
import select
import socket
import argparse
import csv
import os
# import fcntl
import serial
import serial.tools.list_ports
from math import log10
# import sys
# from mbpy import mbcrc  # from folder import file
from struct import pack, unpack
from datetime import datetime
try:
    import RPi.GPIO as GPIO
except ImportError:
    B_RPI_GPIO_EXISTS = False
except RuntimeError:
    B_RPI_GPIO_EXISTS = False
else:
    GPIO.setmode(GPIO.BOARD)
    B_RPI_GPIO_EXISTS = True
    # print('does exist')


ERASE_LINE = '\x1b[2K'

# list of type options
ONE_BYTE_FORMATS = ('uint8', 'sint8')
TWO_BYTE_FORMATS = ('uint16', 'sint16', 'sm1k16', 'sm10k16', 'bin', 'hex', 'ascii')
FOUR_BYTE_FORMATS = ('uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32', 'float')
SIX_BYTE_FORMATS = ('uint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48')  # 'sint48' is not supported
EIGHT_BYTE_FORMATS = ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'dbl', 'engy')

DATA_TYPE_LIST = ONE_BYTE_FORMATS + TWO_BYTE_FORMATS + FOUR_BYTE_FORMATS + SIX_BYTE_FORMATS + EIGHT_BYTE_FORMATS

# set flag to determine if from commandline or called function
B_CMD_LINE = False

# list possible errors
MB_ERR_DICT = {1: ('Err', 1, 'ILLEGAL FUNCTION'),
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
               115: ('Err', 115, 'UNABLE TO OPEN SERIAL PORT'),
               116: ('Err', 116, 'INVALID RASPBERRY PI GPIO PIN'),
               224: ('Err', 224, 'GATEWAY: INVALID SLAVE ID'),
               225: ('Err', 225, 'GATEWAY: RETURNED FUNCTION DOES NOT MATCH'),
               226: ('Err', 226, 'GATEWAY: GATEWAY TIMEOUT'),
               227: ('Err', 227, 'GATEWAY: INVALID CRC'),
               228: ('Err', 228, 'GATEWAY: INVALID CLIENT')}  # ? don't know what i was thinking

#        File: CRC16.PY
#              CRC-16 (reverse) table lookup for Modbus or DF1
# code obtained from https://www.digi.com/wiki/developer/index.php/Python_CRC16_Modbus_DF1
CRC_TABLE = (0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
             0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
             0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
             0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
             0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
             0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
             0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
             0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
             0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
             0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
             0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
             0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
             0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
             0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
             0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
             0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
             0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
             0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
             0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
             0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
             0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
             0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
             0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
             0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041,
             0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
             0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
             0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
             0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
             0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
             0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
             0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
             0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040)


def calc_next_crc_byte(new_byte, prev_crc=0xFFFF):
    """Given a new Byte and previous CRC, Calc a new CRC-16"""
    # if type(new_byte) == type("c"):
    if isinstance(new_byte, str):
        by = ord(new_byte)
    else:
        by = new_byte
    prev_crc = (prev_crc >> 8) ^ CRC_TABLE[(prev_crc ^ by) & 0xFF]
    return prev_crc & 0xFFFF


def calc_crc_binary_string(st, start_crc=0xFFFF):
    """Given a bunary string and starting CRC, Calc a final CRC-16 """
    for ch in st:
        start_crc = (start_crc >> 8) ^ CRC_TABLE[(start_crc ^ ord(ch)) & 0xFF]
    return start_crc


def calc_crc_byte_array(st, start_crc=0xFFFF):
    """Given a byte array and starting CRC, Calc a final CRC-16 """
    for ch in st:
        start_crc = (start_crc >> 8) ^ CRC_TABLE[(start_crc ^ ch) & 0xFF]
    crcb = bytearray(2)
    crcb[1] = int(start_crc / 256)
    crcb[0] = start_crc % 256
    return crcb


# bandwidth checks for input variables:
def device_bw(x):
    x = int(x)
    if x < 1 or x > 255:
        raise argparse.ArgumentTypeError("Device ID must be between [1, 255].")
    return x


def validate_device_id(dev):
    dev = int(dev)
    if dev < 1 or dev > 255:
        return None, MB_ERR_DICT[10]  # gateway path unavailable
    return dev, None


def register_bw(x):
    x = int(x)
    if x < 0 or x > 99990:
        raise argparse.ArgumentTypeError("Starting address must be in [0, 99990].")
    return x


def validate_register(reg):
    reg = int(reg)
    if reg < 0 or reg > 99990:
        return None, MB_ERR_DICT[2]  # invalid data address
    return reg, None


def num_regs_bw(x):
    x = int(x)
    if x < 1 or x > 9999:
        raise argparse.ArgumentTypeError("Length of addresses must be in [1, 9999].")
    return x


def validate_num_registers(num_regs):
    num_regs = int(num_regs)
    if num_regs < 1 or num_regs > 99990:
        return None, MB_ERR_DICT[2]  # invalid data address
    return num_regs, None


def write_reg_bw(x):
    x = int(x)
    if x != (x & 0xFFFF):
        raise argparse.ArgumentTypeError('Value to write must be in [0, 65535]')
    return x


def validate_write_value(wrt_val):
    wrt_val = int(wrt_val)
    if wrt_val != (wrt_val & 0xFFFF):
        return None, MB_ERR_DICT[3]  # illegal data value
    return wrt_val, None


def timeout_bw(x):
    x = int(x)
    if x < 1 or x > 10000:
        raise argparse.ArgumentTypeError("Timeout should be less than 10000 ms.")
    return x


def validate_timeout(timeout):
    timeout = int(timeout)
    if timeout < 1 or timeout > 10000:
        return None, MB_ERR_DICT[3]  # illegal data value
    return timeout, None


def modbus_func_bw(x):
    x = int(x)
    if x not in (1, 2, 3, 4, 5, 6, 16):  # still need to add reading coils
        raise argparse.ArgumentTypeError("ILLEGAL MODBUS FUNCTION")
    return x


def validate_modbus_function(func):
    func = int(func)
    if func not in (1, 2, 3, 4, 5, 6, 16):
        return None, MB_ERR_DICT[1]  # illegal function
    return func, None


def pin_cntl_bw(x):
    if x is not None:
        x = int(x)
        if x not in (3, 5, 7, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40):
            raise argparse.ArgumentTypeError('Illegal Raspberr Pi pin.')
    return x


def validate_cntl_pin(cntl_pin):
    if cntl_pin is not None:
        cntl_pin = int(cntl_pin)
        if cntl_pin not in (3, 5, 7, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38,
                            40):
            return None, MB_ERR_DICT[116]  # invalid rpi gpio pin
        return cntl_pin, None
    return None, None


def validate_data_type(data_type):
    if data_type not in DATA_TYPE_LIST:
        return None, MB_ERR_DICT[102]  # invalid data type
    return data_type, None


def validate_ip(ip):
    error_code = None
    serial_port = None
    ip_func = ip

    if type(ip_func) == str:
        ip_arr = ip_func.split(".")

        if len(ip_arr) != 4:
            if os.name == 'nt':
                if len(ip_arr) == 1:
                    com_ports = list(serial.tools.list_ports.comports())
                    ip_upper = ip_func.upper()

                    for ports in com_ports:
                        if ip_upper == ports[0]:
                            serial_port = int(ip_upper[3:]) - 1
                            ip_func = None
                            break
                    else:
                        error_code = MB_ERR_DICT[101]
                else:
                    error_code = MB_ERR_DICT[101]  # raise ValueError('Invalid IP address!')
            else:
                # going on faith alone at this point that the correct serial address is being used on a linux system
                serial_port = ip_func
                ip_func = None
        else:
            for ch in ip_arr:
                if int(ch) > 255 or int(ch) < 0:
                    error_code = MB_ERR_DICT[101]  # raise ValueError('Invalid IP address!')
                    break

    return ip_func, serial_port, error_code


def validate_file_name(file_name_input):
    if file_name_input is not None:
        if file_name_input.endswith('.csv'):
            file_name = file_name_input
        else:
            file_name = file_name_input + '.csv'
    else:
        file_name = None
    return file_name, None


def print_errs_prog_bar(verbosity, poll_iter, row_len, b_poll_forever, valid_polls, prog_bar_cols, total_polls,
                        modbus_err=0):  # prints error messages and progress bar
    if verbosity is not None:
        # if err_type == 'to':
        #     print('Poll', poll_iter, 'timed out.', '\n' * row_len, end='')
        if modbus_err != 0:
            print('Modbus', modbus_err, 'error', '\n' * row_len, end='')
        # elif err_type == 'crc':
        #     print('CRC does not match for poll', poll_iter, ', transmission failure.', '\n' * row_len, end='')

        if verbosity in (3, 4):
            if verbosity == 3:
                print(ERASE_LINE, end='')

            if b_poll_forever:
                print('(', valid_polls, ' / ', poll_iter, ')', sep='', end='\r')
            else:
                print('[', '=' * ((poll_iter * prog_bar_cols) // total_polls), ' ' *
                      (prog_bar_cols - ((poll_iter * prog_bar_cols) // total_polls)), '] (',
                      (poll_iter * 100) // total_polls, '%) (', valid_polls, ' / ', poll_iter, ')', sep='', end='\r')

            if verbosity == 4:
                print()


class ModbusData:
    def __init__(self, start_reg, num_vals, byte_swap, word_swap, b_print, data_type, mb_func, b_raw_bytes=False):
        self.mb_func = mb_func

        if data_type in FOUR_BYTE_FORMATS:  # ('uint32', 'sint32', 'float', 'mod10k'):
            regs_per_val = 2
        elif data_type in SIX_BYTE_FORMATS:  # ('mod20k'):
            regs_per_val = 3
        elif data_type in EIGHT_BYTE_FORMATS:  # ('mod30k', 'uint64', 'engy', 'dbl')
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
        self._value_array = []
        self.b_raw_bytes = b_raw_bytes

    def translate_regs_to_vals(self, recv_packet):
        self._value_array = []

        if self.b_raw_bytes:
            iter_reg = 0
        else:
            iter_reg = self.start_reg
        raw_regs = []

        if self.byte_swap:
            recv_packet[::2], recv_packet[1::2] = recv_packet[1::2], recv_packet[::2]

        if self.mb_func in (1, 2):
            if self.b_raw_bytes:
                for mb_byte in recv_packet:
                    self._value_array.append(mb_byte & 0xff)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
                return
            else:
                for bit_coil_byte in recv_packet:
                    for bit_coil in range(8):
                        self._value_array.append((bit_coil_byte >> bit_coil) & 0x1)

                        if self.b_print is not None:
                            if self.b_print in (1, 3):
                                print(ERASE_LINE, end='\r')
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
                    print(ERASE_LINE, end='\r')
                print('Wrote', self.start_reg, ":", self._value_array[-1])
            return

        if self.data_type in ONE_BYTE_FORMATS:  # ('uint8', 'sint8'):
            if self.b_raw_bytes:
                for mb_byte in recv_packet:
                    self._value_array.append(mb_byte & 0xff)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
            else:
                for r0 in raw_regs:
                    if self.data_type == 'uint8':
                        self._value_array.append(r0 >> 8)
                        self._value_array.append(r0 & 0xff)
                    elif self.data_type == 'sint8':
                        self._value_array.append(unpack('b', pack('B', (r0 >> 8)))[0])
                        self._value_array.append(unpack('b', pack('B', (r0 & 0xff)))[0])

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, "  :", self._value_array[-2])
                        print(iter_reg + .5, ":", self._value_array[-1])
                        iter_reg += 1
        elif self.data_type in TWO_BYTE_FORMATS:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16', 'sm1k16', 'sm10k16'):
            if self.b_raw_bytes:
                for mb_byte in recv_packet:
                    self._value_array.append(mb_byte & 0xff)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
            else:
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
                            print(ERASE_LINE, end='\r')
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
        elif self.data_type in FOUR_BYTE_FORMATS:
            # ('float', 'uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32','sm10k32'):
            if self.word_swap:
                raw_regs[::2], raw_regs[1::2] = raw_regs[1::2], raw_regs[::2]

            if self.b_raw_bytes:
                for mb_reg in raw_regs:
                    self._value_array.append((mb_reg >> 8) & 0xff)
                    self._value_array.append(mb_reg & 0xff)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-2])
                    iter_reg += 1

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
            else:
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
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                        iter_reg += 2
        elif self.data_type in SIX_BYTE_FORMATS:  # ('uint48', 'sint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48'):
            if self.word_swap:
                raw_regs[::3], raw_regs[2::3] = raw_regs[2:3], raw_regs[::3]

            if self.b_raw_bytes:
                for mb_reg in raw_regs:
                    self._value_array.append((mb_reg >> 8) & 0xff)
                    self._value_array.append(mb_reg & 0xff)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-2])
                    iter_reg += 1

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
            else:
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
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                        iter_reg += 2
        else:  # ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'engy', 'dbl')
            if self.word_swap:
                raw_regs[::4], raw_regs[1::4], raw_regs[2::4], raw_regs[3::4] = \
                    raw_regs[3::4], raw_regs[2::4], raw_regs[1::4], raw_regs[::4]

            if self.b_raw_bytes:
                for mb_reg in raw_regs:
                    self._value_array.append((mb_reg >> 8) & 0xff)
                    self._value_array.append(mb_reg & 0xff)

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-2])
                    iter_reg += 1

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                    iter_reg += 1
            else:
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
                        # split r3 into engineering and mantissa bytes THIS WILL NOT HANDLE MANTISSA-DOCUMENTATION DOES
                        # NOT EXIST ON HOW TO HANDLE IT WITH THEIR UNITS

                        engr = unpack('b', pack('B', (r3 >> 8)))[0]
                        self._value_array.append(((r2 << 32) | (r1 << 16) | r0) * (10 ** engr))
                    elif self.data_type == 'dbl':
                        self._value_array.append(unpack('d', pack('Q', (r3 << 48) | (r2 << 32) | (r1 << 16) | r0))[0])

                    if self.b_print is not None:
                        if self.b_print in (1, 3):
                            print(ERASE_LINE, end='\r')
                        print(iter_reg, ":", self._value_array[-1])
                        iter_reg += 4

    def insert_datetime(self):
        self._value_array.insert(0, str(datetime.now()))

    def set_error(self, mb_err):  # , opt_str=None):
        if mb_err not in MB_ERR_DICT:
            self._value_array = MB_ERR_DICT[114] + tuple([mb_err])
        else:
            self._value_array = MB_ERR_DICT[mb_err]

    def get_value_array(self):
        return self._value_array


def get_expected_num_ret_bytes(b_write_mb, mb_func, num_vals, data_type):
    num_regs = 1
    if b_write_mb:  # write to register/coil
        exp_num_bytes_ret = 8
    else:
        num_vals = num_regs_bw(num_vals)  # check if lng is in correct interval

        if mb_func in (1, 2):
            num_regs = num_vals
        elif data_type in FOUR_BYTE_FORMATS:  # ('float', 'uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32'):
            num_regs = num_vals * 2
        elif data_type in SIX_BYTE_FORMATS:  # ('uint48', 'sint48'):
            num_regs = num_vals * 3
        elif data_type in EIGHT_BYTE_FORMATS:  # ('mod30k', 'uint64', 'engy', 'dbl'):
            num_regs = num_vals * 4
        elif data_type in ONE_BYTE_FORMATS:  # ('uint8', 'sint8'):
            num_regs = (num_vals + 1) // 2
        else:
            num_regs = num_vals

        if mb_func in (1, 2):
            exp_num_bytes_ret = 5 + ((num_regs + 7) // 8)  # number of bytes converted from number of bits
        else:
            exp_num_bytes_ret = 5 + num_regs * 2  # number of bytes expected in return for com port
    return exp_num_bytes_ret, num_regs


def make_csv_header(mb_func, start_reg_zero, num_vals, num_regs, data_type):
    if mb_func in (1, 2):
        csv_header = range(start_reg_zero, start_reg_zero + num_vals)
    elif data_type in ONE_BYTE_FORMATS:  # ('uint8', 'sint8'):
        csv_header = [x / 2 + start_reg_zero for x in range(0, num_regs * 2)]  # should work
    elif data_type in TWO_BYTE_FORMATS:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
        csv_header = range(start_reg_zero, start_reg_zero + num_regs)
    elif data_type in FOUR_BYTE_FORMATS:  # ('uint32', 'sint32', 'float', 'mod1k', 'mod10k'):
        csv_header = range(start_reg_zero, start_reg_zero + num_regs)[::2]
    elif data_type in SIX_BYTE_FORMATS:  # 'mod20k':
        csv_header = range(start_reg_zero, start_reg_zero + num_regs)[::3]
    else:  # ('uint64', 'mod30k', 'engy', 'dbl')
        csv_header = range(start_reg_zero, start_reg_zero + num_regs)[::4]
    csv_header = list(csv_header)
    # csv_header.insert(0, None)
    csv_header.insert(0, 'Datetime')
    return csv_header


def make_request_packet(serial_port, b_write_mb, mb_id, mb_func, start_reg_zero, val_to_write, num_regs):
    packet_write_list = None
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
                    return MB_ERR_DICT[3]

                req_packet[5] = 0x00
            else:
                req_packet[4] = (val_to_write >> 8) & 0xFF   # value to write to read high byte
                req_packet[5] = val_to_write & 0xFF          # value to write to read low byte

            packet_write_list = list(req_packet)
        else:
            req_packet[4] = (num_regs >> 8) & 0xFF   # starting length to read high byte
            req_packet[5] = num_regs & 0xFF          # starting length to read low byte

        req_packet.extend(calc_crc_byte_array(req_packet))
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

    return req_packet, packet_write_list


def set_rpi_pin_tx(pi_pin_cntl):
    if pi_pin_cntl is not None and B_RPI_GPIO_EXISTS:
        GPIO.output(pi_pin_cntl, GPIO.LOW)


def set_rpi_pin_rx(pi_pin_cntl):
    if pi_pin_cntl is not None and B_RPI_GPIO_EXISTS:
        GPIO.output(pi_pin_cntl, GPIO.HIGH)


def verify_no_comm_errs(serial_port, recv_packet_bytearr, verbosity, num_prnt_rws):
    error_code = None
    recv_packet = None

    if serial_port is not None:  # using com port!
        if recv_packet_bytearr:  # recv_packet_bytearr != []:
            # print(list(rec_packet_bytearr))
            recv_packet = list(recv_packet_bytearr[:-2])

            if calc_crc_byte_array(recv_packet) != recv_packet_bytearr[-2:]:
                error_code = MB_ERR_DICT[113]
        else:
            error_code = MB_ERR_DICT[87]
    else:  # using ethernet!
        if len(recv_packet_bytearr) > 6:
            if recv_packet_bytearr[0] >= 0:
                tcp_hdr_exp_len = int.from_bytes(recv_packet_bytearr[4:6], byteorder='big')
                # print(list(packetbt), '\n'*rws, end='')
                if tcp_hdr_exp_len == (len(recv_packet_bytearr) - 6):
                    recv_packet = list(recv_packet_bytearr[6:])
                    # print(packetrec)
                else:
                    error_code = MB_ERR_DICT[108]  # UNEXPECTED MODBUS MESSAGE LENGTH

                    try:
                        print('Possible ASCII message returned:', recv_packet_bytearr.decode('ascii'),
                              '\n' * num_prnt_rws, end='')
                    except UnicodeDecodeError:
                        print('Possible ASCII message returned:', list(recv_packet_bytearr), '\n' * num_prnt_rws,
                              end='')
            else:
                if verbosity is not None:
                    try:
                        print(recv_packet_bytearr.decode('ascii'), '\n' * num_prnt_rws, end='')
                    except UnicodeDecodeError:
                        print(list(recv_packet_bytearr), '\n' * num_prnt_rws, end='')
                error_code = MB_ERR_DICT[106]  # UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER
                # break
        else:  # TCP message <6
            print('Partial TCP message returned of length', len(recv_packet_bytearr))
            error_code = MB_ERR_DICT[106]  # UNEXPECTED RETURN DATA, SOCKET LIKELY CLOSED BY OTHER
            # break

    return error_code, recv_packet


def verify_no_modbus_errs(recv_packet, mb_id, mb_func, val_to_write, b_write_mb, packet_write_list):
    error_code = None
    register_list = []

    if mb_id == recv_packet[0] or recv_packet[0] == 0:  # check modbus device
        if recv_packet[1] == mb_func:  # check modbus function
            if b_write_mb:  # if write command, will have different checks
                if packet_write_list == recv_packet:
                    if mb_func == 6:
                        register_list = recv_packet[4:]
                    else:
                        register_list = [0, val_to_write]
                else:
                    error_code = MB_ERR_DICT[111]
            else:
                if recv_packet[2] == (len(recv_packet) - 3):  # check length of modbus message
                    register_list = recv_packet[3:]
                else:
                    error_code = MB_ERR_DICT[109]  # UNEXPECTED MODBUS MESSAGE LENGTH
        elif recv_packet[1] == (mb_func + 128) or recv_packet[1] == 128:  # check for error return
            error_code = MB_ERR_DICT[recv_packet[2]]
        else:
            error_code = MB_ERR_DICT[110]  # UNEXPECTED MODBUS FUNCTION RETURNED
    else:
        error_code = MB_ERR_DICT[111]  # UNEXPECTED MODBUS SLAVE DEVICE MESSAGE

    return error_code, register_list


def tick_poll_and_wait(cur_poll, num_polls, b_poll_forever, poll_start_time, poll_delay):
    new_cur_poll = cur_poll + 1
    new_num_polls = num_polls
    if b_poll_forever:
        new_num_polls += 1

    # sleep for the rest of poll delay
    if new_cur_poll != new_num_polls + 1:
        time.sleep(max(0, poll_start_time + poll_delay / 1000 - time.time()))

    return new_cur_poll, new_num_polls


# run script
def mb_poll(ip, mb_id, start_reg, num_vals, b_help=False, num_polls=1, data_type='float', b_byteswap=False,
            b_wordswap=False, zero_based=False, mb_timeout=1500, file_name_input=None, verbosity=None, port=502,
            poll_delay=1000, mb_func=3, pi_pin_cntl=None, b_raw_bytes=False):

    if b_help:
        print('Polls a modbus device through network.',
              '\nip:          The IP address of the gateway or the com port (comX)',
              '\nmb_id:       The id number of the desired device.',
              '\nstart_reg:   The address of the first register desired.',
              '\nnum_vals:    The number of outputs to return (certain types will use 2 or 4 registers per output).',
              '\nnum_polls:   The number of polls. Default is 1.',
              '\ndata_type:   The desired type to be returned.',
              '\nb_byteswap:  Sets byteswap to true.  Default is Big Endian (False).',
              '\nb_wordswap:  Sets wordswap to true.  Default is Little Endian (False).',
              '\nzero_based:  Interprets starting address as 0-based value.  If not set then',
              '\n                 setting srt=2 looks at 1 (second register).  If set then setting',
              '\n                 srt=2 looks at 2 (third register) (Default is 1, else 0).',
              '\nmb_timeout:  Time in milliseconds to wait for reply message. Default is 1500.'
              '\nfile_name:   Generates csv file in current folder.',
              '\nverbosity:   Verbosity options. 1: Static display  2: Consecutive display  3: Static + progress bar '
              '\n                 4: Consecutive + progress bar',
              '\nport:        Set port to communicate over.  Default is 502.'
              '\npoll_delay:  Delay in ms to let function sleep to retrieve reasonable data.  Default is 1000.'
              '\nmb_func:     Modbus function. Default is 3.'
              '\npi_pin_cntl: Raspberry Pi GPIO pin (using BOARD pinouts) for Tx control of 485 chip.  If None, then '
              '\nb_raw_bytes: Returns bytes after accounting for word and byte swaps.'
              )
        return

    ip, serial_port, error_code = validate_ip(ip)
    if error_code is not None:
        return error_code

    # check certain things if called through script rather than commandline
    if not B_CMD_LINE:
        mb_id, error_code = validate_device_id(mb_id)
        if error_code is not None:
            return error_code

        start_reg, error_code = validate_register(start_reg)
        if error_code is not None:
            return error_code

        mb_timeout, error_code = validate_timeout(mb_timeout)
        if error_code is not None:
            return error_code

        data_type, error_code = validate_data_type(data_type)
        if error_code is not None:
            return error_code

        port = int(port)

        mb_func, error_code = validate_modbus_function(mb_func)
        if error_code is not None:
            return error_code

        pi_pin_cntl, error_code = validate_cntl_pin(pi_pin_cntl)
        if error_code is not None:
            return error_code
        if pi_pin_cntl is not None and B_RPI_GPIO_EXISTS:
            GPIO.setup(pi_pin_cntl, GPIO.OUT)

    mb_timeout /= 1000  # mb_timeout / 1000  # convert from ms to s
    val_to_write = None

    # check if read or write
    if mb_func in (5, 6, 16):
        b_write_mb = True
        poll_delay = 0
        val_to_write, error_code = validate_write_value(num_vals)
        if error_code is not None:
            return error_code
    else:
        b_write_mb = False

    exp_num_bytes_ret, num_regs = get_expected_num_ret_bytes(b_write_mb, mb_func, num_vals, data_type)

    # check if zero based and starting register will work
    start_reg_zero = start_reg - (not zero_based)
    if start_reg_zero < 0:
        return MB_ERR_DICT[103]  # raise ValueError('Invalid register lookup.')

    # check if infinite polling
    if num_polls != 1 and b_write_mb:
        return MB_ERR_DICT[112]  # shouldn't have multiple polls for a write command
    else:
        if num_polls < 1:  # poll forever
            print('Ctrl-C to exit.')
            b_poll_forever = True
            num_polls = 1
        elif num_polls == 1:  # single poll
            b_poll_forever = False
        else:  # multiple polls
            b_poll_forever = False

    # check filename for validity
    file_name = validate_file_name(file_name_input)

    # check os to determine if there will be a problem with different print options
    if verbosity in (1, 3):
        if os.name == 'nt':  # if static print is called, this can't be implemented in windows, give other options
            if not B_CMD_LINE:
                verbosity = None  # not called from commandline, no guarantee to respond to input
            else:
                while verbosity in (1, 3):
                    verbosity = int(input('Please choose from [0, 2, 4] (blank, consecutive, cons + progress bar): '))

                if verbosity == 0:
                    verbosity = None
        else:
            if b_write_mb:
                num_prnt_rws = 2
            elif b_raw_bytes:
                num_prnt_rws = num_regs * 2 + 1
            else:
                num_prnt_rws = num_vals + 1

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

    mb_data = ModbusData(start_reg, num_vals, b_byteswap, b_wordswap, verbosity, data_type, mb_func,
                         b_raw_bytes=b_raw_bytes)

    if file_name_input is not None:
        try:
            csv_file = open(file_name, 'w', newline='')
        except IOError:
            return MB_ERR_DICT[105]
        else:
            csv_file_wrtr = csv.writer(csv_file)
            csv_header = make_csv_header(mb_func, start_reg_zero, num_vals, num_regs, data_type)
            csv_file_wrtr.writerow(csv_header)
    else:
        csv_file = None
        csv_file_wrtr = None

    # ~ #create packet here:
    req_packet, packet_write_list = make_request_packet(serial_port, b_write_mb, mb_id, mb_func, start_reg_zero,
                                                        val_to_write, num_regs)

    serial_conn = None

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_conn:
        tcp_conn.settimeout(mb_timeout)

        if serial_port is not None:  # COM port
            b_open_serial_port = False
            start_serial_time = time.time()

            while not b_open_serial_port:
                if time.time() - start_serial_time > mb_timeout:
                    return MB_ERR_DICT[115]  # port was busy for duration of timeout
                try:
                    serial_conn = serial.Serial(serial_port, timeout=mb_timeout, baudrate=9600, exclusive=True)
                except serial.serialutil.SerialException:
                    pass  # port is busy
                else:
                    b_open_serial_port = True
                    set_rpi_pin_tx(pi_pin_cntl)
        else:
            try:
                tcp_conn.connect((ip, port))

            except socket.timeout:
                if verbosity is not None:
                    print('Connection could not be made with gateway.  Timed out after 5 seconds.')
                return MB_ERR_DICT[19]
            except socket.error:
                return MB_ERR_DICT[19]

            tcp_conn.setblocking(0)
        valid_polls = 0

        cur_poll = 1
        while cur_poll < num_polls + 1:
            try:
                if serial_port is not None:  # COM port
                    set_rpi_pin_tx(pi_pin_cntl)

                    serial_conn.reset_input_buffer()
                    serial_conn.write(req_packet)  # send msg

                    set_rpi_pin_rx(pi_pin_cntl)
                else:
                    # clear Rx buffer !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    tcp_conn.sendall(req_packet)  # send modbus request

                if verbosity in (1, 3):
                    print('\x1b[', num_prnt_rws + 1, 'F' + ERASE_LINE, sep='', end='\r')

                if verbosity is not None:
                    print('\nPoll', cur_poll, 'at:', str(datetime.now()))

                poll_start_time = time.time()

                if serial_port is not None:  # using com port!
                    recv_packet_bytearr = serial_conn.read(exp_num_bytes_ret)  # blocks for mb_timeout seconds

                    set_rpi_pin_tx(pi_pin_cntl)
                else:  # using ethernet!
                    select_inputs = select.select([tcp_conn], [], [], mb_timeout)[0]

                    if select_inputs:  # select_inputs != []:
                        try:
                            recv_packet_bytearr = tcp_conn.recv(1024, )  # gives bytes type
                        except socket.timeout:
                            print('socket timeout')
                            mb_data.set_error(87)
                            break
                        except socket.error as r:
                            print(r)
                            mb_data.set_error(87)
                            break
                    else:  # select timed out
                        mb_data.set_error(87)
                        # b_conn_err = True
                        print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                            prog_bar_len, num_polls, 87)
                        cur_poll, num_polls = tick_poll_and_wait(cur_poll, num_polls, b_poll_forever, poll_start_time,
                                                                 poll_delay)
                        continue  # start next loop

                error_code, recv_packet = verify_no_comm_errs(serial_port, recv_packet_bytearr, verbosity, num_prnt_rws)

                if error_code is not None:
                    mb_data.set_error(error_code[1])
                    if error_code[1] == 106:
                        break
                    elif error_code[1] != 108:
                        print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                            prog_bar_len, num_polls, error_code[1])
                else:
                    error_code, register_list = verify_no_modbus_errs(recv_packet, mb_id, mb_func, val_to_write,
                                                                      b_write_mb, packet_write_list)

                    if error_code is not None:
                        mb_data.set_error(error_code[1])
                        print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                            prog_bar_len, num_polls, error_code[1])
                    else:
                        mb_data.translate_regs_to_vals(register_list)

                        if csv_file_wrtr is not None:
                            mb_data.insert_datetime()
                            csv_file_wrtr.writerow(mb_data.get_value_array())

                        valid_polls += 1
                        print_errs_prog_bar(verbosity, cur_poll, num_prnt_rws, b_poll_forever, valid_polls,
                                            prog_bar_len, num_polls)

                cur_poll, num_polls = tick_poll_and_wait(cur_poll, num_polls, b_poll_forever, poll_start_time,
                                                         poll_delay)
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

    if pi_pin_cntl is not None and B_RPI_GPIO_EXISTS:
        GPIO.cleanup()

    return mb_data.get_value_array()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Polls a modbus device through network.')

    parser.add_argument('ip', type=str, help='The IP address of the gateway or the comport (comX).')
    parser.add_argument('dev', type=device_bw, help='The id number of the desired device.')
    parser.add_argument('srt', type=register_bw, help='The address of the first register desired.')
    parser.add_argument('lng', type=int,
                        help='The number of registers to return (certain types will use 2 or 4 registers per output).')
    parser.add_argument('-p', '--poll', type=int, default=1, help='The number of polls. Default is 1.')
    parser.add_argument('-t', '--typ', type=str, default='float', choices=DATA_TYPE_LIST,
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
    parser.add_argument('-pin', '--pin_cntl', type=pin_cntl_bw, default=None,
                        help='Pin control for 485 chip on Raspberry Pi hat. Only used for serial.  Use Board pin '
                             'numbers.  Default is None.')
    parser.add_argument('-rb', '--raw_bytes', action='store_true',
                        help='Returns raw bytes after any necessary byte or word swaps.')

    args = parser.parse_args()

    B_CMD_LINE = True
    poll_results = mb_poll(args.ip, args.dev, args.srt, args.lng, num_polls=args.poll, data_type=args.typ,
                           b_byteswap=args.byteswap, b_wordswap=args.wordswap, zero_based=args.zbased,
                           mb_timeout=args.timeout, file_name_input=args.file, verbosity=args.verbose, port=args.port,
                           poll_delay=args.pdelay, mb_func=args.func, pi_pin_cntl=args.pin_cntl,
                           b_raw_bytes=args.raw_bytes)

    print(poll_results)
