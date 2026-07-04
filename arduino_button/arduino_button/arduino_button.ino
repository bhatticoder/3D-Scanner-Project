const int buttonPin = 2; 
int lastButtonState = HIGH;

// FIXED: Added missing pin declarations for your stepper driver control
const int dirPin = 3;  // Assign to whatever digital pin you choose
const int stepPin = 4; // Assign to whatever digital pin you choose

void setup() {
  pinMode(buttonPin, INPUT_PULLUP);
  Serial.begin(9600); // Must match your Python 9600 baud rate configuration
  
  // If you are using a stepper driver (like an A4988), configure your output pins here:
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
}

void loop() {
  // 1. Handle incoming serial commands from Python
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'R') {
      
      // If you have a motor attached, put the step/pulse code here!
      delay(1500); // Simulates the duration of physical platform movement
      
      // Clear out any duplicate incoming data noise
      while(Serial.available() > 0) { Serial.read(); }
      
      // Send message back to release the Python execution lock
      Serial.println("STEP_DONE"); 
    }
  }

  // FIXED: Kept inside the loop() boundary context rather than falling to global scope
  // 2. Fallback support for manual tactile button presses
  int buttonState = digitalRead(buttonPin);
  if (buttonState == LOW && lastButtonState == HIGH) {
    delay(50); // Debounce delay
    if (digitalRead(buttonPin) == LOW) {
      Serial.println("CAPTURE"); 
    }
  }
  lastButtonState = buttonState;
} // <─── Exactly one closing brace at the very end of loop()
