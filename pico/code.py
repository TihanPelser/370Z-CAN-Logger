import board
import busio
import digitalio
import canio
import time

# Setup LED for indicating CAN activity
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

# Initialize CAN bus
can_bus = canio.CAN(
    busio.UART(tx=board.GP0, rx=board.GP1, baudrate=500000), 
    baudrate=500000,
    auto_restart=True
)

print("CAN bus initialized")

while True:
    # Listen for CAN messages
    with canio.Listener(can_bus) as listener:
        message = listener.receive(timeout=1.0)
        if message is not None:
            led.value = True
            print(f"Message ID: {message.id}")
            print(f"Message Data: {message.data}")
            time.sleep(0.1)
        else:
            led.value = False

    time.sleep(0.1)
