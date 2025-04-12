#!/usr/bin/env python3
"""
Nissan 370Z CAN Bus Decoder - Command Line Interface

This script provides a command-line interface for decoding CAN bus data from a Nissan 370Z
using either live serial input or log files.
"""

import argparse
import os
import re
import time
import json
import csv
import signal
import sys
import threading
import queue
from collections import deque
from datetime import datetime
from pathlib import Path
import sqlite3

try:
    import serial
    import pandas as pd
    import matplotlib.pyplot as plt
    from tabulate import tabulate
    import curses
except ImportError:
    print("Required packages not found. Please install them with:")
    print("pip install pyserial pandas matplotlib tabulate")
    sys.exit(1)

# Default configuration
DEFAULT_PORT = '/dev/ttyACM0'
DEFAULT_BAUD = 115200
DEFAULT_DB_PATH = 'logs/can_database.db'
DEFAULT_LOG_DIR = 'logs'


class CANMessageParser:
    """Parser for CAN bus messages from the Nissan 370Z"""
    
    def __init__(self, ids_file='candata/ids_of_interest.csv'):
        """Initialize the parser"""
        self.pattern = re.compile(r"(\d+\.\d+)\s+RX:\s+\[(\w+)\]\((\w+)\)\s+(.*)")
        self.ids_lookup = self._load_ids(ids_file)
        
    def _load_ids(self, ids_file):
        """Load CAN IDs from CSV file"""
        ids_lookup = {}
        try:
            with open(ids_file, 'r') as f:
                reader = csv.reader(f, delimiter=';')
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 4:
                        can_id_hex = row[0].lower().strip()
                        can_id_int = int(can_id_hex, 16) if can_id_hex.startswith('0x') else int(can_id_hex, 16)
                        ids_lookup[can_id_int] = {
                            'source': row[1],
                            'frequency': row[2],
                            'data_bytes': row[3]
                        }
            print(f"Loaded {len(ids_lookup)} CAN IDs for decoding")
        except Exception as e:
            print(f"Warning: Could not load IDs file: {e}")
        return ids_lookup
        
    def parse_line(self, line):
        """Parse a line from the CAN bus log"""
        match = self.pattern.match(line)
        if not match:
            return None
        
        timestamp, can_id_hex, msg_type, data_hex = match.groups()
        
        # Convert hex values to integers
        can_id = int(can_id_hex, 16)
        
        # Parse the data bytes
        data_bytes = [int(byte, 16) for byte in data_hex.split() if byte.strip()]
        
        return {
            'timestamp': float(timestamp),
            'can_id': can_id,
            'can_id_hex': f"0x{can_id:X}",
            'msg_type': msg_type,
            'data': data_bytes,
            'raw': line.strip()
        }
    
    def decode_message(self, message):
        """Decode a CAN message based on its ID"""
        if message is None:
            return None
        
        # Add basic info
        decoded = message.copy()
        can_id = message['can_id']
        data = message['data']
        
        # Add lookup info if available
        if can_id in self.ids_lookup:
            decoded['source'] = self.ids_lookup[can_id]['source']
            decoded['frequency'] = self.ids_lookup[can_id]['frequency']
        else:
            decoded['source'] = 'Unknown'
            decoded['frequency'] = 'Unknown'
        
        # Decode specific CAN IDs
        if can_id == 0x180:  # Engine RPM, Throttle
            if len(data) >= 8:
                rpm_raw = (data[0] << 8) + data[1]  # Bytes A, B
                decoded['rpm'] = rpm_raw / 8  # Apply scaling factor to get correct RPM
                decoded['throttle_pct'] = round((data[5] / 255) * 100, 1)  # Byte F
        
        elif can_id == 0x1F9:  # Engine RPM
            if len(data) >= 4:
                rpm_raw = (data[2] << 8) + data[3]  # Bytes C, D
                decoded['rpm'] = rpm_raw / 8  # Apply scaling factor to get correct RPM
        
        elif can_id == 0x280:  # Vehicle Speed
            if len(data) >= 6:
                # Calculate speed from bytes E and F
                speed_raw = (data[4] << 8) + data[5]
                decoded['speed_kph'] = speed_raw / 100  # Approximate conversion
                decoded['speed_mph'] = decoded['speed_kph'] * 0.621371
        
        elif can_id == 0x002:  # Steering Angle
            if len(data) >= 2:
                steering_raw = (data[1] << 8) + data[0]
                if steering_raw > 32767:
                    decoded['steering_angle'] = -((65535 - steering_raw) / 10)
                else:
                    decoded['steering_angle'] = steering_raw / 10
        
        elif can_id == 0x551:  # Engine Temp, Cruise Control
            if len(data) >= 6:
                decoded['engine_temp'] = data[0] - 40  # Approximate Celsius conversion
                decoded['cruise_setpoint_kph'] = data[4] if data[4] > 0 else None
                decoded['cruise_status'] = 'Active' if data[5] == 2 else 'Inactive'
        
        elif can_id == 0x216:  # Clutch Position
            if len(data) >= 1:
                if data[0] == 100:
                    decoded['clutch'] = 'Engaged'
                elif data[0] == 108:
                    decoded['clutch'] = 'Pressed'
                else:
                    decoded['clutch'] = f'Unknown ({data[0]})'
        
        elif can_id == 0x421:  # Gear Position
            if len(data) >= 1:
                gear_value = data[0]
                if gear_value == 24:
                    decoded['gear'] = 'Neutral'
                elif gear_value == 128:
                    decoded['gear'] = '1'
                elif gear_value == 16:
                    decoded['gear'] = 'R'
                else:
                    decoded['gear'] = f'Unknown ({gear_value})'
        
        return decoded


class CANDatabase:
    """Database for storing CAN messages"""
    
    def __init__(self, db_path=DEFAULT_DB_PATH):
        """Initialize the database"""
        self.db_path = db_path
        Path(db_path).parent.mkdir(exist_ok=True)
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Create tables if they don't exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            can_id INTEGER,
            can_id_hex TEXT,
            message_type TEXT,
            data BLOB,
            raw_text TEXT,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS decoded_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            can_id INTEGER,
            parameter TEXT,
            value REAL,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.conn.commit()
        
    def insert_raw_message(self, message, session_id):
        """Insert a raw message into the database"""
        self.cursor.execute(
            "INSERT INTO raw_messages (timestamp, can_id, can_id_hex, message_type, data, raw_text, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                message['timestamp'],
                message['can_id'],
                message['can_id_hex'],
                message['msg_type'],
                json.dumps(message['data']),
                message['raw'],
                session_id
            )
        )
        self.conn.commit()
    
    def insert_decoded_values(self, decoded, session_id):
        """Insert decoded values into the database"""
        # Only insert numeric decoded values
        for key, value in decoded.items():
            if isinstance(value, (int, float)) and key not in ['timestamp', 'can_id']:
                self.cursor.execute(
                    "INSERT INTO decoded_values (timestamp, can_id, parameter, value, session_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        decoded['timestamp'],
                        decoded['can_id'],
                        key,
                        value,
                        session_id
                    )
                )
        self.conn.commit()
    
    def close(self):
        """Close the database connection"""
        self.conn.close()


class CANFileReader:
    """Read CAN messages from a log file"""
    
    def __init__(self, file_path, parser=None):
        """Initialize the file reader"""
        self.file_path = file_path
        self.parser = parser or CANMessageParser()
        
    def read_all(self):
        """Read all messages from the file"""
        messages = []
        try:
            with open(self.file_path, 'r') as file:
                for line in file:
                    message = self.parser.parse_line(line)
                    if message:
                        decoded = self.parser.decode_message(message)
                        if decoded:
                            messages.append(decoded)
            print(f"Read {len(messages)} messages from {self.file_path}")
        except Exception as e:
            print(f"Error reading file: {e}")
        return messages
    
    def read_generator(self):
        """Generator to read messages from the file one by one"""
        try:
            with open(self.file_path, 'r') as file:
                for line in file:
                    message = self.parser.parse_line(line)
                    if message:
                        decoded = self.parser.decode_message(message)
                        if decoded:
                            yield decoded
        except Exception as e:
            print(f"Error reading file: {e}")


class CANSerialReader:
    """Read CAN messages from a serial connection"""
    
    def __init__(self, port=DEFAULT_PORT, baudrate=DEFAULT_BAUD, timeout=1, parser=None):
        """Initialize the serial reader"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.parser = parser or CANMessageParser()
        self.running = False
        self.message_queue = queue.Queue(maxsize=1000)  # Limit queue size to prevent memory issues
        self.thread = None
    
    def connect(self):
        """Connect to the serial port"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            return True
        except Exception as e:
            print(f"Error connecting to serial port: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the serial port"""
        if self.serial and self.serial.is_open:
            self.serial.close()
    
    def _read_thread(self):
        """Thread function to read messages from the serial port"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='replace')
                    message = self.parser.parse_line(line)
                    if message:
                        decoded = self.parser.decode_message(message)
                        if decoded and not self.message_queue.full():
                            self.message_queue.put(decoded)
                else:
                    time.sleep(0.01)  # Small delay to prevent CPU hogging
            except Exception as e:
                print(f"Error reading from serial port: {e}")
                time.sleep(1)  # Wait before retrying
    
    def start(self):
        """Start reading messages"""
        if not self.serial:
            if not self.connect():
                return False
        
        self.running = True
        self.thread = threading.Thread(target=self._read_thread)
        self.thread.daemon = True
        self.thread.start()
        return True
    
    def stop(self):
        """Stop reading messages"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.disconnect()
    
    def get_message(self, block=True, timeout=None):
        """Get a message from the queue"""
        try:
            return self.message_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None


class CANMonitor:
    """Monitor and display CAN messages in real-time"""
    
    def __init__(self, screen=None, db_path=DEFAULT_DB_PATH, history_length=100):
        """Initialize the monitor"""
        self.screen = screen
        self.db = CANDatabase(db_path) if db_path else None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.running = False
        self.history_length = history_length
        
        # Store latest values for key parameters
        self.latest_values = {
            'rpm': 0,
            'speed_kph': 0,
            'throttle_pct': 0,
            'steering_angle': 0,
            'engine_temp': 0,
            'gear': 'N',
            'clutch': 'Engaged',
            'cruise_status': 'Inactive',
            'cruise_setpoint_kph': 0,
        }
        
        # Message history for each CAN ID
        self.message_history = {}
        
        # Initialize curses colors if screen is provided
        if screen:
            curses.start_color()
            curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Normal
            curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK) # Warning
            curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)    # Error/Alert
            curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Info
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Header
    
    def update(self, message):
        """Update with a new message"""
        # Update database
        if self.db:
            self.db.insert_raw_message(message, self.session_id)
            self.db.insert_decoded_values(message, self.session_id)
        
        # Update latest values
        can_id = message['can_id_hex']
        for key in self.latest_values:
            if key in message:
                self.latest_values[key] = message[key]
        
        # Update message history
        if can_id not in self.message_history:
            self.message_history[can_id] = deque(maxlen=self.history_length)
        self.message_history[can_id].append(message)
        
        # Update screen if available
        if self.screen:
            self._update_screen()
    
    def _update_screen(self):
        """Update the curses screen with latest values"""
        if not self.screen:
            return
            
        screen = self.screen
        screen.clear()
        
        # Get screen dimensions
        height, width = screen.getmaxyx()
        
        # Draw header
        header = f" Nissan 370Z CAN Bus Monitor - Session: {self.session_id} "
        screen.addstr(0, (width - len(header)) // 2, header, curses.color_pair(5) | curses.A_BOLD)
        
        # Section 1: Key vehicle information (top left)
        screen.addstr(2, 2, "Vehicle Status:", curses.A_UNDERLINE)
        screen.addstr(3, 4, f"RPM: {self.latest_values['rpm']}")
        screen.addstr(4, 4, f"Speed: {self.latest_values['speed_kph']:.1f} km/h ({self.latest_values['speed_kph'] * 0.621371:.1f} mph)")
        screen.addstr(5, 4, f"Throttle: {self.latest_values['throttle_pct']:.1f}%")
        screen.addstr(6, 4, f"Steering: {self.latest_values['steering_angle']:.1f}°")
        screen.addstr(7, 4, f"Engine Temp: {self.latest_values['engine_temp']}°C")
        screen.addstr(8, 4, f"Gear: {self.latest_values['gear']}")
        screen.addstr(9, 4, f"Clutch: {self.latest_values['clutch']}")
        
        # Section 2: Recent messages (top right)
        screen.addstr(2, width // 2 + 2, "Recent Messages:", curses.A_UNDERLINE)
        
        # Get most recent messages across all CAN IDs
        recent_messages = []
        for id_msgs in self.message_history.values():
            if id_msgs:
                recent_messages.append(id_msgs[-1])
        
        # Sort by timestamp (most recent first)
        recent_messages.sort(key=lambda x: x['timestamp'], reverse=True)
        
        for i, msg in enumerate(recent_messages[:6]):  # Show up to 6 messages
            if 3 + i < height - 2:  # Ensure we don't go off screen
                can_id = msg['can_id_hex']
                source = msg['source']
                data_str = ' '.join([f'{b:02X}' for b in msg['data']])
                msg_str = f"{can_id} ({source}): {data_str[:20]}{'...' if len(data_str) > 20 else ''}"
                screen.addstr(3 + i, width // 2 + 4, msg_str)
        
        # Section 3: Message statistics (bottom)
        screen.addstr(height - 10, 2, "Message Statistics:", curses.A_UNDERLINE)
        
        # Show counts for most frequent CAN IDs
        id_counts = {can_id: len(msgs) for can_id, msgs in self.message_history.items()}
        sorted_ids = sorted(id_counts.items(), key=lambda x: x[1], reverse=True)
        
        for i, (can_id, count) in enumerate(sorted_ids[:5]):  # Show top 5 IDs
            if height - 9 + i < height - 2:  # Ensure we don't go off screen
                source = self.message_history[can_id][-1]['source'] if self.message_history[can_id] else 'Unknown'
                screen.addstr(height - 9 + i, 4, f"{can_id} ({source}): {count} messages")
        
        # Footer
        footer_text = "Press 'q' to quit | 's' to save log | 'h' for help"
        screen.addstr(height - 2, (width - len(footer_text)) // 2, footer_text, curses.A_REVERSE)
        
        screen.refresh()
    
    def print_message(self, message):
        """Print a message to the console in non-curses mode"""
        can_id = message['can_id_hex']
        source = message['source']
        timestamp = message['timestamp']
        
        # Format data as hex
        data_str = ' '.join([f'{b:02X}' for b in message['data']])
        
        # Basic message info
        print(f"[{timestamp:.3f}] {can_id} ({source}): {data_str}")
        
        # Print decoded values
        for key, value in message.items():
            if key not in ['timestamp', 'can_id', 'can_id_hex', 'msg_type', 'data', 'raw', 'source', 'frequency']:
                print(f"  {key}: {value}")
    
    def close(self):
        """Close the monitor and resources"""
        if self.db:
            self.db.close()


def monitor_file(file_path, use_curses=True, db_path=DEFAULT_DB_PATH, replay_speed=1.0):
    """Monitor CAN messages from a file"""
    parser = CANMessageParser()
    reader = CANFileReader(file_path, parser)
    messages = reader.read_all()
    
    if not messages:
        print(f"No valid CAN messages found in {file_path}")
        return
    
    # Sort messages by timestamp
    messages.sort(key=lambda x: x['timestamp'])
    
    if use_curses:
        # Initialize curses and run the monitor
        curses.wrapper(lambda screen: _replay_with_curses(screen, messages, db_path, replay_speed))
    else:
        # Run in simple console mode
        _replay_without_curses(messages, db_path, replay_speed)


def _replay_with_curses(screen, messages, db_path, replay_speed):
    """Replay messages with curses interface"""
    monitor = CANMonitor(screen, db_path)
    
    # Hide cursor and set nodelay mode for non-blocking input
    curses.curs_set(0)
    screen.nodelay(True)
    
    # Get reference timestamp
    start_time = time.time()
    ref_timestamp = messages[0]['timestamp']
    
    try:
        i = 0
        while i < len(messages):
            # Check for user input
            try:
                key = screen.getch()
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    # Save current state (implement if needed)
                    pass
            except:
                pass
            
            # Get current message
            message = messages[i]
            
            # Calculate if it's time to process this message
            elapsed = (time.time() - start_time) * replay_speed
            if elapsed >= (message['timestamp'] - ref_timestamp):
                monitor.update(message)
                i += 1
            else:
                # Small sleep to avoid CPU hogging
                time.sleep(0.01)
        
        # Show completion message
        height, width = screen.getmaxyx()
        screen.addstr(height - 3, 2, "Replay complete. Press any key to exit.", curses.color_pair(4) | curses.A_BOLD)
        screen.refresh()
        screen.nodelay(False)
        screen.getch()
    
    finally:
        monitor.close()


def _replay_without_curses(messages, db_path, replay_speed):
    """Replay messages without curses interface"""
    monitor = CANMonitor(screen=None, db_path=db_path)
    
    # Get reference timestamp
    start_time = time.time()
    ref_timestamp = messages[0]['timestamp']
    
    try:
        for i, message in enumerate(messages):
            # Calculate sleep time
            if i > 0:
                time_diff = message['timestamp'] - messages[i-1]['timestamp']
                time.sleep(max(0, time_diff / replay_speed))
            
            # Process message
            monitor.print_message(message)
            monitor.update(message)
            
            # Handle interrupt
            if i % 10 == 0 and sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    break
    
    except KeyboardInterrupt:
        print("\nReplay interrupted by user.")
    
    finally:
        monitor.close()


def monitor_serial(port=DEFAULT_PORT, baudrate=DEFAULT_BAUD, use_curses=True, db_path=DEFAULT_DB_PATH):
    """Monitor CAN messages from a serial port"""
    parser = CANMessageParser()
    reader = CANSerialReader(port, baudrate, parser=parser)
    
    if not reader.connect():
        print(f"Failed to connect to {port}")
        return
    
    print(f"Connected to {port} at {baudrate} baud")
    reader.start()
    
    if use_curses:
        # Initialize curses and run the monitor
        curses.wrapper(lambda screen: _monitor_with_curses(screen, reader, db_path))
    else:
        # Run in simple console mode
        _monitor_without_curses(reader, db_path)
    
    reader.stop()


def _monitor_with_curses(screen, reader, db_path):
    """Monitor with curses interface"""
    monitor = CANMonitor(screen, db_path)
    
    # Hide cursor and set nodelay mode for non-blocking input
    curses.curs_set(0)
    screen.nodelay(True)
    
    try:
        while True:
            # Check for user input
            try:
                key = screen.getch()
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    # Save current state (implement if needed)
                    pass
            except:
                pass
            
            # Get message from reader
            message = reader.get_message(block=False)
            if message:
                monitor.update(message)
            else:
                # Small sleep to avoid CPU hogging
                time.sleep(0.01)
    
    finally:
        monitor.close()


def _monitor_without_curses(reader, db_path):
    """Monitor without curses interface"""
    monitor = CANMonitor(screen=None, db_path=db_path)
    
    try:
        while True:
            # Get message from reader
            message = reader.get_message(timeout=0.1)
            if message:
                monitor.print_message(message)
                monitor.update(message)
            
            # Check for keyboard interrupt
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    break
    
    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user.")
    
    finally:
        monitor.close()


def export_to_csv(file_path, output_path=None):
    """Export decoded data to CSV"""
    if output_path is None:
        # Generate output filename based on input
        base_name = Path(file_path).stem
        output_path = f"{DEFAULT_LOG_DIR}/{base_name}_decoded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Ensure logs directory exists
    Path(output_path).parent.mkdir(exist_ok=True)
    
    # Read and decode all messages
    parser = CANMessageParser()
    reader = CANFileReader(file_path, parser)
    messages = reader.read_all()
    
    if not messages:
        print(f"No valid CAN messages found in {file_path}")
        return False
    
    # Convert to DataFrame for easier CSV formatting
    df_rows = []
    for msg in messages:
        row = {
            'timestamp': msg['timestamp'],
            'can_id': msg['can_id_hex'],
            'source': msg['source'],
            'raw_data': ' '.join([f'{b:02X}' for b in msg['data']])
        }
        
        # Add decoded fields
        for key, value in msg.items():
            if key not in ['timestamp', 'can_id', 'can_id_hex', 'msg_type', 'data', 'raw', 'source', 'frequency']:
                row[key] = value
        
        df_rows.append(row)
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(df_rows)
    df.to_csv(output_path, index=False)
    
    print(f"Exported {len(df)} decoded messages to {output_path}")
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Nissan 370Z CAN Bus Decoder')
    
    # Input source arguments
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-f', '--file', help='Read CAN data from a log file')
    input_group.add_argument('-s', '--serial', action='store_true', help='Read CAN data from serial port')
    
    # Serial port options
    parser.add_argument('-p', '--port', default=DEFAULT_PORT, help=f'Serial port (default: {DEFAULT_PORT})')
    parser.add_argument('-b', '--baud', type=int, default=DEFAULT_BAUD, help=f'Baud rate (default: {DEFAULT_BAUD})')
    
    # Display options
    parser.add_argument('-c', '--console', action='store_true', help='Use simple console output instead of curses')
    parser.add_argument('-r', '--replay-speed', type=float, default=1.0, help='Replay speed multiplier for file input (default: 1.0)')
    
    # Database options
    parser.add_argument('-d', '--database', default=DEFAULT_DB_PATH, help=f'Path to SQLite database (default: {DEFAULT_DB_PATH})')
    parser.add_argument('--no-db', action='store_true', help='Disable database logging')
    
    # Export option
    parser.add_argument('-e', '--export', help='Export file to CSV (specify output path)')
    
    args = parser.parse_args()
    
    # Handle export mode
    if args.export and args.file:
        export_to_csv(args.file, args.export)
        return
    
    # Set database path
    db_path = None if args.no_db else args.database
    
    # Monitor based on input source
    try:
        if args.file:
            monitor_file(args.file, not args.console, db_path, args.replay_speed)
        elif args.serial:
            monitor_serial(args.port, args.baud, not args.console, db_path)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")


if __name__ == '__main__':
    if 'select' not in globals():
        import select  # Needs to be imported after main for proper error handling
    main()