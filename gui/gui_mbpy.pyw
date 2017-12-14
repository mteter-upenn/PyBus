#!/usr/bin/python3

from math import log10
# from mbpy.mb_poll import modbus_poller
import mbpy.mb_poll as mb_poll
from time import (sleep, time)
import threading
import queue
import csv
import os
import sys
import serial
import serial.tools.list_ports
from datetime import datetime
from tkinter import (Frame, Button, Entry, Label, Checkbutton, GROOVE, DISABLED, NORMAL, TclError, IntVar, StringVar, N,
                     W, E, S, NW, Tk, filedialog, messagebox, Toplevel, Image)  # , PhotoImage)
from tkinter.ttk import Combobox
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as dates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


def merge_dicts(*dict_args):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


# ONE_BYTE_FRMT_LIST = ('uint8', 'sint8')
# two_byte_frmt_list = ('uint16', 'sint16', 'sm1k16', 'sm10k16', 'bin', 'hex', 'ascii')
# four_byte_frmt_list = ('uint32', 'sint32', 'um1k32', 'sm1k32', 'um10k32', 'sm10k32', 'float')
# six_byte_frmt_list = ('uint48', 'um1k48', 'sm1k48', 'um10k48', 'sm10k48')  # 'sint48' is not supported
# eight_byte_frmt_list = ('uint64', 'sint64', 'um1k64', 'sm1k64', 'um10k64', 'sm10k64', 'dbl', 'engy')

ONE_BYTE_FORMAT_DICT = {'Unsigned Integer 8 bit': 'uint8', 'Signed Integer 8 Bit': 'sint8'}
TWO_BYTE_FORMAT_DICT = {'Binary 16 Bit': 'bin', 'Hexadecimal 16 Bit': 'hex', 'ASCII 16 Bit': 'ascii',
                        'Unsigned Integer 16 Bit': 'uint16', 'Signed Integer 16 Bit': 'sint16',
                        'Signed Mod 1K 16 Bit': 'sm1k16', 'Signed Mod 10K 16 Bit': 'sm10k16'}
FOUR_BYTE_FORMAT_DICT = {'Float 32 Bit': 'float', 'Unsigned Integer 32 Bit': 'uint32',
                         'Signed Integer 32 Bit': 'sint32', 'Unsigned Mod 1K 32 Bit': 'um1k32',
                         'Signed Mod 1K 32 Bit': 'sm1k32', 'Unsigned Mod 10K 32 Bit': 'um10k32',
                         'Signed Mod 10K 32 Bit': 'sm10k32'}
SIX_BYTE_FORMAT_DICT = {'Unsigned Integer 48 Bit': 'uint48', 'Unsigned Mod 1K 48 Bit': 'um1k48',
                        'Signed Mod 1K 48 Bit': 'sm1k48', 'Unsigned Mod 10K 48 Bit': 'um10k48',
                        'Signed Mod 10K 48 Bit': 'sm10k48'}  # 'sint48' is not supported
EIGHT_BYTE_FORMAT_DICT = {'Double 64 Bit': 'dbl', 'Eaton Energy 64 Bit': 'engy', 'Unsigned Integer 64 Bit': 'uint64',
                          'Signed Integer 64 Bit': 'sint64', 'Unsigned Mod 1K 64 Bit': 'um1k64',
                          'Signed Mod 1K 64 Bit': 'sm1k64', 'Unsigned Mod 10K 64 Bit': 'um10k64',
                          'Signed Mod 10K 64 Bit': 'sm10k64'}

DATA_TYPE_DICT = merge_dicts(ONE_BYTE_FORMAT_DICT, TWO_BYTE_FORMAT_DICT, FOUR_BYTE_FORMAT_DICT, SIX_BYTE_FORMAT_DICT,
                             EIGHT_BYTE_FORMAT_DICT)


def change_all_children_state(child_list, state):
    for child in child_list:
        try:
            child.configure(state=state)
        except TclError:
            pass


def scale_axis(axis_low_val, axis_high_val, arrow_key, b_ctrl_key):
    otpt = [axis_low_val, axis_high_val]

    if arrow_key in ('Up', 'Down', 'Left', 'Right'):  # , 'ctrl+Up', 'ctrl+Down', 'ctrl+Left', 'ctrl+Right'):
        axis_len = abs(axis_low_val - axis_high_val) * 0.1
        
        if b_ctrl_key:  # if ctrl is selected
            low_val_dict = {'Up': 1, 'Down': -1, 'Left': -1, 'Right': 1}
            high_val_dict = {'Up': -1, 'Down': 1, 'Left': 1, 'Right': -1}
        else:
            low_val_dict = {'Up': 1, 'Down': -1, 'Left': -1, 'Right': 1}
            high_val_dict = {'Up': 1, 'Down': -1, 'Left': -1, 'Right': 1}

        if axis_high_val > axis_low_val:
            otpt = [axis_low_val + low_val_dict[arrow_key] * axis_len, axis_high_val + high_val_dict[arrow_key] *
                    axis_len]
        else:
            otpt = [axis_low_val - (low_val_dict[arrow_key] * axis_len), axis_high_val - (high_val_dict[arrow_key] *
                                                                                          axis_len)]
    else:
        pass

    return otpt


def _quit():
    root.quit()
    root.destroy()


class InputApp:
    def __init__(self, mstr):
        self.mstr = mstr
        self.display_app = DisplayApp(mstr)
        # Frame widgets
        self.input_frame = Frame(mstr, bd=2, relief=GROOVE)
        button_frame = Frame(self.input_frame)
        # self.ex_frame = Frame(mstr)

        self.input_frame.grid(padx=5, pady=5)
        button_frame.grid(row=0, column=6, rowspan=2, columnspan=3)  # , padx=5, pady=5, sticky=NW)
        # self.ex_frame.grid(row=1, columnspan=2)
        # self.ex_frame.grid_remove()

        # Variables
        self.var_graph_otpt = IntVar()
        self.var_ip = StringVar()
        self.var_mbid = StringVar()
        self.var_poll_delay = StringVar()
        self.var_start_reg = StringVar()
        self.var_num_vals = StringVar()
        self.var_byte_swap = IntVar()
        self.var_word_swap = IntVar()
        self.var_data_type = StringVar()
        # self.v_pts = StringVar()
        self.var_port = StringVar()

        self.b_ip_good = False
        self.b_mbid_good = False
        self.b_start_reg_good = True
        self.b_num_vals_good = True
        self.b_poll_delay_good = True
        # self.pts_gd = True
        self.b_graph_otpt_good = True

        # Labels
        Label(self.input_frame, text='IP:').grid(row=0, column=0, sticky=W)
        Label(self.input_frame, text='Device:').grid(row=1, column=0, sticky=W)
        Label(self.input_frame, text='Data Type:').grid(row=2, column=0, sticky=W)
        Label(self.input_frame, text='Starting Register:').grid(row=0, column=2, sticky=W)
        self.l_num_vals = Label(self.input_frame, text='Number of Outputs:', width=16, anchor=W)
        Label(self.input_frame, text='Graph Output:').grid(row=2, column=2, sticky=W)
        Label(self.input_frame, text='Poll Delay (ms):').grid(row=2, column=6, sticky=W)
        Label(self.input_frame, text='Byte Swap:').grid(row=1, column=4, sticky=W)
        Label(self.input_frame, text='Word Swap:').grid(row=2, column=4, sticky=W)
        Label(self.input_frame, text='Port:').grid(row=0, column=4, sticky=W)

    # Entry widgets
        self.e_ip = Entry(self.input_frame, width=22, textvariable=self.var_ip)
        self.e_mbid = Entry(self.input_frame, width=22, textvariable=self.var_mbid)
        self.e_start_reg = Entry(self.input_frame, width=6, textvariable=self.var_start_reg)
        self.e_num_vals = Entry(self.input_frame, width=6, textvariable=self.var_num_vals)
        self.e_poll_delay = Entry(self.input_frame, width=6, textvariable=self.var_poll_delay)
        self.e_port = Entry(self.input_frame, width=6, textvariable=self.var_port)
    # Checkbutton widgets
        # .select and .deselect to change value
        ch_byte_swap = Checkbutton(self.input_frame, variable=self.var_byte_swap)
        ch_word_swap = Checkbutton(self.input_frame, variable=self.var_word_swap)
        self.ch_graph_otpt = Checkbutton(self.input_frame, variable=self.var_graph_otpt)
    # Combobox widget
        cb_data_type = Combobox(self.input_frame, width=21, height=11, textvariable=self.var_data_type)
    # Button widgets
        self.btn_start = Button(button_frame, text='Start Polling', width=15, state=DISABLED,
                                command=self.start_polling)
        self.btn_stop = Button(button_frame, text='Stop Polling', width=15, state=DISABLED, command=self.stop_polling)
        self.btn_func = Button(self.input_frame, text='Function 3', command=self.change_mb_function)

    # Entry widget default values
        self.e_poll_delay.insert(0, 1000)
        self.e_start_reg.insert(0, 1)
        self.e_num_vals.insert(0, 1)
        self.e_port.insert(0, 502)
    # Combobox defualt values
        cb_data_type['values'] = ('Binary 16 Bit', 'Hexadecimal 16 Bit', 'ASCII 16 Bit', 'Float 32 Bit',
                                  'Double 64 Bit', 'Eaton Energy 64 Bit',
                                  'Unsigned Integer  8 Bit', 'Unsigned Integer 16 Bit', 'Unsigned Integer 32 Bit',
                                  'Unsigned Integer 48 Bit', 'Unsigned Integer 64 Bit',
                                  'Signed Integer  8 Bit', 'Signed Integer 16 Bit', 'Signed Integer 32 Bit',
                                  'Signed Integer 48 Bit', 'Signed Integer 64 Bit',
                                  'Unsigned Mod 1K 32 Bit', 'Unsigned Mod 1K 48 Bit', 'Unsigned Mod 1K 64 Bit',
                                  'Signed Mod 1K 16 Bit', 'Signed Mod 1K 32 Bit', 'Signed Mod 1K 48 Bit',
                                  'Signed Mod 1K 64 Bit',
                                  'Unsigned Mod 10K 32 Bit', 'Unsigned Mod 10K 48 Bit', 'Unsigned Mod 10K 64 Bit',
                                  'Signed Mod 10K 16 Bit', 'Signed Mod 10K 32 Bit', 'Signed Mod 10K 48 Bit',
                                  'Signed Mod 10K 64 Bit')

        cb_data_type.current(3)

    # Label widget grid
        self.l_num_vals.grid(row=1, column=2, sticky=W)
    # Entry widget grid
        self.e_ip.grid(row=0, column=1, padx=(0, 10), pady=(5, 0))
        self.e_mbid.grid(row=1, column=1, padx=(0, 10))
        self.e_start_reg.grid(row=0, column=3, padx=(0, 10), pady=(5, 0))
        self.e_num_vals.grid(row=1, column=3, padx=(0, 10))
        self.e_poll_delay.grid(row=2, column=7, pady=(0, 10), sticky=W)
        self.e_port.grid(row=0, column=5, padx=(0, 5), pady=(5, 0))
    # Checkbutton grid
        ch_byte_swap.grid(row=1, column=5)
        ch_word_swap.grid(row=2, column=5)
        self.ch_graph_otpt.grid(row=2, column=3)
    # Combobox grid
        cb_data_type.grid(row=2, column=1, padx=(0, 10))
    # Button grid
        self.btn_start.grid(row=0, column=0, padx=5, pady=5)
        self.btn_stop.grid(row=0, column=1, padx=5, pady=5)
        self.btn_func.grid(row=2, column=8, padx=(0, 5), pady=(0, 10), sticky=W + E)

    # Bindings
        self.var_ip.trace('w', self.verify_ip)
        self.var_mbid.trace('w', self.verify_mbid)
        self.var_start_reg.trace('w', self.verify_start_reg)
        self.var_num_vals.trace('w', self.verify_num_vals)
        self.var_poll_delay.trace('w', self.verify_poll_delay)
        self.var_graph_otpt.trace('w', self.verify_num_vals)

    # Set variables for testing
        self.var_ip.set('10.166.6.67')
        self.var_mbid.set(9)

        self.mb_func = 3
    #     self.v_ip.set('130.91.147.20')
    #     self.v_dev.set(10)

    def start_polling(self):
        self.btn_start.configure(state=DISABLED)
        self.btn_stop.configure(state=NORMAL)
        change_all_children_state(self.input_frame.winfo_children(), DISABLED)
        self.display_app.display_otpt_frame(self.var_graph_otpt.get(), self.var_ip.get(), self.var_mbid.get(),
                                            self.var_start_reg.get(), self.var_num_vals.get(),
                                            DATA_TYPE_DICT[self.var_data_type.get()], self.var_byte_swap.get(),
                                            self.var_word_swap.get(), self.var_poll_delay.get(), self.var_port.get(),
                                            self.mb_func)

    def stop_polling(self):
        self.btn_start.configure(state=NORMAL)
        self.btn_stop.configure(state=DISABLED)
        change_all_children_state(self.input_frame.winfo_children(), NORMAL)

        self.display_app.remove_otpt_frame(self.var_graph_otpt.get())

    def change_mb_function(self):
        self.mb_func = ((self.mb_func - 2) % 4) + 3  # rotate through funcs 3, 4, 5, 6
        func_btn_text = 'Function ' + str(self.mb_func)
        self.btn_func.configure(text=func_btn_text)

        if self.mb_func in (5, 6):
            self.l_num_vals.configure(text='Value to write:')
            self.ch_graph_otpt.configure(fg='red')
            self.b_graph_otpt_good = False
        else:
            self.l_num_vals.configure(text='Number of Outputs:')
            self.ch_graph_otpt.configure(fg='black')
            self.b_graph_otpt_good = True

        self.verify_num_vals()

    def verify_ip(self, *args):
        split_ip_arr = self.var_ip.get().split(".")
        b_ip_flag = True

        if len(split_ip_arr) != 4:
            if len(split_ip_arr) == 1:
                if os.name == 'nt':
                    comports = list(serial.tools.list_ports.comports())
                    port_name = self.var_ip.get().upper()

                    for ports in comports:
                        if port_name == ports[0]:
                            # cmpt = int(ip[3:]) - 1
                            break
                    else:
                        b_ip_flag = False
                else:
                    # going on faith alone at this point that the correct serial address is being used on a linux system
                    pass
            else:
                b_ip_flag = False
        else:
            for ch in split_ip_arr:
                try:
                    if ch == '':
                        b_ip_flag = False
                        break
                    if int(ch) > 255 or int(ch) < 0:
                        b_ip_flag = False
                        break
                except ValueError:
                    b_ip_flag = False
                    break

        if b_ip_flag:
            self.e_ip.configure(fg='black')
            self.b_ip_good = True
        else:
            self.e_ip.configure(fg='red')
            self.b_ip_good = False

        self.verify_all_flags()

    def verify_mbid(self, *args):
        b_mbid_flag = True
        try:
            mbid = int(self.var_mbid.get())
        except ValueError:
            b_mbid_flag = False
        else:
            if mbid < 1 or mbid > 255:
                b_mbid_flag = False

        if b_mbid_flag:
            self.e_mbid.configure(fg='black')
            self.b_mbid_good = True
        else:
            self.e_mbid.configure(fg='red')
            self.b_mbid_good = False

        self.verify_all_flags()

    def verify_start_reg(self, *args):
        b_start_reg_flag = True
        try:
            start_reg = int(self.var_start_reg.get())
        except ValueError:
            b_start_reg_flag = False
        else:
            if start_reg < 0 or start_reg > 99999:
                b_start_reg_flag = False

        if b_start_reg_flag:
            self.e_start_reg.configure(fg='black')
            self.b_start_reg_good = True
        else:
            self.e_start_reg.configure(fg='red')
            self.b_start_reg_good = False

        self.verify_all_flags()

    def verify_num_vals(self, *args):
        b_num_vals_flag = True
        try:
            num_vals = int(self.var_num_vals.get())
        except ValueError:
            b_num_vals_flag = False
        else:
            if self.mb_func in (3, 4):
                if self.var_graph_otpt.get():
                    max_num_vals = 4
                else:
                    max_num_vals = 80

                if num_vals < 1 or num_vals > max_num_vals:
                    b_num_vals_flag = False
            elif self.mb_func == 5:  # only 1 or 0
                if num_vals not in (0, 1):
                    b_num_vals_flag = False
            elif self.mb_func == 6:
                if num_vals < 0 or num_vals > 65535:
                    b_num_vals_flag = False
            else:
                b_num_vals_flag = False

        if b_num_vals_flag:
            self.e_num_vals.configure(fg='black')
            self.b_num_vals_good = True

            if self.var_graph_otpt.get():
                if self.mb_func in (3, 4):
                    self.ch_graph_otpt.configure(fg='black')
                    self.b_graph_otpt_good = True
            else:
                self.ch_graph_otpt.configure(fg='black')
                self.b_graph_otpt_good = True
        else:
            self.e_num_vals.configure(fg='red')
            self.ch_graph_otpt.configure(fg='red')
            self.b_num_vals_good = False
            self.b_graph_otpt_good = False

        self.verify_all_flags()

    def verify_poll_delay(self, *args):
        b_poll_delay_flag = True
        try:
            poll_delay = int(self.var_poll_delay.get())
        except ValueError:
            b_poll_delay_flag = False
        else:
            if poll_delay < 0 or poll_delay > 600000:  # less than 10 minutes
                b_poll_delay_flag = False

        if b_poll_delay_flag:
            self.e_poll_delay.configure(fg='black')
            self.b_poll_delay_good = True
        else:
            self.e_poll_delay.configure(fg='red')
            self.b_poll_delay_good = False

        self.verify_all_flags()

    def verify_all_flags(self):
        if self.b_ip_good and self.b_mbid_good and self.b_start_reg_good and self.b_num_vals_good and \
                self.b_poll_delay_good and self.b_graph_otpt_good:
            self.btn_start.configure(state=NORMAL)
        else:
            self.btn_start.configure(state=DISABLED)


class DisplayApp:
    def __init__(self, mstr):
        self.mstr = mstr

        self.text_mstr_frame = Frame(mstr, bd=2, relief=GROOVE)
        self.text_btn_subfrm = Frame(self.text_mstr_frame, bd=2, relief=GROOVE)
        self.text_otpt_subfrm = Frame(self.text_mstr_frame)

        self.text_mstr_frame.grid(row=1, column=0, sticky=W + E, padx=5, pady=5)
        self.text_btn_subfrm.grid(row=0, column=0, padx=(0, 10), sticky=NW)
        self.text_otpt_subfrm.grid(row=0, column=1, sticky=W + E + N + S)
        self.text_mstr_frame.grid_remove()

    # graph frame
        self.graph_mstr_frame = Frame(mstr, bd=2, relief=GROOVE)
        self.graph_btn_subfrm = Frame(self.graph_mstr_frame, bd=2, relief=GROOVE)
        self.graph_figure = plt.figure(1, figsize=(6.2, 5), dpi=100, tight_layout=True)
        self.graph_canvas = FigureCanvasTkAgg(self.graph_figure, master=self.graph_mstr_frame)
        self.graph_canvas.show()

        # self.canvas.mpl_connect('key_press_event', self.on_key_event)

        self.graph_mstr_frame.grid(row=1, columnspan=2, sticky=W + E, padx=5, pady=5)
        self.graph_btn_subfrm.grid(row=0, column=0, sticky=NW, padx=(0, 10))
        self.graph_canvas.get_tk_widget().grid(row=0, column=1)
        self.graph_mstr_frame.grid_remove()

    # text frame widgets
        self.l_mb_err = Label(self.text_btn_subfrm, text='Err: None', anchor=W)
        self.l_tot_polls = Label(self.text_btn_subfrm, text='Total Polls: 0', anchor=W, width=13)
        self.l_val_polls = Label(self.text_btn_subfrm, text='Valid Polls: 0', anchor=W, width=13)

        self.btn_pause = Button(self.text_btn_subfrm, text='Pause', width=8, command=lambda: self.run_poller(True))
        self.btn_resume = Button(self.text_btn_subfrm, text='Resume', width=8, state=DISABLED,
                                 command=self.start_button)
        self.btn_reset_cntrs = Button(self.text_btn_subfrm, text='Reset Poll\nCounters', width=8, height=2,
                                      command=self.reset_cntrs)
        self.btn_save_data = Button(self.text_btn_subfrm, text='Save Data', width=8, state=DISABLED,
                                    command=self.save_data)

        self.btn_pause.grid(row=0, column=0, padx=5, pady=5)
        self.btn_resume.grid(row=1, column=0, padx=5, pady=5)
        self.l_mb_err.grid(row=2, column=0, sticky=W)
        self.l_tot_polls.grid(row=3, column=0, sticky=W)
        self.l_val_polls.grid(row=4, column=0, sticky=W)
        self.btn_reset_cntrs.grid(row=5, column=0, padx=5, pady=5)
        self.btn_save_data.grid(row=6, column=0, padx=5, pady=5)

    # graph frame widgets
        self.l_mb_err_g = Label(self.graph_btn_subfrm, text='Err: None')
        self.l_tot_polls_g = Label(self.graph_btn_subfrm, text='Total Polls: 0', anchor=W, width=15)
        self.l_val_polls_g = Label(self.graph_btn_subfrm, text='Valid Polls: 0', anchor=W, width=15)

        self.btn_pause_g = Button(self.graph_btn_subfrm, text='Pause', width=8, command=lambda: self.run_poller(True))
        self.btn_resume_g = Button(self.graph_btn_subfrm, text='Resume', width=8, state=DISABLED,
                                   command=self.start_button)
        self.btn_reset_cntrs_g = Button(self.graph_btn_subfrm, text='Reset Poll\nCounters', width=8, height=2,
                                        command=self.reset_cntrs)
        self.btn_adj_plt = Button(self.graph_btn_subfrm, text='All Plots\nAffected', width=8, height=2, state=DISABLED,
                                  command=self.change_active_plot)
        self.btn_save_plot_g = Button(self.graph_btn_subfrm, text='Save Graph', width=8, state=DISABLED,
                                      command=self.save_graph_figure)
        self.btn_save_data_g = Button(self.graph_btn_subfrm, text='Save Data', width=8, state=DISABLED,
                                      command=self.save_data)

        self.btn_pause_g.grid(row=0, column=0, padx=5, pady=5)
        self.btn_resume_g.grid(row=1, column=0, padx=5, pady=5)
        self.l_mb_err_g.grid(row=2, column=0)
        self.l_tot_polls_g.grid(row=3, column=0, sticky=W)
        self.l_val_polls_g.grid(row=4, column=0, sticky=W)
        self.btn_reset_cntrs_g.grid(row=5, column=0, padx=5, pady=5)
        self.btn_adj_plt.grid(row=10, column=0, padx=5, pady=5)
        self.btn_save_plot_g.grid(row=11, column=0, padx=5, pady=5)
        self.btn_save_data_g.grid(row=12, column=0, padx=5, pady=5)

    # variables
        self.otpt_lbls = []  # create dynamic list to handle unknown amount of outputs
        # self.otpt = [[] for _ in range(5)]
        self.otpt_data = []
        self.otpt_errs = []
        self.graph_figure.add_subplot(111)
        self.graph_figure.axes[0].set_autoscalex_on(False)
        self.graph_figure.autofmt_xdate(rotation=45)
        self.graph_figure.axes[0].xaxis.set_major_formatter(dates.DateFormatter('%m-%d %H:%M:%S'))
        self.plots = [None] * 4
        dum_plt, = self.graph_figure.axes[0].plot_date([], [], marker='', linestyle='-')
        self.plots[0] = dum_plt
        self.active_plot = 0  # 0 is all plots

        self.b_disp_graph = False
        self.poll_start_time = time()

        self.ip = '165.123.136.170'
        self.mbid = 9
        # self.ip = '130.91.147.20'
        # self.dev = 10
        self.start_reg = 1
        self.num_vals = 1
        self.data_type = 'float'
        self.poll_delay = 1000
        self.byte_swap = False
        self.word_swap = False
        self.port = 502
        self.mb_func = 3
        self.b_write_msg = False
        # self.typ = 'float'

        self.queue = None  # queue.PriorityQueue()
        self.queue_poll_delay = 99  # amount of time between queue checks
        self._job_mb_poller = None
        self.tot_polls = 0
        self.val_polls = 0

    def start_button(self):
        while not self.queue.empty():
            self.queue.get(block=False)
        self.run_poller(False)
        self.mstr.after(self.queue_poll_delay, self.process_queue)

    def run_poller(self, b_pause):
        if not b_pause:  # run task
            if self.b_disp_graph:
                self.btn_pause_g.configure(state=NORMAL)
                self.btn_resume_g.configure(state=DISABLED)
                self.btn_adj_plt.configure(state=DISABLED)
                self.btn_save_plot_g.configure(state=DISABLED)
                self.btn_save_data_g.configure(state=DISABLED)
            else:
                self.btn_pause.configure(state=NORMAL)
                self.btn_resume.configure(state=DISABLED)
                self.btn_save_data.configure(state=DISABLED)

            # self.queue = queue.Queue()
            self.poll_start_time = time()

            ModbusPollThreadedTask(self.queue, self.ip, self.mbid, self.start_reg, self.num_vals, self.data_type,
                                   self.byte_swap, self.word_swap, self.poll_delay,
                                   int((self.poll_start_time - time()) * 1000) + self.poll_delay - 50, self.port,
                                   self.mb_func).start()

            # self.mstr.after(self.tm, self.process_queue)
        else:  # pause task
            self.queue.put((0, 'Paused'))

    def process_queue(self):
        try:
            queue_msg = self.queue.get(block=False)
            queue_msg = queue_msg[1]
            # handle output ******************************************************************************************
            if queue_msg == 'Paused':
                # print(msg)
                if self._job_mb_poller is not None:
                    self.mstr.after_cancel(self._job_mb_poller)
                    self._job_mb_poller = None

                if self.b_disp_graph:
                    self.btn_pause_g.configure(state=DISABLED)
                else:
                    self.btn_pause.configure(state=DISABLED)
                self.mstr.update()

                # kill thread here?
                if threading.active_count() > 1:
                    wait_splash_screen = WaitSplash(self.mstr)
                    # top.update()

                    while threading.active_count() > 1:
                        # print('thread running on pause')
                        sleep(.05)
                    else:
                        wait_splash_screen.destroy()

                while not self.queue.empty():
                    self.queue.get(block=False)

                if self.b_disp_graph:
                    # self.b_pause_g.configure(state=DISABLED)
                    self.btn_resume_g.configure(state=NORMAL)
                    self.btn_adj_plt.configure(state=NORMAL)
                    self.btn_save_plot_g.configure(state=NORMAL)
                    self.btn_save_data_g.configure(state=NORMAL)
                else:
                    # self.b_pause.configure(state=DISABLED)
                    self.btn_resume.configure(state=NORMAL)
                    self.btn_save_data.configure(state=NORMAL)
                return
            else:
                # print(time(), threading.active_count())
                self.tot_polls += 1
                if self.b_disp_graph:  # graph data
                    if queue_msg[0] != 'Err':
                        self.val_polls += 1
                        self.l_mb_err_g.configure(text='Err: None')
                        self.write_otpt_to_labels(queue_msg)
                    else:
                        self.l_mb_err_g.configure(text='Err: ' + str(queue_msg[1]))
                        self.write_err(queue_msg)
                    self.l_tot_polls_g.configure(text='Total Polls: ' + str(self.tot_polls))
                    self.l_val_polls_g.configure(text='Valid Polls: ' + str(self.val_polls))
                else:  # no graph

                    # while (self.chk_tm + self.pd / 1000 - time()) > 0.02:
                    #     pass
                    if queue_msg[0] != 'Err':
                        self.val_polls += 1
                        self.l_mb_err.configure(text='Err: None')
                        self.write_otpt_to_labels(queue_msg)
                    else:
                        self.l_mb_err.configure(text='Err: ' + str(queue_msg[1]))
                        self.write_err(queue_msg)
                    self.l_tot_polls.configure(text='Total Polls: ' + str(self.tot_polls))
                    self.l_val_polls.configure(text='Valid Polls: ' + str(self.val_polls))

                self._job_mb_poller = self.mstr.after(max(0, int((self.poll_start_time - time()) * 1000) +
                                                          self.poll_delay), lambda: self.run_poller(self.b_write_msg))
                self.mstr.after(self.queue_poll_delay, self.process_queue)
        except queue.Empty:
            self.mstr.after(self.queue_poll_delay, self.process_queue)

    def display_otpt_frame(self, b_disp_graph, ip, mbid, start_reg=1, num_vals=1, data_type='float', b_byte_swap=False,
                           b_word_swap=False, poll_delay=1000, port=502, mb_func=3):
        self.tot_polls = 0
        self.val_polls = 0

        self.ip = ip
        self.mbid = mbid
        self.start_reg = int(start_reg)
        self.num_vals = int(num_vals)
        self.data_type = data_type
        self.byte_swap = b_byte_swap
        self.word_swap = b_word_swap
        self.poll_delay = int(poll_delay)
        self.port = port
        self.mb_func = mb_func
        # self.typ = typ

        if self.mb_func in (3, 4):
            self.b_write_msg = False
            num_otpts = self.num_vals
        else:
            self.b_write_msg = True
            num_otpts = 1

        self.otpt_data = [[] for _ in range(self.num_vals + 1)]
        self.otpt_errs = [[] for _ in range(3)]

        self.queue = queue.PriorityQueue()

        if b_disp_graph == 1:
            self.b_disp_graph = True
            self.active_plot = 0
            self.init_otpt_labels(num_otpts)

            self.mstr.bind('<Key>', self.on_key_event)
            self.mstr.bind('<Control-Up>', lambda e: self.on_key_event(e, True))
            self.mstr.bind('<Control-Left>', lambda e: self.on_key_event(e, True))
            self.mstr.bind('<Control-Right>', lambda e: self.on_key_event(e, True))
            self.mstr.bind('<Control-Down>', lambda e: self.on_key_event(e, True))

            self.graph_mstr_frame.grid()
            self.start_button()
        else:
            self.b_disp_graph = False
            self.init_otpt_labels(num_otpts)
            self.text_mstr_frame.grid()
            self.start_button()

    def remove_otpt_frame(self, b_show_graph):
        self.clear_labels()

        if b_show_graph == 1:
            self.mstr.unbind('<Key>')
            self.mstr.unbind('<Control-Up>')
            self.mstr.unbind('<Control-Left>')
            self.mstr.unbind('<Control-Right>')
            self.mstr.unbind('<Control-Down>')

            self.graph_mstr_frame.grid_remove()
        else:
            self.text_mstr_frame.grid_remove()

        self.otpt_data = []
        self.otpt_errs = []
        self.run_poller(True)

    def init_otpt_labels(self, num_otpts):
        start_reg = self.start_reg
        if self.data_type in mb_poll.TWO_BYTE_FORMATS:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
            regs_per_val = 1
        elif self.data_type in mb_poll.FOUR_BYTE_FORMATS:  # ('uint32', 'sint32', 'float', 'mod10k'):
            regs_per_val = 2
        elif self.data_type in mb_poll.SIX_BYTE_FORMATS:  # ('mod20k'):
            regs_per_val = 3
        else:  # ('mod30k', 'uint64', 'engy', 'dbl')
            regs_per_val = 4

        last_reg = start_reg + num_otpts * regs_per_val
        num_digits = max(int(log10(last_reg)) + 1, 4)

        if self.mb_func in (3, 6):
            start_reg += 4 * 10 ** num_digits  # 40000
        elif self.mb_func == 4:
            start_reg += 3 * 10 ** num_digits
        else:  # func 5
            start_reg += 1 * 10 ** num_digits

        if self.b_disp_graph:
            otpt_frame = self.graph_btn_subfrm
            row_offset = 6
            col_offset = 0

            prev_num_plots = len(self.graph_figure.axes)

            if prev_num_plots == num_otpts:
                pass  # don't need to change subplot geometry
            elif num_otpts < prev_num_plots:
                for ii in range(prev_num_plots - 1, num_otpts - 1, -1):
                    self.graph_figure.delaxes(self.graph_figure.axes[ii])
                    self.plots[ii] = None

                if num_otpts == 1:
                    self.graph_figure.axes[0].change_geometry(1, 1, 1)
                    plt.setp(self.graph_figure.axes[0].get_xticklabels(), visible=True)
                elif num_otpts == 2:
                    self.graph_figure.axes[0].change_geometry(2, 1, 1)
                    self.graph_figure.axes[1].change_geometry(2, 1, 2)
                    plt.setp(self.graph_figure.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.graph_figure.axes[1].get_xticklabels(), visible=True)
                else:
                    self.graph_figure.axes[0].change_geometry(2, 2, 1)
                    self.graph_figure.axes[1].change_geometry(2, 2, 2)
                    self.graph_figure.axes[2].change_geometry(2, 2, 3)
                    plt.setp(self.graph_figure.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.graph_figure.axes[1].get_xticklabels(), visible=True)
            else:  # cnt > pst_cnt
                for ii in range(prev_num_plots, num_otpts):
                    self.graph_figure.add_subplot(num_otpts, 1, ii + 1)
                    plt.setp(self.graph_figure.axes[ii].get_xticklabels(), rotation=45)
                    self.graph_figure.axes[ii].xaxis.set_major_formatter(dates.DateFormatter('%m-%d %H:%M:%S'))
                    dum_plt, = self.graph_figure.axes[ii].plot_date([], [], marker='', linestyle='-')
                    self.plots[ii] = dum_plt

                if num_otpts == 2:
                    self.graph_figure.axes[0].change_geometry(2, 1, 1)
                    self.graph_figure.axes[1].change_geometry(2, 1, 2)
                    plt.setp(self.graph_figure.axes[0].get_xticklabels(), visible=False)
                elif num_otpts == 3:
                    self.graph_figure.axes[0].change_geometry(2, 2, 1)
                    self.graph_figure.axes[1].change_geometry(2, 2, 2)
                    self.graph_figure.axes[2].change_geometry(2, 2, 3)
                    plt.setp(self.graph_figure.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.graph_figure.axes[1].get_xticklabels(), visible=True)
                else:
                    self.graph_figure.axes[0].change_geometry(2, 2, 1)
                    self.graph_figure.axes[1].change_geometry(2, 2, 2)
                    self.graph_figure.axes[2].change_geometry(2, 2, 3)
                    self.graph_figure.axes[3].change_geometry(2, 2, 4)
                    plt.setp(self.graph_figure.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.graph_figure.axes[1].get_xticklabels(), visible=False)

        else:
            otpt_frame = self.text_otpt_subfrm
            row_offset = 0
            col_offset = 10

        for ii in range(num_otpts):
            lbl_col = ii // 10
            lbl_row = (ii % 10) + row_offset
            reg_str = str(start_reg + ii * regs_per_val)
            self.otpt_data[ii].append(reg_str)

            lbl = Label(otpt_frame, text=reg_str + ': ', width=19, anchor=W)
            self.otpt_lbls.append(lbl)
            lbl.grid(row=lbl_row, column=lbl_col, padx=(0, col_offset), sticky=W)

        self.otpt_data[-1].append('Datetime')

        self.otpt_errs[0].append('Error Code')
        self.otpt_errs[1].append('Description')
        self.otpt_errs[2].append('Error Datetime')

    def clear_labels(self):
        for ii in range(len(self.otpt_lbls)):
            self.otpt_lbls[ii].destroy()
        self.otpt_lbls = []

        if self.b_disp_graph:
            self.l_mb_err_g.configure(text='Err: None')
            self.l_tot_polls_g.configure(text='Total Polls: 0')
            self.l_val_polls_g.configure(text='Valid Polls: 0')
        else:
            self.l_mb_err.configure(text='Err: None')
            self.l_tot_polls.configure(text='Total Polls: 0')
            self.l_val_polls.configure(text='Valid Polls: 0')

    def write_otpt_to_labels(self, data):
        if len(self.otpt_lbls) == len(data):
            # handle data
            for ii in range(len(self.otpt_lbls)):
                if self.data_type in ('bin', 'hex', 'ascii'):
                    otpt_str = self.otpt_lbls[ii].cget('text')[:7] + data[ii]
                elif self.data_type in ('float', 'dbl'):
                    otpt_str = self.otpt_lbls[ii].cget('text')[:7] + '%.2f' % data[ii]
                else:
                    otpt_str = self.otpt_lbls[ii].cget('text')[:7] + '%.0f' % data[ii]
                self.otpt_lbls[ii].configure(text=otpt_str)
                self.otpt_data[ii].append(data[ii])

            self.otpt_data[-1].append(dates.date2num(datetime.now()))

            if self.b_disp_graph:
                total_polls = len(self.otpt_data[0]) - 1

                if total_polls > 1:
                    for ii in range(self.num_vals):
                        if total_polls > 20:
                            minx = total_polls - 20
                        else:
                            minx = 1

                        # renew plot data
                        self.plots[ii].set_xdata(self.otpt_data[-1][1:])
                        self.plots[ii].set_ydata(self.otpt_data[ii][1:])

                        # reset axes
                        self.graph_figure.axes[ii].set_autoscaley_on(True)
                        self.graph_figure.axes[ii].relim()
                        self.graph_figure.axes[ii].set_xlim([self.otpt_data[-1][minx], self.otpt_data[-1][total_polls]])
                        self.graph_figure.axes[ii].autoscale_view()

                    self.graph_canvas.draw()

        else:
            pass

    def write_err(self, data):
        self.otpt_errs[0].append(data[1])
        self.otpt_errs[1].append(data[2])
        self.otpt_errs[2].append(dates.date2num(datetime.now()))

    def reset_cntrs(self):
        self.tot_polls = 0
        self.val_polls = 0

        if self.b_disp_graph:
            self.l_tot_polls_g.configure(text='Total Polls: ' + str(self.tot_polls))
            self.l_val_polls_g.configure(text='Valid Polls: ' + str(self.val_polls))
        else:
            self.l_tot_polls.configure(text='Total Polls: ' + str(self.tot_polls))
            self.l_val_polls.configure(text='Valid Polls: ' + str(self.val_polls))

    def save_graph_figure(self):
        # print(plt.gcf().canvas.get_supported_filetypes())
        ftypes = [('PNG', '.png'), ('SVG', '.svg'), ('SVG', '.svgz'), ('PDF', '.pdf'), ('PostScript', '.ps'),
                  ('Encapsulated PostScript', '.eps'), ('Raw Bitmap', '.rgba'), ('Raw Bitmap', '.raw'),
                  ('LaTeX', '.pgf')]
        graph_file = filedialog.asksaveasfilename(defaultextension='.png', filetypes=ftypes, parent=self.mstr)
        if graph_file != '':
            try:
                plt.savefig(graph_file, dpi=400)
            except IOError:
                messagebox.showerror('File Error', 'Plot could not be saved because file is already open!')

    def save_data(self):
        # print(os.getcwd())
        data_file = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '.csv')], parent=self.mstr)
        if data_file != '':
            try:
                csv_file = open(data_file, 'w', newline='')
            except IOError:
                messagebox.showerror('File Error', 'Data could not be written because file is already open!')
            else:
                csv_writer = csv.writer(csv_file)
                for rw in self.otpt_data:
                    csv_writer.writerow(rw)

                csv_writer.writerow([])

                for rw in self.otpt_errs:
                    csv_writer.writerow(rw)

    def change_active_plot(self):
        self.active_plot = (self.active_plot + 1) % (self.num_vals + 1)
        if self.active_plot == 0:
            self.btn_adj_plt.configure(text='All Plots\nAffected')
        else:
            self.btn_adj_plt.configure(text='Plot ' + str(self.active_plot) + '\nAffected')

    def on_key_event(self, event, ctrl=False):
        # print(self.flg_gph, self.b_pause_g.cget('state'), event.keysym, event.keycode)

        if self.b_disp_graph:
            if self.btn_pause_g.cget('state') == DISABLED:  # don't want to do this while the graphs are updating
                if self.active_plot == 0:
                    minax = 0
                    maxax = self.num_vals
                else:
                    minax = self.active_plot - 1
                    maxax = self.active_plot
        
                if event.keysym in ('Up', 'Down'):  # , 'ctrl+up', 'ctrl+down'):
                    for i in range(minax, maxax):
                        lw, hg = self.graph_figure.axes[i].get_ylim()
                        new_lim = scale_axis(lw, hg, event.keysym, ctrl)
                        self.graph_figure.axes[i].set_ylim(new_lim)
        
                    self.graph_canvas.draw()
                elif event.keysym in ('Left', 'Right'):  # , 'ctrl+left', 'ctrl+right'):
                    for i in range(minax, maxax):
                        lw, hg = self.graph_figure.axes[i].get_xlim()
                        new_lim = scale_axis(lw, hg, event.keysym, ctrl)
                        self.graph_figure.axes[i].set_xlim(new_lim)
        
                    self.graph_canvas.draw()
                elif event.keysym == 's':
                    self.save_graph_figure()
                elif event.keysym == 'w':
                    self.change_active_plot()
                elif event.keysym == 'g':
                    plt.grid()
                    self.graph_canvas.draw()
                elif event.keysym == 'r':
                    self.start_button()
            elif event.keysym == 'p':
                self.run_poller(True)


class WaitSplash(Toplevel):
    def __init__(self, mstr):
        Toplevel.__init__(self, master=mstr)

        Label(self, text='Please wait until background\nthreads are done running.', bg='white').grid(sticky=W+E+N+S)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        mstr_width = mstr.winfo_width()
        mstr_height = mstr.winfo_height()
        mstr_x = mstr.winfo_rootx()
        mstr_y = mstr.winfo_rooty()

        width = mstr_width / 5 * 4
        height = mstr_height / 5 * 4
        x = mstr_x + (mstr_width - width) / 2
        y = mstr_y + (mstr_height - height) / 2

        self.configure(bg='white')
        self.geometry('%dx%d+%d+%d' % (width, height, x, y))

        self.overrideredirect(True)
        self.update()


class ModbusPollThreadedTask(threading.Thread):
    def __init__(self, queue_obj, ip, mbid, start_reg, num_vals, data_type, b_byte_swap, b_word_swap, mb_timeout,
                 poll_delay, port, mb_func):
        self.ip = ip
        self.mbid = mbid
        self.start_reg = start_reg
        self.num_vals = num_vals
        self.data_type = data_type
        self.b_byte_swap = b_byte_swap
        self.b_word_swap = b_word_swap
        self.port = port
        self.mb_func = mb_func
        self.mb_timeout = mb_timeout
        self.poll_delay = poll_delay

        # print(self.timeout, self.pd)
        threading.Thread.__init__(self)
        self.queue = queue_obj

    def run(self):
        # run function overrides thread run method
        # print('start ', time())
        otpt = mb_poll.modbus_poller(self.ip, self.mbid, self.start_reg, self.num_vals, data_type=self.data_type,
                                     b_byteswap=self.b_byte_swap, b_wordswap=self.b_word_swap,
                                     mb_timeout=self.mb_timeout, poll_delay=self.poll_delay, port=self.port,
                                     mb_func=self.mb_func)
        # print('finish', time(), '\n')
        self.queue.put((1, otpt))


matplotlib.use('TkAgg')

root = Tk()
root.title('PyBus Modbus Scanner')
root.resizable(width=False, height=False)
root.protocol("WM_DELETE_WINDOW", _quit)

if os.name == 'nt':
    # icopath = sys.path[0] + '/resources/Upenn16.ico'
    icopath = os.getcwd() + '/resources/Upenn16.ico'
    root.iconbitmap(icopath)
else:
    pass
    icopath = sys.path[0] + '/resources/Upenn64.png'
    icon_img = Image('photo', file=icopath)
    root.tk.call('wm', 'iconphoto', root._w, icon_img)
    # root.iconphoto(True, PhotoImage)

    # img = Tkinter.Image("photo", file="appicon.gif")
    # root.tk.call('wm','iconphoto',root._w,img)

# disp_app_rt = DisplayApp(root)
inpt_app_rt = InputApp(root)

root.mainloop()

try:
    root.destroy()  # optional; see description below
except TclError:
    pass
