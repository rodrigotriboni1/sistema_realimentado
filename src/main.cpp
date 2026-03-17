#include <Arduino.h>
#include <math.h>

// Pinos
#define PWM_TEMP     14
#define PWM_COOLER   25
#define SENSOR_TEMP  26
#define SENSOR_FLUXO 27

// Constantes do NTC
const double VS      = 3.3;
const double R1      = 10000.0;
const double BETA    = 3950.0;
const double T0_K    = 298.15;
const double R0      = 10000.0;
const int    ADC_RES = 4095;
// Ajuste temporario: leitura atual esta ~metade da real no hardware
const float TEMP_GAIN = 2.0f;
const float TEMP_OFFSET_C = 0.0f;
const int   TEMP_ADC_SAMPLES = 16;

// Setpoints
const float SP_TEMP = 40.0f;
const float SP_VAZAO_COOLER_ON = 5.0f;
const float SP_VAZAO_COOLER_OFF = 0.0f;
const float GANHO_PID_FLUXO = 1.8f;  // >1.0 deixa a malha de vazao mais rapida

// Amostragem (novo PID identificado)
const unsigned long TS_TEMP_MS  = 2000;  // Ts temperatura = 2.0 s
const unsigned long TS_FLUXO_MS = 100;   // Ts vazao = 0.1 s

// Janela de estabilizacao
const int   ESTAB_ALVO       = 15;
const float BANDA_TEMP_C     = 0.5f;
const float BANDA_VAZAO_LMIN = 0.4f;

// Maquina de estados do ensaio PID
enum Fase { AQUECENDO, COOLER_ON, ESTABILIZADO };
Fase faseAtual = AQUECENDO;
const char* nomesFase[] = { "AQUECENDO", "COOLER_ON", "ESTABILIZADO" };

// Estrutura do controlador discreto: (b0 z^2 + b1 z + b2) / (z^2 + a1 z + a2)
struct PIDDisc {
  float b0, b1, b2, a1, a2;
  float e1, e2;
  float u1, u2;
};

// --- Novos coeficientes vindos do MATLAB ---
PIDDisc pidTemp = {
  7.8860f, -11.6949f, 3.8760f,
  -0.6000f, -0.4000f,
  0.0f, 0.0f, 0.0f, 0.0f
};

PIDDisc pidFluxo = {
  0.0390f, -0.0336f, -0.0038f,
  -1.6000f, 0.6000f,
  0.0f, 0.0f, 0.0f, 0.0f
};

volatile int pulsos = 0;
int pulsosUltAmostra = 0;
unsigned long tempoAntTemp = 0;
unsigned long tempoAntFluxo = 0;

float temperaturaC = 25.0f;
float vazaoLmin    = 0.0f;
float spVazao      = SP_VAZAO_COOLER_OFF;

int dcResistencia = 0;
int dcCooler      = 0;
int estabContagem = 0;

void IRAM_ATTR lerFluxo() { pulsos++; }

static float clampf(float x, float mn, float mx) {
  if (x < mn) return mn;
  if (x > mx) return mx;
  return x;
}

static float atualizarPID(PIDDisc& c, float erro) {
  float u = c.b0 * erro + c.b1 * c.e1 + c.b2 * c.e2
          - c.a1 * c.u1 - c.a2 * c.u2;

  u = clampf(u, 0.0f, 100.0f);

  c.e2 = c.e1;
  c.e1 = erro;
  c.u2 = c.u1;
  c.u1 = u;
  return u;
}

static float lerTemperaturaC() {
  long soma = 0;
  for (int i = 0; i < TEMP_ADC_SAMPLES; i++) {
    soma += analogRead(SENSOR_TEMP);
  }
  float leitura = (float)soma / TEMP_ADC_SAMPLES;
  double vout = (leitura * VS) / ADC_RES;
  if (vout <= 0.0) vout = 0.001;
  if ((VS - vout) < 0.001) vout = VS - 0.001;
  double rt = R1 * vout / (VS - vout);
  float tempCraw = (float)(1.0 / (1.0 / T0_K + log(rt / R0) / BETA) - 273.15);
  return tempCraw * TEMP_GAIN + TEMP_OFFSET_C;
}

void setup() {
  Serial.begin(115200);

  pinMode(SENSOR_TEMP, INPUT);
  pinMode(SENSOR_FLUXO, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(SENSOR_TEMP, ADC_11db);

  ledcAttach(PWM_TEMP, 1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);
  ledcWrite(PWM_TEMP, 0);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  unsigned long agora = millis();
  tempoAntTemp = agora;
  tempoAntFluxo = agora;

  Serial.println(">>> Controle PID discreto iniciado.");
  Serial.println(">>> Fase AQUECENDO: SP_Temp=40C, cooler OFF.");
}

void loop() {
  unsigned long agora = millis();

  // Malha de vazao (Ts = 0.1 s)
  if (agora - tempoAntFluxo >= TS_FLUXO_MS) {
    float dt = (agora - tempoAntFluxo) / 1000.0f;
    tempoAntFluxo = agora;

    noInterrupts();
    int p = pulsos;
    pulsos = 0;
    interrupts();

    pulsosUltAmostra = p;
    vazaoLmin = (p / dt) / 7.5f;

    if (faseAtual == AQUECENDO) {
      dcCooler = 0;
      pidFluxo.e1 = pidFluxo.e2 = 0.0f;
      pidFluxo.u1 = pidFluxo.u2 = 0.0f;
    } else {
      float erroF = (spVazao - vazaoLmin) * GANHO_PID_FLUXO;
      float uFluxo = atualizarPID(pidFluxo, erroF);
      dcCooler = (int)roundf(uFluxo);
    }
    ledcWrite(PWM_COOLER, map(dcCooler, 0, 100, 0, 255));
  }

  // Malha de temperatura + log (Ts = 2.0 s)
  if (agora - tempoAntTemp >= TS_TEMP_MS) {
    tempoAntTemp = agora;
    temperaturaC = lerTemperaturaC();

    float erroT = SP_TEMP - temperaturaC;
    float uTemp = atualizarPID(pidTemp, erroT);
    dcResistencia = (int)roundf(uTemp);
    ledcWrite(PWM_TEMP, map(dcResistencia, 0, 100, 0, 255));

    // Maquina de fases para experimento de variacao de SP do cooler
    bool tempOk = fabsf(erroT) <= BANDA_TEMP_C;
    bool vazaoOk = fabsf(spVazao - vazaoLmin) <= BANDA_VAZAO_LMIN;

    switch (faseAtual) {
      case AQUECENDO:
        spVazao = SP_VAZAO_COOLER_OFF;
        if (tempOk) estabContagem++;
        else estabContagem = 0;
        if (estabContagem >= ESTAB_ALVO) {
          faseAtual = COOLER_ON;
          estabContagem = 0;
          spVazao = SP_VAZAO_COOLER_ON;
          Serial.println(">>> Temperatura estabilizada. Entrando em COOLER_ON (SP_Vazao = 5 L/min).");
        }
        break;

      case COOLER_ON:
        spVazao = SP_VAZAO_COOLER_ON;
        if (tempOk && vazaoOk) estabContagem++;
        else estabContagem = 0;
        if (estabContagem >= ESTAB_ALVO) {
          faseAtual = ESTABILIZADO;
          estabContagem = ESTAB_ALVO;
          Serial.println(">>> Sistema estabilizado com ambos PIDs ativos.");
        }
        break;

      case ESTABILIZADO:
        spVazao = SP_VAZAO_COOLER_ON;
        break;
    }

    Serial.printf(
      "Temp: %.2f C | SP_Temp: %.1f C | Fase: %s | Estab: %d/%d | "
      "Vazao: %.2f L/min | SP_Vazao: %.1f | DC_Cooler: %d%% | DC_Resist: %d%% | Resistencia: %s\n",
      temperaturaC, SP_TEMP, nomesFase[faseAtual], estabContagem, ESTAB_ALVO,
      vazaoLmin, spVazao, dcCooler, dcResistencia, (dcResistencia > 0 ? "ON" : "OFF")
    );
  }
}
