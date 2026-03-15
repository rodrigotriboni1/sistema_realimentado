#include <Arduino.h>

#define PWM_TEMP     14
#define PWM_COOLER   25
#define SENSOR_FLUXO 27

const int DC_TEMP   = 0;    // resistencia desligada
const int DC_COOLER = 100;  // cooler no maximo

volatile int pulsos = 0;
unsigned long tempoAnt = 0;

void IRAM_ATTR lerFluxo() { pulsos++; }

void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_FLUXO, INPUT);
  ledcAttach(PWM_TEMP,   1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP,   0);    // 0%
  ledcWrite(PWM_COOLER, 255);  // 100%

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  Serial.printf(">>> Ensaio open-loop: DC_Temp=%d%% | DC_Cooler=%d%%\n",
                DC_TEMP, DC_COOLER);
}

void loop()
{
  unsigned long agora = millis();

  if (agora - tempoAnt >= 200)
  {
    float dt = (agora - tempoAnt) / 1000.0f;
    tempoAnt = agora;

    int p    = pulsos;
    pulsos   = 0;

    float freq  = p / dt;
    float vazao = freq / 7.5f;  // L/min (fator do sensor YF-S201)

    Serial.printf("Vazao: %.2f L/min | Pulsos: %d | DC_Temp: %d%% | DC_Cooler: %d%%\n",
                  vazao, p, DC_TEMP, DC_COOLER);
  }
}
