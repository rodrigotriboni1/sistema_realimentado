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
const float TEMP_OFFSET_C = 0.0f;
const int   TEMP_ADC_SAMPLES = 16;

// Setpoints
const float SP_TEMP              = 40.0f;
const float SP_VAZAO_COOLER_ON   = 5.0f;
const float SP_VAZAO_COOLER_OFF  = 0.0f;
const float GANHO_PID_FLUXO      = 10.0f;
const int   MAX_STEP_PWM_COOLER  = 12;   // limite de variacao por ciclo da malha de vazao

// Amostragem
const unsigned long TS_TEMP_MS  = 2000;   // Ts temperatura = 2.0 s
const unsigned long TS_FLUXO_MS = 1000;   // Ts vazão = 1.0 s  (Ts do C_F no MATLAB)

// Janela de estabilizacao
const int   ESTAB_ALVO       = 15;
const float BANDA_TEMP_C     = 0.5f;
const float BANDA_VAZAO_LMIN = 0.4f;
const float TEMP_ENTRADA_COOLER_C = SP_TEMP - BANDA_TEMP_C; // proximo de 40 C

// Maquina de estados do ensaio PID
enum Fase { AQUECENDO, COOLER_ON, ESTABILIZADO };
Fase faseAtual = AQUECENDO;
const char* nomesFase[] = { "AQUECENDO", "COOLER_ON", "ESTABILIZADO" };

// ---------------------------------------------------------------------------
// Estrutura do controlador discreto de 2ª ordem
//   u(k) = b0*e(k) + b1*e(k-1) + b2*e(k-2)
//         - a1*u(k-1) - a2*u(k-2)
//
// Forma padrão da equação de diferenças (denominador mônico):
//   D(z) = z² + a1_matlab*z + a2_matlab
//   Na recorrência: u(k) = ... - a1_matlab*u(k-1) - a2_matlab*u(k-2)
// ---------------------------------------------------------------------------
struct PIDDisc {
  float b0, b1, b2;   // coeficientes do numerador
  float a1, a2;       // coeficientes do denominador (sem o termo z²)
  float e1, e2;       // erros anteriores
  float u1, u2;       // saídas anteriores
};

// ---------------------------------------------------------------------------
// PID de Temperatura  —  Ts = 2 s
//
// C_T(z) = K_T * (z - a_T)(z - b_T) / [(z - 1)(z - delta_T)]
//        = 20  * (z - 0.997)(z - 0.3) / [(z - 1)(z + 0.5)]
//
// Numerador expandido:
//   20 * [z² - 1.297z + 0.2991]
//   = [20,  -25.940,  5.982]
//   => b0 = 20.000 | b1 = -25.940 | b2 = 5.982
//
// Denominador expandido (mônico):
//   (z - 1)(z + 0.5) = z² - 0.5z - 0.5
//   => a1 = -0.5 | a2 = -0.5
//
// Ajuste fino do ganho: altere K_T e recalcule b0..b2 proporcionalmente.
//   K_T = 20 → padrão do projeto MATLAB
// ---------------------------------------------------------------------------
static const float K_T = 40.0f;
PIDDisc pidTemp = {
   20.000f * (K_T / 20.0f),   // b0
  -25.940f * (K_T / 20.0f),   // b1
    5.982f * (K_T / 20.0f),   // b2
   -0.5f,                     // a1
   -0.5f,                     // a2
   0.0f, 0.0f, 0.0f, 0.0f    // estados iniciais
};

// ---------------------------------------------------------------------------
// PID de Vazão  —  Ts = 1 s
//
// C_F(z) = K_F * (z - a_F)(z - b_F) / [(z - 1)(z - delta_F)]
//
// a_F  = polo de G_f_disc (extraído automaticamente no MATLAB via zpk).
//        Valor típico medido no ensaio: ~0.9754  (ajuste se o seu difere)
// b_F  = 0.3   (zero livre, igual ao projeto de temperatura)
// delta_F = -0.5
// K_F  = 1     (ponto de partida; ajuste via sisotool e atualize aqui)
//
// Numerador expandido com a_F = 0.9754, b_F = 0.3, K_F = 1:
//   1 * [z² - 1.2754z + 0.29262]
//   => b0 = 1.00000 | b1 = -1.27540 | b2 = 0.29262
//
// Denominador: mesmo que C_T => a1 = -0.5 | a2 = -0.5
//
// *** Se o seu polo a_F for diferente, recalcule:
//       b0 =  K_F
//       b1 = -K_F * (a_F + b_F)
//       b2 =  K_F * a_F * b_F          ***
// ---------------------------------------------------------------------------
static const float a_F  = 0.9754f;   // ← atualize com o polo real de G_f_disc
static const float b_F  = 0.3f;
static const float K_F  = 1.0f;      // ← ajuste após sisotool

PIDDisc pidFluxo = {
   K_F,                          // b0 =  K_F
  -K_F * (a_F + b_F),           // b1 = -K_F*(a_F + b_F)
   K_F * a_F * b_F,             // b2 =  K_F*a_F*b_F
  -0.5f,                        // a1
  -0.5f,                        // a2
  0.0f, 0.0f, 0.0f, 0.0f       // estados iniciais
};

// ---------------------------------------------------------------------------
volatile int pulsos = 0;
unsigned long tempoAntTemp  = 0;
unsigned long tempoAntFluxo = 0;

float temperaturaC = 25.0f;
float vazaoLmin    = 0.0f;
float spVazao      = SP_VAZAO_COOLER_OFF;

int dcResistencia = 0;
int dcCooler      = 0;
int estabContagem = 0;

// Acumulador de pulsos para Ts = 1 s
int pulsosAcum = 0;

void IRAM_ATTR lerFluxo() { pulsos++; }

// ---------------------------------------------------------------------------
static float clampf(float x, float mn, float mx) {
  if (x < mn) return mn;
  if (x > mx) return mx;
  return x;
}

static float atualizarPID(PIDDisc& c, float erro) {
  float u = c.b0 * erro
          + c.b1 * c.e1
          + c.b2 * c.e2
          - c.a1 * c.u1
          - c.a2 * c.u2;

  u = clampf(u, 0.0f, 100.0f);

  c.e2 = c.e1;  c.e1 = erro;
  c.u2 = c.u1;  c.u1 = u;
  return u;
}

static float lerTemperaturaC() {
  long soma = 0;
  for (int i = 0; i < TEMP_ADC_SAMPLES; i++) soma += analogRead(SENSOR_TEMP);
  float leitura = (float)soma / TEMP_ADC_SAMPLES;
  double vout = (leitura * VS) / ADC_RES;
  if (vout <= 0.0)       vout = 0.001;
  if ((VS - vout) < 0.001) vout = VS - 0.001;
  double rt = R1 * vout / (VS - vout);
  float tempCraw = (float)(1.0 / (1.0 / T0_K + log(rt / R0) / BETA) - 273.15);
  return tempCraw + TEMP_OFFSET_C;
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  pinMode(SENSOR_TEMP,  INPUT);
  pinMode(SENSOR_FLUXO, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(SENSOR_TEMP, ADC_11db);

  ledcAttach(PWM_TEMP,   1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);
  ledcWrite(PWM_TEMP,   0);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  unsigned long agora = millis();
  tempoAntTemp  = agora;
  tempoAntFluxo = agora;

  // Imprime coeficientes em uso (útil para conferência)
  Serial.println(">>> Controle PID discreto iniciado (coeficientes MATLAB).");
  Serial.printf(">>> C_T: b=[%.4f, %.4f, %.4f]  a=[%.4f, %.4f]  Ts=2s\n",
                pidTemp.b0, pidTemp.b1, pidTemp.b2, pidTemp.a1, pidTemp.a2);
  Serial.printf(">>> C_F: b=[%.5f, %.5f, %.5f]  a=[%.4f, %.4f]  Ts=1s\n",
                pidFluxo.b0, pidFluxo.b1, pidFluxo.b2, pidFluxo.a1, pidFluxo.a2);
  Serial.println(">>> Fase AQUECENDO: SP_Temp=40C, cooler OFF.");
}

// ---------------------------------------------------------------------------
void loop() {
  unsigned long agora = millis();

  // ------------------------------------------------------------------
  // Leitura de pulsos do sensor de fluxo (acumulador contínuo)
  // ------------------------------------------------------------------
  noInterrupts();
  int p = pulsos;
  pulsos = 0;
  interrupts();
  pulsosAcum += p;

  // ------------------------------------------------------------------
  // Malha de vazão  —  Ts = 1.0 s
  // ------------------------------------------------------------------
  if (agora - tempoAntFluxo >= TS_FLUXO_MS) {
    float dt = (agora - tempoAntFluxo) / 1000.0f;
    tempoAntFluxo = agora;

    // Converte pulsos acumulados em L/min  (YF-S201: 7,5 pulsos/s por L/min)
    vazaoLmin  = (pulsosAcum / dt) / 7.5f;
    pulsosAcum = 0;

    if (faseAtual == AQUECENDO) {
      dcCooler = 0;
      // Zera estados do PID de vazão para bumpless transfer
      pidFluxo.e1 = pidFluxo.e2 = 0.0f;
      pidFluxo.u1 = pidFluxo.u2 = 0.0f;
    } else {
      float erroF   = (spVazao - vazaoLmin) * GANHO_PID_FLUXO;
      float uFluxo  = atualizarPID(pidFluxo, erroF);
      int dcAlvo    = (int)roundf(uFluxo);
      int deltaPwm  = dcAlvo - dcCooler;
      deltaPwm      = (int)clampf((float)deltaPwm, -MAX_STEP_PWM_COOLER, MAX_STEP_PWM_COOLER);
      dcCooler      = (int)clampf((float)(dcCooler + deltaPwm), 0.0f, 100.0f);
    }
    ledcWrite(PWM_COOLER, map(dcCooler, 0, 100, 0, 255));
  }

  // ------------------------------------------------------------------
  // Malha de temperatura + log  —  Ts = 2.0 s
  // ------------------------------------------------------------------
  if (agora - tempoAntTemp >= TS_TEMP_MS) {
    tempoAntTemp = agora;
    temperaturaC = lerTemperaturaC();

    float erroT  = SP_TEMP - temperaturaC;
    float uTemp  = atualizarPID(pidTemp, erroT);
    dcResistencia = (int)roundf(uTemp);
    ledcWrite(PWM_TEMP, map(dcResistencia, 0, 100, 0, 255));

    // Lógica de fases
    bool tempOk  = fabsf(erroT)                <= BANDA_TEMP_C;
    bool tempProntaParaCooler = temperaturaC   >= TEMP_ENTRADA_COOLER_C;
    bool vazaoOk = fabsf(spVazao - vazaoLmin) <= BANDA_VAZAO_LMIN;

    switch (faseAtual) {
      case AQUECENDO:
        spVazao = SP_VAZAO_COOLER_OFF;
        // Ao chegar proximo de 40 C, inicia degrau de vazao para 5 L/min.
        if (tempProntaParaCooler) {
          faseAtual     = COOLER_ON;
          estabContagem = 0;
          spVazao       = SP_VAZAO_COOLER_ON;
          Serial.println(">>> Temperatura proxima de 40 C. Entrando em COOLER_ON (SP_Vazao=5 L/min).");
        } else {
          estabContagem = 0;
        }
        break;

      case COOLER_ON:
        spVazao       = SP_VAZAO_COOLER_ON;
        estabContagem = (tempOk && vazaoOk) ? estabContagem + 1 : 0;
        if (estabContagem >= ESTAB_ALVO) {
          faseAtual     = ESTABILIZADO;
          estabContagem = ESTAB_ALVO;
          Serial.println(">>> Sistema estabilizado com ambos PIDs ativos.");
        }
        break;

      case ESTABILIZADO:
        spVazao = SP_VAZAO_COOLER_ON;
        break;
    }

    Serial.printf(
      "Temp: %.2f C | SP_T: %.1f | Fase: %s | Estab: %d/%d | "
      "Vazao: %.2f L/min | SP_V: %.1f | DC_Cool: %d%% | DC_Res: %d%% | Resist: %s\n",
      temperaturaC, SP_TEMP, nomesFase[faseAtual], estabContagem, ESTAB_ALVO,
      vazaoLmin, spVazao, dcCooler, dcResistencia,
      (dcResistencia > 0 ? "ON" : "OFF")
    );
  }
}
