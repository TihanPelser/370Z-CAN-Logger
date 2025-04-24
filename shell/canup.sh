#!/bin/sh

#Create can device
sudo slcan_attach -f -s6 -o -l /dev/ttyACM1
sudo slcand -S 115200 /dev/ttyACM1 can0
sudo ip link set can0 up