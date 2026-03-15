#include <Arduino.h>

// Pinos
#define PWM_TEMP     14
#define PWM_COOLER   25
#define SENSOR_TEMP  26
#define SENSOR_FLUXO 27

// Variáveis
const int resolution = 4095;
volatile int pulsos = 0;
unsigned long tempoAntFluxo = 0, tempoAntTemp = 0, tempoAtual = 0;
int dutycycleCooler = 0, dutycycleTemp = 0;
float temperatura = 0, vazao = 0;
bool estadoResistencia = false;

// Constantes do NTC
double Vs   = 3.3;
double R1   = 10000;
double Beta = 3950;
double To   = 298.15;
double Ro   = 10000;

// Setpoints fixos
const float SP_TEMPERATURA    = 40.0f;
const float SP_VAZAO_COOLER   = 5.0f;
float spVazao = 0.0f;  // começa com cooler desligado

// Detecção de estabilização
const int   ESTAB_ALVO  = 5;      // leituras consecutivas dentro da faixa
const float ESTAB_BANDA = 0.5f;   // ±0.5 °C em torno do SP
int estabContagem = 0;

// Máquina de estados
enum Fase { AQUECENDO, COOLER_ON, ESTABILIZADO };
Fase faseAtual = AQUECENDO;
const char* nomesFase[] = { "AQUECENDO", "COOLER_ON", "ESTABILIZADO" };

// --- PID Vazão (PIDF): Ts = 0.2s ---
// H(z) = (0.05z² - 0.03277z + 0.002777) / (z² - 0.7z - 0.3)
const float bF0 =  0.05,    bF1 = -0.03277, bF2 =  0.002777;
const float aF1 = -0.7,     aF2 = -0.3;
float eF[3] = {0, 0, 0};
float uF[3] = {0, 0, 0};

// --- PID Temperatura (PIDt): Ts = 2s ---
// H(z) = (8.5z² - 10.99z + 2.531) / (z² - 0.5z - 0.5)
const float bT0 =  8.5,     bT1 = -10.99,   bT2 =  2.531;
const float aT1 = -0.5,     aT2 = -0.5;
float eT[3] = {0, 0, 0};
float uT[3] = {0, 0, 0};

void IRAM_ATTR lerFluxo() { pulsos++; }

float saturar(float valor, float minimo, float maximo)
{
  if (valor > maximo) return maximo;
  if (valor < minimo) return minimo;
  return valor;
}

void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_TEMP,  INPUT);
  pinMode(SENSOR_FLUXO, INPUT);
  pinMode(PWM_TEMP,     OUTPUT);
  pinMode(PWM_COOLER,   OUTPUT);

  ledcAttach(PWM_TEMP,   1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP,   0);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);
}

void loop()
{
  tempoAtual = millis();

  // ---- PID Vazão: Ts = 200ms ----
  if (tempoAtual - tempoAntFluxo >= 200)
  {
    float dtFluxo = (tempoAtual - tempoAntFluxo) / 1000.0f;
    tempoAntFluxo = tempoAtual;

    float frequencia = pulsos / dtFluxo;
    vazao = frequencia / 7.5f;
    pulsos = 0;

    if (faseAtual >= COOLER_ON)
    {
      // Cooler ativo com PID de vazão
      eF[0] = spVazao - vazao;
      uF[0] = bF0*eF[0] + bF1*eF[1] + bF2*eF[2] - aF1*uF[1] - aF2*uF[2];
      uF[0] = saturar(uF[0], 0, 100);
      eF[2] = eF[1];  eF[1] = eF[0];
      uF[2] = uF[1];  uF[1] = uF[0];
      dutycycleCooler = (int)uF[0];
    }
    else
    {
      // Cooler desligado: zera saída e estado do PID
      dutycycleCooler = 0;
      for (int i = 0; i < 3; i++) { eF[i] = 0; uF[i] = 0; }
    }

    ledcWrite(PWM_COOLER, (dutycycleCooler * 255) / 100);
  }

  // ---- PID Temperatura: Ts = 2000ms ----
  if (tempoAtual - tempoAntTemp >= 2000)
  {
    tempoAntTemp = tempoAtual;

    int leituraADC = analogRead(SENSOR_TEMP);
    double Vout = (leituraADC * Vs) / resolution;
    if (Vs - Vout < 0.01) Vout = Vs - 0.01;
    double Rt = R1 * Vout / (Vs - Vout);
    temperatura = (float)(1.0 / (1.0/To + log(Rt/Ro)/Beta) - 273.15);

    // PID de temperatura (SP fixo em 40 °C durante todo o ensaio)
    eT[0] = SP_TEMPERATURA - temperatura;
    uT[0] = bT0*eT[0] + bT1*eT[1] + bT2*eT[2] - aT1*uT[1] - aT2*uT[2];
    uT[0] = saturar(uT[0], 0, 100);
    eT[2] = eT[1];  eT[1] = eT[0];
    uT[2] = uT[1];  uT[1] = uT[0];

    dutycycleTemp   = (int)uT[0];
    estadoResistencia = (dutycycleTemp > 0);
    ledcWrite(PWM_TEMP, (dutycycleTemp * 255) / 100);

    // --- Máquina de estados (verificada a cada Ts de temperatura) ---
    bool dentroFaixa = (fabsf(temperatura - SP_TEMPERATURA) <= ESTAB_BANDA);

    switch (faseAtual)
    {
      case AQUECENDO:
        if (dentroFaixa) estabContagem++;
        else             estabContagem = 0;
        if (estabContagem >= ESTAB_ALVO)
        {
          faseAtual     = COOLER_ON;
          spVazao       = SP_VAZAO_COOLER;
          estabContagem = 0;
          Serial.println(">>> Temperatura estabilizada em 40 C! Ligando cooler (SP_Vazao = 5.0 L/min)");
        }
        break;

      case COOLER_ON:
        if (dentroFaixa) estabContagem++;
        else             estabContagem = 0;
        if (estabContagem >= ESTAB_ALVO)
        {
          faseAtual     = ESTABILIZADO;
          estabContagem = ESTAB_ALVO;
          Serial.println(">>> Sistema totalmente estabilizado com cooler ligado!");
        }
        break;

      case ESTABILIZADO:
        break;
    }

    Serial.printf(
      "Temp: %.2f C | SP_Temp: %.1f C | Fase: %s | Estab: %d/%d | "
      "Vazao: %.2f L/min | SP_Vazao: %.1f | "
      "DC_Cooler: %d%% | DC_Resist: %d%% | Resistencia: %s\n",
      temperatura, SP_TEMPERATURA, nomesFase[faseAtual],
      estabContagem, ESTAB_ALVO,
      vazao, spVazao,
      dutycycleCooler, dutycycleTemp,
      estadoResistencia ? "ON" : "OFF"
    );
  }
}
