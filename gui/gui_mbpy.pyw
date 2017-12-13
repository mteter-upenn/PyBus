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
        self.var_num_regs = StringVar()
        self.var_byte_swap = IntVar()
        self.var_word_swap = IntVar()
        self.var_data_type = StringVar()
        # self.v_pts = StringVar()
        self.var_port = StringVar()

        self.b_ip_good = False
        self.b_mbid_good = False
        self.b_start_reg_good = True
        self.b_num_regs_good = True
        self.b_poll_delay_good = True
        # self.pts_gd = True
        self.b_graph_otpt_good = True

        # Labels
        Label(self.input_frame, text='IP:').grid(row=0, column=0, sticky=W)
        Label(self.input_frame, text='Device:').grid(row=1, column=0, sticky=W)
        Label(self.input_frame, text='Data Type:').grid(row=2, column=0, sticky=W)
        Label(self.input_frame, text='Starting Register:').grid(row=0, column=2, sticky=W)
        self.l_num_regs = Label(self.input_frame, text='Number of Outputs:', width=16, anchor=W)
        Label(self.input_frame, text='Graph Output:').grid(row=2, column=2, sticky=W)
        Label(self.input_frame, text='Poll Delay (ms):').grid(row=2, column=6, sticky=W)
        Label(self.input_frame, text='Byte Swap:').grid(row=1, column=4, sticky=W)
        Label(self.input_frame, text='Word Swap:').grid(row=2, column=4, sticky=W)
        Label(self.input_frame, text='Port:').grid(row=0, column=4, sticky=W)

    # Entry widgets
        self.e_ip = Entry(self.input_frame, width=22, textvariable=self.var_ip)
        self.e_mbid = Entry(self.input_frame, width=22, textvariable=self.var_mbid)
        self.e_start_reg = Entry(self.input_frame, width=6, textvariable=self.var_start_reg)
        self.e_num_regs = Entry(self.input_frame, width=6, textvariable=self.var_num_regs)
        self.e_poll_delay = Entry(self.input_frame, width=6, textvariable=self.var_poll_delay)
        self.e_port = Entry(self.input_frame, width=6, textvariable=self.var_port)
    # Checkbutton widgets
        ch_byte_swap = Checkbutton(self.input_frame, variable=self.var_byte_swap)  # .select and .deselect to change value
        ch_word_swap = Checkbutton(self.input_frame, variable=self.var_word_swap)
        self.ch_graph_otpt = Checkbutton(self.input_frame, variable=self.var_graph_otpt)
    # Combobox widget
        cb_data_type = Combobox(self.input_frame, width=21, height=11, textvariable=self.var_data_type)
    # Button widgets
        self.b_start = Button(button_frame, text='Start Polling', width=15, state=DISABLED, command=self.start_polling)
        self.b_stop = Button(button_frame, text='Stop Polling', width=15, state=DISABLED, command=self.stop_polling)
        self.b_func = Button(self.input_frame, text='Function 3', command=self.change_mb_function)

    # Entry widget default values
        self.e_poll_delay.insert(0, 1000)
        self.e_start_reg.insert(0, 1)
        self.e_num_regs.insert(0, 1)
        self.e_port.insert(0, 502)
    # Combobox defualt values
        cb_data_type['values'] = ('Binary 16 Bit', 'Hexadecimal 16 Bit', 'ASCII 16 Bit', 'Float 32 Bit', 'Double 64 Bit',
                             'Eaton Energy 64 Bit',
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
        self.l_num_regs.grid(row=1, column=2, sticky=W)
    # Entry widget grid
        self.e_ip.grid(row=0, column=1, padx=(0, 10), pady=(5, 0))
        self.e_mbid.grid(row=1, column=1, padx=(0, 10))
        self.e_start_reg.grid(row=0, column=3, padx=(0, 10), pady=(5, 0))
        self.e_num_regs.grid(row=1, column=3, padx=(0, 10))
        self.e_poll_delay.grid(row=2, column=7, pady=(0, 10), sticky=W)
        self.e_port.grid(row=0, column=5, padx=(0, 5), pady=(5, 0))
    # Checkbutton grid
        ch_byte_swap.grid(row=1, column=5)
        ch_word_swap.grid(row=2, column=5)
        self.ch_graph_otpt.grid(row=2, column=3)
    # Combobox grid
        cb_data_type.grid(row=2, column=1, padx=(0, 10))
    # Button grid
        self.b_start.grid(row=0, column=0, padx=5, pady=5)
        self.b_stop.grid(row=0, column=1, padx=5, pady=5)
        self.b_func.grid(row=2, column=8, padx=(0, 5), pady=(0, 10), sticky=W+E)

    # Bindings
        self.var_ip.trace('w', self.verify_ip)
        self.var_mbid.trace('w', self.dev_chk)
        self.var_start_reg.trace('w', self.strt_chk)
        self.var_num_regs.trace('w', self.lgth_chk)
        self.var_poll_delay.trace('w', self.pd_chk)
        self.var_graph_otpt.trace('w', self.lgth_chk)

    # Set variables for testing
        self.var_ip.set('10.166.6.67')
        self.var_mbid.set(9)

        self.mb_func = 3
    #     self.v_ip.set('130.91.147.20')
    #     self.v_dev.set(10)

    def start_polling(self):
        self.b_start.configure(state=DISABLED)
        self.b_stop.configure(state=NORMAL)
        change_all_children_state(self.input_frame.winfo_children(), DISABLED)
        self.display_app.makeframe(self.var_graph_otpt.get(), self.var_ip.get(), self.var_mbid.get(), self.var_start_reg.get(),
                                   self.var_num_regs.get(), DATA_TYPE_DICT[self.var_data_type.get()], self.var_byte_swap.get(), self.var_word_swap.get(),
                                   self.var_poll_delay.get(), self.var_port.get(), self.mb_func)

    def stop_polling(self):
        self.b_start.configure(state=NORMAL)
        self.b_stop.configure(state=DISABLED)
        change_all_children_state(self.input_frame.winfo_children(), NORMAL)

        self.display_app.killframe(self.var_graph_otpt.get())

    def change_mb_function(self):
        self.mb_func = ((self.mb_func - 2) % 4) + 3  # rotate through funcs 3, 4, 5, 6
        func_btn_text = 'Function ' + str(self.mb_func)
        self.b_func.configure(text=func_btn_text)

        if self.mb_func in (5, 6):
            self.l_num_regs.configure(text='Value to write:')
            self.ch_graph_otpt.configure(fg='red')
            self.b_graph_otpt_good = False
        else:
            self.l_num_regs.configure(text='Number of Outputs:')
            self.ch_graph_otpt.configure(fg='black')
            self.b_graph_otpt_good = True

        self.lgth_chk()

    def verify_ip(self, *args):
        iparr = self.var_ip.get().split(".")
        b_ip_flag = True

        if len(iparr) != 4:
            if len(iparr) == 1:
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
            for ch in iparr:
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

        self.all_chk()

    def dev_chk(self, *args):
        dev_flg = True
        try:
            dev = int(self.var_mbid.get())
        except ValueError:
            dev_flg = False
        else:
            if dev < 1 or dev > 255:
                dev_flg = False

        if dev_flg:
            self.e_mbid.configure(fg='black')
            self.b_mbid_good = True
        else:
            self.e_mbid.configure(fg='red')
            self.b_mbid_good = False

        self.all_chk()

    def strt_chk(self, *args):
        strt_flg = True
        try:
            strt = int(self.var_start_reg.get())
        except ValueError:
            strt_flg = False
        else:
            if strt < 0 or strt > 99999:
                strt_flg = False

        if strt_flg:
            self.e_start_reg.configure(fg='black')
            self.b_start_reg_good = True
        else:
            self.e_start_reg.configure(fg='red')
            self.b_start_reg_good = False

        self.all_chk()

    def lgth_chk(self, *args):
        lgth_flg = True
        try:
            lgth = int(self.var_num_regs.get())
        except ValueError:
            lgth_flg = False
        else:
            if self.mb_func in (3, 4):
                if self.var_graph_otpt.get():
                    cap = 4
                else:
                    cap = 80

                if lgth < 1 or lgth > cap:
                    lgth_flg = False
            elif self.mb_func == 5:  # only 1 or 0
                if lgth not in (0, 1):
                    lgth_flg = False
            elif self.mb_func == 6:
                if lgth < 0 or lgth > 65535:
                    lgth_flg = False
            else:
                lgth_flg = False

        if lgth_flg:
            self.e_num_regs.configure(fg='black')
            self.b_num_regs_good = True

            if self.var_graph_otpt.get():
                if self.mb_func in (3, 4):
                    self.ch_graph_otpt.configure(fg='black')
                    self.b_graph_otpt_good = True
            else:
                self.ch_graph_otpt.configure(fg='black')
                self.b_graph_otpt_good = True
        else:
            self.e_num_regs.configure(fg='red')
            self.ch_graph_otpt.configure(fg='red')
            self.b_num_regs_good = False
            self.b_graph_otpt_good = False

        self.all_chk()

    def pd_chk(self, *args):
        pd_flg = True
        try:
            pd = int(self.var_poll_delay.get())
        except ValueError:
            pd_flg = False
        else:
            if pd < 0 or pd > 600000:  # less than 10 minutes
                pd_flg = False

        if pd_flg:
            self.e_poll_delay.configure(fg='black')
            self.b_poll_delay_good = True
        else:
            self.e_poll_delay.configure(fg='red')
            self.b_poll_delay_good = False

        self.all_chk()

    def all_chk(self):
        if self.b_ip_good and self.b_mbid_good and self.b_start_reg_good and self.b_num_regs_good and self.b_poll_delay_good and self.b_graph_otpt_good:
            self.b_start.configure(state=NORMAL)
        else:
            self.b_start.configure(state=DISABLED)


class DisplayApp:
    def __init__(self, mstr):
        self.mstr = mstr

        self.text_frm = Frame(mstr, bd=2, relief=GROOVE)
        self.tb_frm = Frame(self.text_frm, bd=2, relief=GROOVE)
        self.tl_frm = Frame(self.text_frm)

        self.text_frm.grid(row=1, column=0, sticky=W+E, padx=5, pady=5)
        self.tb_frm.grid(row=0, column=0, padx=(0, 10), sticky=NW)
        self.tl_frm.grid(row=0, column=1, sticky=W+E+N+S)
        self.text_frm.grid_remove()

    # graph frame
        self.graph_frm = Frame(mstr, bd=2, relief=GROOVE)
        self.gb_frm = Frame(self.graph_frm, bd=2, relief=GROOVE)
        self.fig = plt.figure(1, figsize=(6.2, 5), dpi=100, tight_layout=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frm)
        self.canvas.show()

        # self.canvas.mpl_connect('key_press_event', self.on_key_event)

        self.graph_frm.grid(row=1, columnspan=2, sticky=W+E, padx=5, pady=5)
        self.gb_frm.grid(row=0, column=0, sticky=NW, padx=(0, 10))
        self.canvas.get_tk_widget().grid(row=0, column=1)
        self.graph_frm.grid_remove()

    # text frame widgets
        self.l_errs = Label(self.tb_frm, text='Err: None', anchor=W)
        self.l_tot_polls = Label(self.tb_frm, text='Total Polls: 0', anchor=W, width=13)
        self.l_val_polls = Label(self.tb_frm, text='Valid Polls: 0', anchor=W, width=13)

        self.b_pause = Button(self.tb_frm, text='Pause', width=8, command=lambda: self.run_poller(False))
        self.b_resume = Button(self.tb_frm, text='Resume', width=8, state=DISABLED, command=self.start_button)
        self.b_reset = Button(self.tb_frm, text='Reset Poll\nCounters', width=8, height=2, command=self.reset_cntrs)
        self.b_savetx = Button(self.tb_frm, text='Save Data', width=8, state=DISABLED, command=self.sv_data)

        self.b_pause.grid(row=0, column=0, padx=5, pady=5)
        self.b_resume.grid(row=1, column=0, padx=5, pady=5)
        self.l_errs.grid(row=2, column=0, sticky=W)
        self.l_tot_polls.grid(row=3, column=0, sticky=W)
        self.l_val_polls.grid(row=4, column=0, sticky=W)
        self.b_reset.grid(row=5, column=0, padx=5, pady=5)
        self.b_savetx.grid(row=6, column=0, padx=5, pady=5)

    # graph frame widgets
        self.l_errs_g = Label(self.gb_frm, text='Err: None')
        self.l_tot_polls_g = Label(self.gb_frm, text='Total Polls: 0', anchor=W, width=15)
        self.l_val_polls_g = Label(self.gb_frm, text='Valid Polls: 0', anchor=W, width=15)

        self.b_pause_g = Button(self.gb_frm, text='Pause', width=8, command=lambda: self.run_poller(False))
        self.b_resume_g = Button(self.gb_frm, text='Resume', width=8, state=DISABLED, command=self.start_button)
        self.b_reset_g = Button(self.gb_frm, text='Reset Poll\nCounters', width=8, height=2, command=self.reset_cntrs)
        self.b_adj_plt = Button(self.gb_frm, text='All Plots\nAffected', width=8, height=2, state=DISABLED,
                                command=self.adj_plt)
        self.b_savegr_g = Button(self.gb_frm, text='Save Graph', width=8, state=DISABLED, command=self.sv_fig)
        self.b_savetx_g = Button(self.gb_frm, text='Save Data', width=8, state=DISABLED, command=self.sv_data)

        self.b_pause_g.grid(row=0, column=0, padx=5, pady=5)
        self.b_resume_g.grid(row=1, column=0, padx=5, pady=5)
        self.l_errs_g.grid(row=2, column=0)
        self.l_tot_polls_g.grid(row=3, column=0, sticky=W)
        self.l_val_polls_g.grid(row=4, column=0, sticky=W)
        self.b_reset_g.grid(row=5, column=0, padx=5, pady=5)
        self.b_adj_plt.grid(row=10, column=0, padx=5, pady=5)
        self.b_savegr_g.grid(row=11, column=0, padx=5, pady=5)
        self.b_savetx_g.grid(row=12, column=0, padx=5, pady=5)

    # variables
        self.text_lbls = []  # create dynamic list to handle unknown amount of outputs
        # self.otpt = [[] for _ in range(5)]
        self.otpt = []
        self.otpt_err = []
        self.fig.add_subplot(111)
        self.fig.axes[0].set_autoscalex_on(False)
        self.fig.autofmt_xdate(rotation=45)
        self.fig.axes[0].xaxis.set_major_formatter(dates.DateFormatter('%m-%d %H:%M:%S'))
        self.plts = [None]*4
        dum_plt, = self.fig.axes[0].plot_date([], [], marker='', linestyle='-')
        self.plts[0] = dum_plt
        self.wch_plt = 0

        self.flg_gph = False
        self.chk_tm = time()

        self.ip = '165.123.136.170'
        self.dev = 9
        # self.ip = '130.91.147.20'
        # self.dev = 10
        self.strt = 1
        self.lgth = 1
        self.dtype = 'float'
        self.pd = 1000
        self.bs = False
        self.ws = False
        self.prt = 502
        self.func = 3
        self.wrt = True
        self.typ = 'float'

        self.queue = None  # queue.PriorityQueue()
        self.tm = 99  # amount of time between queue checks
        self._job = None
        self.totpolls = 0
        self.valpolls = 0

    def start_button(self):
        while not self.queue.empty():
            self.queue.get(block=False)
        self.run_poller(True)
        self.mstr.after(self.tm, self.process_queue)

    def run_poller(self, flg_pse):
        if flg_pse:  # run task
            if self.flg_gph:
                self.b_pause_g.configure(state=NORMAL)
                self.b_resume_g.configure(state=DISABLED)
                self.b_adj_plt.configure(state=DISABLED)
                self.b_savegr_g.configure(state=DISABLED)
                self.b_savetx_g.configure(state=DISABLED)
            else:
                self.b_pause.configure(state=NORMAL)
                self.b_resume.configure(state=DISABLED)
                self.b_savetx.configure(state=DISABLED)

            # self.queue = queue.Queue()
            self.chk_tm = time()

            ModbusPollThreadedTask(self.queue, self.ip, self.dev, self.strt, self.lgth, self.dtype, self.bs, self.ws,
                                   self.pd, int((self.chk_tm - time()) * 1000) + self.pd - 50, self.prt,
                                   self.func).start()

            # self.mstr.after(self.tm, self.process_queue)
        else:  # pause task
            self.queue.put((0, 'Paused'))

    def process_queue(self):
        try:
            msg = self.queue.get(block=False)
            msg = msg[1]
            # handle output ******************************************************************************************
            if msg == 'Paused':
                # print(msg)
                if self._job is not None:
                    self.mstr.after_cancel(self._job)
                    self._job = None

                if self.flg_gph:
                    self.b_pause_g.configure(state=DISABLED)
                else:
                    self.b_pause.configure(state=DISABLED)
                self.mstr.update()

                # kill thread here?
                if threading.active_count() > 1:
                    top = WaitSplash(self.mstr)
                    # top.update()

                    while threading.active_count() > 1:
                        # print('thread running on pause')
                        sleep(.05)
                    else:
                        top.destroy()

                while not self.queue.empty():
                    self.queue.get(block=False)

                if self.flg_gph:
                    # self.b_pause_g.configure(state=DISABLED)
                    self.b_resume_g.configure(state=NORMAL)
                    self.b_adj_plt.configure(state=NORMAL)
                    self.b_savegr_g.configure(state=NORMAL)
                    self.b_savetx_g.configure(state=NORMAL)
                else:
                    # self.b_pause.configure(state=DISABLED)
                    self.b_resume.configure(state=NORMAL)
                    self.b_savetx.configure(state=NORMAL)
                return
            else:
                # print(time(), threading.active_count())
                self.totpolls += 1
                if self.flg_gph:  # graph data
                    if msg[0] != 'Err':
                        self.valpolls += 1
                        self.l_errs_g.configure(text='Err: None')
                        self.write_lbls(msg)
                    else:
                        self.l_errs_g.configure(text='Err: ' + str(msg[1]))
                        self.write_err(msg)
                    self.l_tot_polls_g.configure(text='Total Polls: ' + str(self.totpolls))
                    self.l_val_polls_g.configure(text='Valid Polls: ' + str(self.valpolls))
                else:  # no graph

                    # while (self.chk_tm + self.pd / 1000 - time()) > 0.02:
                    #     pass
                    if msg[0] != 'Err':
                        self.valpolls += 1
                        self.l_errs.configure(text='Err: None')
                        self.write_lbls(msg)
                    else:
                        self.l_errs.configure(text='Err: ' + str(msg[1]))
                        self.write_err(msg)
                    self.l_tot_polls.configure(text='Total Polls: ' + str(self.totpolls))
                    self.l_val_polls.configure(text='Valid Polls: ' + str(self.valpolls))

                # time.sleep(max(0, self.chk_tm + self.pd - time.time()))
                # self.run_poller(True)
                # self._job = self.mstr.after(max(0, int((self.chk_tm + self.pd - time()) * 1000)),
                #                             lambda: self.run_poller(True))
                self._job = self.mstr.after(max(0, int((self.chk_tm - time()) * 1000) + self.pd),
                                            lambda: self.run_poller(self.wrt))
                self.mstr.after(self.tm, self.process_queue)
        except queue.Empty:
            self.mstr.after(self.tm, self.process_queue)

    def makeframe(self, flg_frm, ip, dev, strt=1, cnt=1, typ='float', bs=False, ws=False, pd=1000, prt=502, funct=3):
        self.totpolls = 0
        self.valpolls = 0

        self.ip = ip
        self.dev = dev
        self.strt = strt
        self.lgth = int(cnt)
        self.dtype = typ
        self.bs = bs
        self.ws = ws
        self.pd = int(pd)
        self.prt = prt
        self.func = funct
        self.typ = typ

        if self.func in (3, 4):
            self.wrt = True
            regs = int(cnt)
        else:
            self.wrt = False
            regs = 1

        self.otpt = [[] for _ in range(self.lgth + 1)]
        self.otpt_err = [[] for _ in range(3)]

        self.queue = queue.PriorityQueue()

        if flg_frm == 1:
            self.flg_gph = True
            self.wch_plt = 0
            self.mk_lbls(int(strt), regs)

            self.mstr.bind('<Key>', self.on_key_event)
            self.mstr.bind('<Control-Up>', lambda e: self.on_key_event(e, True))
            self.mstr.bind('<Control-Left>', lambda e: self.on_key_event(e, True))
            self.mstr.bind('<Control-Right>', lambda e: self.on_key_event(e, True))
            self.mstr.bind('<Control-Down>', lambda e: self.on_key_event(e, True))

            self.graph_frm.grid()
            self.start_button()
        else:
            self.flg_gph = False
            self.mk_lbls(int(strt), regs)
            self.text_frm.grid()
            self.start_button()

    def killframe(self, flg):
        self.clear_lbls()

        if flg == 1:
            self.mstr.unbind('<Key>')
            self.mstr.unbind('<Control-Up>')
            self.mstr.unbind('<Control-Left>')
            self.mstr.unbind('<Control-Right>')
            self.mstr.unbind('<Control-Down>')

            self.graph_frm.grid_remove()
        else:
            self.text_frm.grid_remove()

        self.otpt = []
        self.otpt_err = []
        self.run_poller(False)

    def mk_lbls(self, strt, cnt):
        if self.typ in mb_poll.TWO_BYTE_FORMATS:  # ('bin', 'hex', 'ascii', 'uint16', 'sint16'):
            mlt = 1
        elif self.typ in mb_poll.FOUR_BYTE_FORMATS:  # ('uint32', 'sint32', 'float', 'mod10k'):
            mlt = 2
        elif self.typ in mb_poll.SIX_BYTE_FORMATS:  # ('mod20k'):
            mlt = 3
        else:  # ('mod30k', 'uint64', 'engy', 'dbl')
            mlt = 4

        last_reg = strt + cnt * mlt
        num_digits = max(int(log10(last_reg)) + 1, 4)

        if self.func in (3, 6):
            strt += 4 * 10 ** num_digits  # 40000
        elif self.func == 4:
            strt += 3 * 10 ** num_digits
        else:  # func 5
            strt += 1 * 10 ** num_digits

        if self.flg_gph:
            frm = self.gb_frm
            rw_adj = 6
            col_adj = 0

            pst_cnt = len(self.fig.axes)

            if pst_cnt == cnt:
                pass  # don't need to change subplot geometry
            elif cnt < pst_cnt:
                for i in range(pst_cnt - 1, cnt - 1, -1):
                    self.fig.delaxes(self.fig.axes[i])
                    self.plts[i] = None

                if cnt == 1:
                    self.fig.axes[0].change_geometry(1, 1, 1)
                    plt.setp(self.fig.axes[0].get_xticklabels(), visible=True)
                elif cnt == 2:
                    self.fig.axes[0].change_geometry(2, 1, 1)
                    self.fig.axes[1].change_geometry(2, 1, 2)
                    plt.setp(self.fig.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.fig.axes[1].get_xticklabels(), visible=True)
                else:
                    self.fig.axes[0].change_geometry(2, 2, 1)
                    self.fig.axes[1].change_geometry(2, 2, 2)
                    self.fig.axes[2].change_geometry(2, 2, 3)
                    plt.setp(self.fig.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.fig.axes[1].get_xticklabels(), visible=True)
            else:  # cnt > pst_cnt
                for i in range(pst_cnt, cnt):
                    self.fig.add_subplot(cnt, 1, i + 1)
                    plt.setp(self.fig.axes[i].get_xticklabels(), rotation=45)
                    self.fig.axes[i].xaxis.set_major_formatter(dates.DateFormatter('%m-%d %H:%M:%S'))
                    dum_plt, = self.fig.axes[i].plot_date([], [], marker='', linestyle='-')
                    self.plts[i] = dum_plt

                if cnt == 2:
                    self.fig.axes[0].change_geometry(2, 1, 1)
                    self.fig.axes[1].change_geometry(2, 1, 2)
                    plt.setp(self.fig.axes[0].get_xticklabels(), visible=False)
                elif cnt == 3:
                    self.fig.axes[0].change_geometry(2, 2, 1)
                    self.fig.axes[1].change_geometry(2, 2, 2)
                    self.fig.axes[2].change_geometry(2, 2, 3)
                    plt.setp(self.fig.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.fig.axes[1].get_xticklabels(), visible=True)
                else:
                    self.fig.axes[0].change_geometry(2, 2, 1)
                    self.fig.axes[1].change_geometry(2, 2, 2)
                    self.fig.axes[2].change_geometry(2, 2, 3)
                    self.fig.axes[3].change_geometry(2, 2, 4)
                    plt.setp(self.fig.axes[0].get_xticklabels(), visible=False)
                    plt.setp(self.fig.axes[1].get_xticklabels(), visible=False)

        else:
            frm = self.tl_frm
            rw_adj = 0
            col_adj = 10

        for i in range(cnt):
            col = i // 10
            rw = (i % 10) + rw_adj
            reg_str = str(strt + i * mlt)
            self.otpt[i].append(reg_str)

            lbl = Label(frm, text=reg_str + ': ', width=19, anchor=W)
            self.text_lbls.append(lbl)
            lbl.grid(row=rw, column=col, padx=(0, col_adj), sticky=W)

        self.otpt[-1].append('Datetime')

        self.otpt_err[0].append('Error Code')
        self.otpt_err[1].append('Description')
        self.otpt_err[2].append('Error Datetime')

    def clear_lbls(self):
        for i in range(len(self.text_lbls)):
            self.text_lbls[i].destroy()
        self.text_lbls = []

        if self.flg_gph:
            self.l_tot_polls_g.configure(text='Total Polls: 0')
            self.l_val_polls_g.configure(text='Valid Polls: 0')
        else:
            self.l_tot_polls.configure(text='Total Polls: 0')
            self.l_val_polls.configure(text='Valid Polls: 0')

    def write_lbls(self, data):
        if len(self.text_lbls) == len(data):
            # handle data
            for i in range(len(self.text_lbls)):
                if self.typ in ('bin', 'hex', 'ascii'):
                    txt = self.text_lbls[i].cget('text')[:7] + data[i]
                elif self.typ in ('float', 'dbl'):
                    txt = self.text_lbls[i].cget('text')[:7] + '%.2f' % data[i]
                else:
                    txt = self.text_lbls[i].cget('text')[:7] + '%.0f' % data[i]
                self.text_lbls[i].configure(text=txt)
                self.otpt[i].append(data[i])

            self.otpt[-1].append(dates.date2num(datetime.now()))

            if self.flg_gph:
                plls = len(self.otpt[0]) - 1

                if plls > 1:
                    for i in range(self.lgth):
                        if plls > 20:
                            minx = plls - 20
                        else:
                            minx = 1

                        # renew plot data
                        self.plts[i].set_xdata(self.otpt[-1][1:])
                        self.plts[i].set_ydata(self.otpt[i][1:])

                        # reset axes
                        self.fig.axes[i].set_autoscaley_on(True)
                        self.fig.axes[i].relim()
                        self.fig.axes[i].set_xlim([self.otpt[-1][minx], self.otpt[-1][plls]])
                        self.fig.axes[i].autoscale_view()

                    self.canvas.draw()

        else:
            pass

    def write_err(self, data):
        self.otpt_err[0].append(data[1])
        self.otpt_err[1].append(data[2])
        self.otpt_err[2].append(dates.date2num(datetime.now()))

    def reset_cntrs(self):
        self.totpolls = 0
        self.valpolls = 0

        if self.flg_gph:
            self.l_tot_polls_g.configure(text='Total Polls: ' + str(self.totpolls))
            self.l_val_polls_g.configure(text='Valid Polls: ' + str(self.valpolls))
        else:
            self.l_tot_polls.configure(text='Total Polls: ' + str(self.totpolls))
            self.l_val_polls.configure(text='Valid Polls: ' + str(self.valpolls))

    def sv_fig(self):
        # print(plt.gcf().canvas.get_supported_filetypes())
        ftypes = [('PNG', '.png'), ('SVG', '.svg'), ('SVG', '.svgz'), ('PDF', '.pdf'), ('PostScript', '.ps'),
                  ('Encapsulated PostScript', '.eps'), ('Raw Bitmap', '.rgba'), ('Raw Bitmap', '.raw'),
                  ('LaTeX', '.pgf')]
        f = filedialog.asksaveasfilename(defaultextension='.png', filetypes=ftypes, parent=self.mstr)
        if f != '':
            try:
                plt.savefig(f, dpi=400)
            except IOError:
                messagebox.showerror('File Error', 'Plot could not be saved because file is already open!')

    def sv_data(self):
        # print(os.getcwd())
        f = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '.csv')], parent=self.mstr)
        if f != '':
            try:
                csvfile = open(f, 'w', newline='')
            except IOError:
                messagebox.showerror('File Error', 'Data could not be written because file is already open!')
            else:
                fwriter = csv.writer(csvfile)
                for rw in self.otpt:
                    fwriter.writerow(rw)

                fwriter.writerow([])

                for rw in self.otpt_err:
                    fwriter.writerow(rw)

    def adj_plt(self):
        self.wch_plt = (self.wch_plt + 1) % (self.lgth + 1)
        if self.wch_plt == 0:
            self.b_adj_plt.configure(text='All Plots\nAffected')
        else:
            self.b_adj_plt.configure(text='Plot ' + str(self.wch_plt) + '\nAffected')

    def on_key_event(self, event, ctrl=False):
        # print(self.flg_gph, self.b_pause_g.cget('state'), event.keysym, event.keycode)

        if self.flg_gph:
            if self.b_pause_g.cget('state') == DISABLED:  # don't want to do this while the graphs are updating
                if self.wch_plt == 0:
                    minax = 0
                    maxax = self.lgth
                else:
                    minax = self.wch_plt - 1
                    maxax = self.wch_plt
        
                if event.keysym in ('Up', 'Down'):  # , 'ctrl+up', 'ctrl+down'):
                    for i in range(minax, maxax):
                        lw, hg = self.fig.axes[i].get_ylim()
                        new_lim = scale_axis(lw, hg, event.keysym, ctrl)
                        self.fig.axes[i].set_ylim(new_lim)
        
                    self.canvas.draw()
                elif event.keysym in ('Left', 'Right'):  # , 'ctrl+left', 'ctrl+right'):
                    for i in range(minax, maxax):
                        lw, hg = self.fig.axes[i].get_xlim()
                        new_lim = scale_axis(lw, hg, event.keysym, ctrl)
                        self.fig.axes[i].set_xlim(new_lim)
        
                    self.canvas.draw()
                elif event.keysym == 's':
                    self.sv_fig()
                elif event.keysym == 'w':
                    self.adj_plt()
                elif event.keysym == 'g':
                    plt.grid()
                    self.canvas.draw()
                elif event.keysym == 'r':
                    self.start_button()
            elif event.keysym == 'p':
                self.run_poller(False)


class WaitSplash(Toplevel):
    def __init__(self, mstr):
        Toplevel.__init__(self, master=mstr)

        Label(self, text='Please wait until background\nthreads are done running.', bg='white').grid(sticky=W+E+N+S)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        rw = mstr.winfo_width()
        rh = mstr.winfo_height()
        rx = mstr.winfo_rootx()
        ry = mstr.winfo_rooty()

        w = rw / 5 * 4
        h = rh / 5 * 4
        x = rx + (rw - w) / 2
        y = ry + (rh - h) / 2

        self.configure(bg='white')
        self.geometry('%dx%d+%d+%d' % (w, h, x, y))

        self.overrideredirect(True)
        self.update()


class ModbusPollThreadedTask(threading.Thread):
    def __init__(self, queue_obj, ip, dev, strt, lgth, dtype, bs, ws, to, pd, prt, func):
        self.ip = ip
        self.dev = dev
        self.strt = strt
        self.lgth = lgth
        self.dtype = dtype
        self.bs = bs
        self.ws = ws
        self.prt = prt
        self.func = func
        self.timeout = to
        self.pd = pd

        # print(self.timeout, self.pd)
        threading.Thread.__init__(self)
        self.queue = queue_obj

    def run(self):
        # run function overrides thread run method
        # print('start ', time())
        otpt = mb_poll.modbus_poller(self.ip, self.dev, self.strt, self.lgth, data_type=self.dtype, b_byteswap=self.bs,
                                     b_wordswap=self.ws, mb_timeout=self.timeout, poll_delay=self.pd, port=self.prt,
                                     mb_func=self.func)
        # print('finish', time(), '\n')
        self.queue.put((1, otpt))


matplotlib.use('TkAgg')

root = Tk()
root.title('PyBus Modbus Scanner')
root.resizable(width=False, height=False)
root.protocol("WM_DELETE_WINDOW", _quit)

if os.name == 'nt':
    icopath = sys.path[0] + '/resources/Upenn16.ico'
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
