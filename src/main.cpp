#include <Arduino.h>

#define PWM_TEMP   14
#define PWM_COOLER 25

void setup()
{
  Serial.begin(115200);

  ledcAttach(PWM_TEMP,   1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP,   255);  // 100%
  ledcWrite(PWM_COOLER,   0);  // 0%

  Serial.println("PWM_TEMP: 100% | PWM_COOLER: 0%");
}

void loop() {}
