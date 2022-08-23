#!/bin/sh

#Create can device
sudo slcan_attach -f -s6 -o -l /dev/ttyACM0
sudo slcand -S 115200 /dev/ttyACM0 can0
sudo ip link set can0 up