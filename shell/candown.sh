#!/bin/sh

# Delete CAN device
sudo ip link set can0 down
sudo killall slcand