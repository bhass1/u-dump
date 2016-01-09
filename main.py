#!/usr/bin/env python3
__author__ = 'Ion Agorria'
import argparse
from datetime import datetime
from time import time
from serial import Serial

def parse_line(line, size):
    # Break down each part
    assert len(line) == size
    i = 0
    addr = line[i:i + 8]
    i += 8
    assert line[i:i + 2] == ": "
    i += 2
    hex_data = line[i:i + 8]
    i += 8
    assert line[i:i + 1] == " "
    i += 1
    hex_data += line[i:i + 8]
    i += 8
    assert line[i:i + 1] == " "
    i += 1
    hex_data += line[i:i + 8]
    i += 8
    assert line[i:i + 1] == " "
    i += 1
    hex_data += line[i:i + 8]
    i += 8
    assert line[i:i + 4] == "    "
    i += 4
    text = line[i:i + 16]
    i += 16
    assert line[i:i + 2] == "\r\n"

    #Convert hex string into actual data
    data = []
    for i in range(0, len(hex_data), 2):
        piece = hex_data[i:i + 2]
        data.append(int(piece, 16))

    #For redundancy check if data matches text, but only for printable characters (non dot)
    for i, piece in enumerate(data):
        if text[i] != ".":
            assert chr(piece) == text[i]

    return int(addr, 16), data, text


def write(serial, opts, data):
    if opts.debug:
        print("Debug write: " + data.replace("\n", "\\n"))
    data = bytes(data, "ascii")
    serial.write(data)


def dump(serial, opts):
    data = bytes()
    finish = False
    lastaddr = 0
    # Send the initial command
    write(serial, opts, "md %s %s\n" % (hex(opts.start), hex(opts.step * 4)))

    while not finish:
        #Read response
        chunk = serial.readlines()
        if opts.debug:
            print("Debug read: " + str(chunk))

        assert len(chunk) > 0

        #Remove first one, its the command that we sent
        chunk = chunk[1:]

        #Iterate each line in chunk
        for line in chunk:
            line = line.decode("ascii")

            #Adquire new chunk by sending newline
            if line == '=> ':
                if opts.debug:
                    print("Debug: detected prompt, sending newline")
                write(serial, opts, "\n")
                continue

            if opts.debug:
                print("line: " + str(line))

            addr, line_data, text = parse_line(line, opts.size)

            #Print current line
            hex_addr = hex(addr).upper()[2:]
            while not len(hex_addr) == 8:
                hex_addr = "0" + hex_addr
            hex_data = ""
            for line_byte in line_data:
                line_byte = hex(line_byte).upper()[2:]
                if len(line_byte) == 1:
                    line_byte = "0" + line_byte
                hex_data += " " + line_byte
            print("0x%s %s |%s|" % (hex_addr, hex_data, text))

            #Check if we skipped some line
            if lastaddr != 0 and lastaddr != addr - 0x10:
                raise Exception("Posible skip, last address 0x%x doesn't match with previous address 0x%x" % (lastaddr, addr - 0x10))
            lastaddr = addr

            #Discard if not start
            if addr < opts.start:
                print("Warning: address of this line is lower than start address! discarding")
                continue

            #Store line data
            data += bytes(line_data)

            #Check if we reach end
            if addr >= opts.end:
                print("Info: Reached specified end address")
                finish = True
                break

    return data


def main():
    # Args parse
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="Serial port of device")
    parser.add_argument("baud", type=int, help="Serial baud rate")
    parser.add_argument("start",  help="Start address in dec or hex (with 0x), must be multiple of 16")
    parser.add_argument("end", help="End address in dec or hex (with 0x), must be multiple of 16")
    parser.add_argument("--step", type=int, default=64, help="Number of lines per dump chunk")
    parser.add_argument("--size", type=int, default=67, help="Total size of each line including spaces and newlines")
    parser.add_argument("--timeout", type=float, default=0.1, help="Timeout in secs for serial")
    parser.add_argument('--debug', action='store_true', help='Enables debug mode')
    opts = parser.parse_args()

    # Args conversion
    if opts.start[0:2] == "0x":
        opts.start = int(opts.start, 16)
    else:
        opts.start = int(opts.start)
    if opts.end[0:2] == "0x":
        opts.end = int(opts.end, 16)
    else:
        opts.end = int(opts.end)

    # Args check
    if opts.start % 16 != 0:
        raise Exception("start argument is not multiple of 16")
    if opts.start < 0:
        raise Exception("start argument is too low")
    if opts.end % 16 != 0:
        raise Exception("end argument is not multiple of 16")
    if opts.end <= opts.start:
        raise Exception("end argument is too low")
    if opts.step <= 0:
        raise Exception("step argument is too low")
    if opts.size <= 0:
        raise Exception("size argument is too low")
    if opts.timeout <= 0:
        raise Exception("timeout argument is too low")
    if opts.debug:
        print("Debug mode enabled")

    #Prepare to dump
    serial = Serial(port=opts.port, baudrate=opts.baud, timeout=opts.timeout)
    try:
        data = dump(serial, opts)
    except Exception as e:
        raise e
    finally:
        serial.close()

    #Write to file
    name = datetime.fromtimestamp(time()).strftime("%Y-%m-%dT%H:%M:%S") + " " + hex(opts.start) + " " + hex(
        opts.end) + ".img"
    file = open(name, "wb")
    try:
        file.write(data)
    except Exception as e:
        raise e
    finally:
        file.close()

main()
