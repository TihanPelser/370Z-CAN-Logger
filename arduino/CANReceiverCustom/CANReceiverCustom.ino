// Copyright (c) Sandeep Mistry. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#include <CAN.h>

void setup() {
  Serial.begin(115200);
  while (!Serial);

//  Serial.println("CAN Receiver");

  // start the CAN bus at 500 kbps
  if (!CAN.begin(500E3)) {
    Serial.println("Starting CAN failed!");
    while (1);
  }
}

void printByte(byte X) {

   if (X < 16) {Serial.print("0");}

   Serial.print(X, HEX);

}

void loop() {
  // try to parse packet
  int packetSize = CAN.parsePacket();

  if (packetSize) {
    // received a packet
//    Serial.print("Received ");

//    if (CAN.packetExtended()) {
//      Serial.print("extended ");
//    }

//    if (CAN.packetRtr()) {
      // Remote transmission request, packet contains no data
//      Serial.print("RTR ");
//    }

//    Serial.print("packet with id 0x");
    Serial.print(millis());
    Serial.print("-");
    Serial.print(CAN.packetId(), HEX);
//    Serial.print("-");

    if (CAN.packetRtr()) {
      Serial.print("-");
      Serial.print(CAN.packetDlc());
//      printByte(CAN.packetDlc());
    } else {
      // Serial.print("-");
      // Serial.print(packetSize);
//      printByte(packetSize);

      // only print packet data for non-RTR packets
      Serial.print("-");
      while (CAN.available()) {
        
//        Serial.print((char)CAN.read(), HEX);
        printByte(CAN.read());
      }
//      Serial.println();
    }

    Serial.println();
  }
}
