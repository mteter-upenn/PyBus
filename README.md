# PyBus

PyBus is a Modbus scanner tool to be used in either a command line setting or as a function in a Python script.


## Command Line

Navigate to the `/mbpy` directory.  You must use `python3` in a Linux environment.

```
python mb_poll.py IP_ADDRESS MODBUS_DEVICE REGISTER NUM_VALS [-h] [-p POLL] [-t TYPE] [-bs] [-ws] [-0] [-to TIMEOUT] [-fl FILE] [-v] [-pt PORT] [-pd POLL_DELAY] [-f FUNCTION] 
```

Positional arguments:

- `IP_ADDESS`: The IP address or com port (/dev/tty, COM1, etc.).  
- `MODBUS_DEVICE`: The Modbus device number. [0,255]
- `REGISTER`: The starting register in 1-based format.
- `NUM_VALS`: The number of values desired to return or the number in uint format to be written to the register.  This is NOT the number of registers needed- if 2 is used for float datatype, then 2 values will be returned by the function, but 4 registers will be requested behind the scenes.

Optional arguments:  

- `-h, --help`: Returns help message.
- `-p POLL, --poll POLL`: [1] The number of polls to take.
- `-t TYPE, --type TYPE`: [float] The datatype of the value to be returned.  Can be any of the following:
	- `hex`: Register represented in hexidecimal
	- `bin`: Register represented in raw binary format
	- `ascii`: Register split into two ASCII bytes
	- `float`: IEEE754 float 32 bit
	- `dbl`: IEEE754 double 64 bit
	- `engy`: Eaton proprietary 64 bit datatype
	- `uint8`: Unsigned integer, 8 bits long
	- `uint16`: Unsigned integer, 16 bits long
	- `uint32`: Unsigned integer, 32 bits long
	- `uint48`: Unsigned integer, 48 bits long
	- `uint64`: Unsigned integer, 64 bits long
	- `sint8`: Signed integer, 8 bits long
	- `sint16`: Signed integer, 16 bits long
	- `sint32`: Signed integer, 32 bits long
	- `sint64`: Signed integer, 64 bits long
	- `um1k32`: Unsigned Mod 1000, 32 bits long
	- `um1k48`: Unsigned Mod 1000, 48 bits long
	- `um1k64`: Unsigned Mod 1000, 64 bits long
	- `sm1k16`: Signed Mod 1000, 16 bits long
	- `sm1k32`: Signed Mod 1000, 32 bits long
	- `sm1k48`: Signed Mod 1000, 48 bits long
	- `sm1k64`: Signed Mod 1000, 64 bits long
	- `um10k32`: Unsigned Mod 10000, 32 bits long
	- `um10k48`: Unsigned Mod 10000, 48 bits long
	- `um10k64`: Unsigned Mod 10000, 64 bits long
	- `sm10k16`: Signed Mod 10000, 16 bits long
	- `sm10k32`: Signed Mod 10000, 32 bits long
	- `sm10k48`: Signed Mod 10000, 48 bits long
	- `sm10k64`: Signed Mod 10000, 64 bits long
- `-to TIMEOUT, --timeout TIMEOUT`: Time in ms to wait for response from device.
- `-pd POLL_DELAY, --pdelay POLL_DELAY`: Time between polls. This will not trigger another request if the previous request has not timed out yet.
- `-bs, --byteswap`: Sets byte order to Little Endian. Default is Big Endian.
- `-ws, --byteswap`: Sets word order to Big Endian. Default is Little Endian.
- `-0, --zbased`: Register given in 0 based array format.
- `-pt PORT, --port PORT`: [502] Change port to open socket over.
- `-f FUNCTION, --func FUNCTION`: [3] Modbus function. Only 1, 2, 3, 4, 5, and 6 are fully supported.
- `-fl FILE, --file FILE`: Generates a csv file with name FILE in current directory.
-  `-v, --verbose`: Verbosity options:
	-  `-v`: Display last result only (Linux only)
	-  `-vv`: Display all results consecutively
	-  `-vvv`: `-v` with a progress bar (Linux only)
	-  `-vvvv`: `-vv` with a progress bar

