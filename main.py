import can
import os

def main():
    # Configure the CAN interface for Makerbase CANable Pro
    bus = can.interface.Bus(interface='slcan', channel='/dev/ttyACM0', bitrate=500000)

    # Ensure the logs directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Create a log file with a timestamp
    log_file_path = os.path.join(log_dir, "can_log_2025-04-11.log")

    print("Listening on the CAN bus. Press Ctrl+C to stop.")

    try:
        with open(log_file_path, "w") as log_file:
            # Listen for messages on the CAN bus
            for msg in bus:
                log_entry = f"Timestamp: {msg.timestamp}, ID: {msg.arbitration_id:#x}, Data: {msg.data}\n"
                print(log_entry.strip())
                log_file.write(log_entry)
    except KeyboardInterrupt:
        print("Stopped listening to the CAN bus.")
    finally:
        bus.shutdown()

if __name__ == "__main__":
    main()
