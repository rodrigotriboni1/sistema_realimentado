#include <Arduino.h>

// ============================================================
//  Pinos
// ============================================================
#define PWM_TEMP     14
#define PWM_COOLER   25
#define SENSOR_TEMP  26
#define SENSOR_FLUXO 27

// ============================================================
//  Parâmetros do ensaio de identificação  G_F(s)
//  Vazão [L/min]  ←  PWM Cooler [0-100 %]
// ============================================================
#define TS_MS           200   // Período de amostragem da vazão  (ms)
                              // A planta de vazão é ~10× mais rápida que a de temperatura
                              // → 200 ms dá boa resolução do transitório sem overload serial

#define JANELA_SS       30    // Nº de amostras consecutivas para declarar regime permanente
#define TOL_SS_REL      0.03f // Tolerância relativa da janela (3 % da média)
#define TOL_SS_ABS      0.02f // Tolerância absoluta mínima (L/min) — evita FP ruído em fluxos baixos

#define TEMPO_INICIAL_MS 3000 // Tempo (ms) de observação com cooler desligado antes do degrau
                              // Confirma a condição inicial (vazão = 0)

// ============================================================
//  Constantes do sensor de fluxo
//  Modelo genérico YF-S201: F(Hz) = 7,5 × Q(L/min)
//  → Q = F / 7,5   (ajuste conforme datasheet do seu sensor)
// ============================================================
#define K_SENSOR 7.5f

// ============================================================
//  Constantes do NTC (mantidas para referência futura)
// ============================================================
const double Vs   = 3.3;
const double R1   = 10000.0;
const double Beta = 3950.0;
const double To   = 298.15;
const double Ro   = 10000.0;
const int    ADC_RES = 4095;

// ============================================================
//  Variáveis globais
// ============================================================
volatile int pulsos = 0;           // Incrementado pela ISR

// Máquina de estados do ensaio
enum EstadoEnsaio { INICIAL, DEGRAU, CONCLUIDO };
EstadoEnsaio estadoEnsaio = INICIAL;

unsigned long tempoInicio = 0;     // Instante t=0 do ensaio (ms absoluto)
unsigned long tempoAnt    = 0;     // Marca do último período de amostragem

// Janela deslizante para detecção de regime permanente
float janela[JANELA_SS];
int   idxJanela   = 0;
bool  janelaCheia = false;

float vazaoRegimePermanente = 0.0f; // Registrado ao declarar RP

// ============================================================
//  ISR – sensor de fluxo (RISING)
// ============================================================
void IRAM_ATTR lerFluxo()
{
  pulsos++;
}

// ============================================================
//  Verifica regime permanente via janela deslizante
//  Retorna true quando todas as amostras da janela ficam dentro
//  da banda  [ média ± max(TOL_SS_REL*média , TOL_SS_ABS) ]
// ============================================================
bool regimePermanente(float novaAmostra)
{
  janela[idxJanela % JANELA_SS] = novaAmostra;
  idxJanela++;
  if (idxJanela >= JANELA_SS) janelaCheia = true;
  if (!janelaCheia) return false;

  float soma = 0.0f;
  for (int i = 0; i < JANELA_SS; i++) soma += janela[i];
  float media = soma / JANELA_SS;

  float tolerancia = max(TOL_SS_REL * media, TOL_SS_ABS);

  for (int i = 0; i < JANELA_SS; i++) {
    if (fabsf(janela[i] - media) > tolerancia) return false;
  }
  return true;
}

// ============================================================
//  Setup
// ============================================================
void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_TEMP,  INPUT);
  pinMode(SENSOR_FLUXO, INPUT_PULLUP);
  pinMode(PWM_TEMP,     OUTPUT);
  pinMode(PWM_COOLER,   OUTPUT);

  ledcAttach(PWM_TEMP,   1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  // Condição inicial: cooler desligado, resistência desligada
  ledcWrite(PWM_TEMP,   0);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  tempoInicio = millis();
  tempoAnt    = millis();

  // Cabeçalho CSV — cole diretamente no Python/Excel/MATLAB para identificar G_F(s)
  Serial.println("# ============================================================");
  Serial.println("# Ensaio de identificacao  G_F(s) : Vazao x PWM Cooler");
  Serial.printf ("# Periodo de amostragem : %d ms\n", TS_MS);
  Serial.printf ("# Degrau aplicado       : 100%% PWM (cooler)\n");
  Serial.printf ("# Tolerancia RP relativa: %.0f%%   |  absoluta: %.3f L/min\n",
                 TOL_SS_REL * 100.0f, TOL_SS_ABS);
  Serial.println("# ============================================================");
  Serial.println("t_ms,vazao_Lmin,fase");
}

// ============================================================
//  Loop
// ============================================================
void loop()
{
  unsigned long agora = millis();

  if ((agora - tempoAnt) < TS_MS) return; // Aguarda próximo período

  // --- Captura atômica dos pulsos acumulados no intervalo ---
  noInterrupts();
  int pulsosCapturados = pulsos;
  pulsos = 0;
  interrupts();

  // dt real (pode diferir ligeiramente de TS_MS por jitter)
  float dt_s = (agora - tempoAnt) / 1000.0f;
  tempoAnt   = agora;

  // Frequência instantânea → vazão
  float freq  = pulsosCapturados / dt_s;     // Hz
  float vazao = freq / K_SENSOR;              // L/min

  // Tempo relativo ao início do ensaio
  unsigned long t_ensaio = agora - tempoInicio;

  // --- Máquina de estados ---
  switch (estadoEnsaio)
  {
    // ----------------------------------------------------------
    case INICIAL:
      Serial.printf("%lu,%.4f,INICIAL\n", t_ensaio, vazao);

      if (t_ensaio >= TEMPO_INICIAL_MS) {
        // Aplica degrau: 100 % PWM no cooler
        ledcWrite(PWM_COOLER, 255);
        estadoEnsaio = DEGRAU;

        // Zera janela para não contaminar com amostras do período inicial
        idxJanela  = 0;
        janelaCheia = false;

        Serial.println("# --- DEGRAU APLICADO: Cooler 100% PWM ---");
      }
      break;

    // ----------------------------------------------------------
    case DEGRAU:
      Serial.printf("%lu,%.4f,DEGRAU\n", t_ensaio, vazao);

      if (regimePermanente(vazao)) {
        estadoEnsaio = CONCLUIDO;

        // Calcula vazão média no regime permanente
        float soma = 0.0f;
        for (int i = 0; i < JANELA_SS; i++) soma += janela[i];
        vazaoRegimePermanente = soma / JANELA_SS;

        Serial.println("# ============================================================");
        Serial.println("# REGIME PERMANENTE ATINGIDO");
        Serial.printf ("# Vazao_RP (setpoint maximo) = %.4f L/min\n", vazaoRegimePermanente);
        Serial.println("# Use os dados CSV acima para ajustar G_F(s) = K / (tau*s + 1)");
        Serial.println("# K   = Vazao_RP / 1  (ganho DC para entrada degrau unitario 100% PWM)");
        Serial.println("# tau = tempo para atingir 63,2% de Vazao_RP (leia no grafico)");
        Serial.println("# ============================================================");
      }
      break;

    // ----------------------------------------------------------
    case CONCLUIDO:
      // Continua amostrando para confirmação visual, sem alterar estado
      Serial.printf("%lu,%.4f,CONCLUIDO\n", t_ensaio, vazao);
      break;
  }
}
