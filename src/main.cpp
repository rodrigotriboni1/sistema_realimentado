#include <Arduino.h>

// Pinos
#define PWM_TEMP     14
#define PWM_COOLER   25
#define SENSOR_TEMP  26
#define SENSOR_FLUXO 27

// Constantes do NTC
const double Vs   = 3.3;
const double R1   = 10000;
const double Beta = 3950;
const double To   = 298.15;
const double Ro   = 10000;
const int    ADC_RES = 4095;

// Deteccao de estabilizacao por janela deslizante
const int   ESTAB_ALVO  = 30;     // leituras consecutivas dentro da banda
const float ESTAB_BANDA = 0.3f;  // erro maximo entre temp atual e anterior (°C)

// Maquina de estados
enum Fase { AQUECENDO, COOLER_MAX, ESTABILIZADO };
Fase faseAtual = AQUECENDO;
const char* nomesFase[] = { "AQUECENDO", "COOLER_MAX", "ESTABILIZADO" };

int   estabContagem = 0;
float tempAnterior  = -999.0f;

volatile int pulsos = 0;
unsigned long tempoAntTemp  = 0;
unsigned long tempoAntFluxo = 0;
float vazao = 0.0f;

void IRAM_ATTR lerFluxo() { pulsos++; }

void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_TEMP,  INPUT);
  pinMode(SENSOR_FLUXO, INPUT);

  ledcAttach(PWM_TEMP,   1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  // Inicia com resistencia no maximo e cooler desligado
  ledcWrite(PWM_TEMP,   255);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  Serial.println(">>> Ensaio: Resist. 100% -> estabilizar -> Cooler 100% -> estabilizar");
}

void loop()
{
  unsigned long agora = millis();

  // ── Vazao: Ts = 200ms ──────────────────────────────────────────────────────
  if (agora - tempoAntFluxo >= 200)
  {
    float dt    = (agora - tempoAntFluxo) / 1000.0f;
    tempoAntFluxo = agora;
    int p = pulsos;
    pulsos = 0;
    vazao = (p / dt) / 7.5f;
  }

  // ── Temperatura: Ts = 2000ms ───────────────────────────────────────────────
  if (agora - tempoAntTemp >= 2000)
  {
    tempoAntTemp = agora;

    // Leitura NTC
    int    leitura = analogRead(SENSOR_TEMP);
    double Vout    = (leitura * Vs) / ADC_RES;
    if (Vs - Vout < 0.01) Vout = Vs - 0.01;
    double Rt   = R1 * Vout / (Vs - Vout);
    float  temp = (float)(1.0 / (1.0/To + log(Rt/Ro)/Beta) - 273.15);

    // Criterio de estabilizacao: variacao entre leituras <= ESTAB_BANDA
    bool estavel = (tempAnterior > -900.0f) &&
                   (fabsf(temp - tempAnterior) <= ESTAB_BANDA);
    tempAnterior = temp;

    // Maquina de estados
    switch (faseAtual)
    {
      case AQUECENDO:
        if (estavel) estabContagem++;
        else         estabContagem = 0;
        if (estabContagem >= ESTAB_ALVO)
        {
          faseAtual     = COOLER_MAX;
          estabContagem = 0;
          ledcWrite(PWM_COOLER, 255);  // liga cooler no maximo
          Serial.println(">>> Temperatura estabilizada! Ligando cooler no maximo.");
        }
        break;

      case COOLER_MAX:
        if (estavel) estabContagem++;
        else         estabContagem = 0;
        if (estabContagem >= ESTAB_ALVO)
        {
          faseAtual     = ESTABILIZADO;
          estabContagem = ESTAB_ALVO;
          Serial.println(">>> Sistema estabilizado com cooler no maximo!");
        }
        break;

      case ESTABILIZADO:
        break;
    }

    int dcTemp   = 100;
    int dcCooler = (faseAtual >= COOLER_MAX) ? 100 : 0;

    Serial.printf(
      "Temp: %.2f C | Fase: %s | Estab: %d/%d | "
      "Vazao: %.2f L/min | DC_Temp: %d%% | DC_Cooler: %d%%\n",
      temp, nomesFase[faseAtual],
      estabContagem, ESTAB_ALVO,
      vazao, dcTemp, dcCooler
    );
  }
}
