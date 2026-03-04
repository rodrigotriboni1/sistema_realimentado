#include <Arduino.h>

// Pinos
#define PWM_TEMP 14
#define PWM_COOLER 25
#define SENSOR_TEMP 26
#define SENSOR_FLUXO 27

// Variáveis
const int resolution = 4095;                         // Resolução do conversor AD do ESP
volatile int pulsos = 0;                             // Pulsos do sensor de fluxo
unsigned long tempoAtual = 0;                        // Tempo atual (millis)
unsigned long tempoAntFluxo = 0;                     // Timer do sensor de fluxo (200 ms)
unsigned long tempoAntTemp  = 0;                     // Timer do sensor de temperatura (2000 ms)
float temperatura = 0, vazao = 0;                    // Leituras dos sensores
float vazaoAcum  = 0;                                // Acumulador de vazão entre leituras de temperatura
int   nVazao     = 0;                                // Contagem de amostras de vazão acumuladas
int dutycycleTemp = 0, dutycycleCooler = 0;          // Duty Cycle do PWM do transistor e do cooler
bool estadoResistencia = false;

// Detecção de estabilização da temperatura
#define JANELA_ESTAB  30        // Amostras na janela: 30 × 2s = 60s
#define LIMIAR_ESTAB  0.5f      // Variação máxima permitida (°C)
float bufferTemp[JANELA_ESTAB] = {0};
int   idxBuf      = 0;
bool  bufferCheio = false;
bool  coolerLigado = false;

// Constantes do NTC e sistema
double Vs = 3.3;    // Tensão de referência do ESP32
double R1 = 10000;  // Resistor fixo de 10kΩ no divisor de tensão
double Beta = 3950; // Coeficiente beta do NTC
double To = 298.15; // Temperatura de referência (25°C em Kelvin)
double Ro = 10000;  // Resistência nominal do NTC a 25°C

// Rotina da interrupção que realiza leitura do sensor de fluxo
void IRAM_ATTR lerFluxo()
{
  pulsos++;
}

// Retorna true se a variação de temperatura na janela for <= LIMIAR_ESTAB
bool estaEstabilizado()
{
  if (!bufferCheio) return false;
  float tMin = bufferTemp[0], tMax = bufferTemp[0];
  for (int i = 1; i < JANELA_ESTAB; i++)
  {
    if (bufferTemp[i] < tMin) tMin = bufferTemp[i];
    if (bufferTemp[i] > tMax) tMax = bufferTemp[i];
  }
  return (tMax - tMin) <= LIMIAR_ESTAB;
}

void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_TEMP, INPUT);
  pinMode(SENSOR_FLUXO, INPUT);
  pinMode(PWM_TEMP, OUTPUT);
  pinMode(PWM_COOLER, OUTPUT);

  dutycycleTemp = 0;
  dutycycleCooler = 0;

  ledcAttach(PWM_TEMP, 1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP, 0);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  // Aguarda 2 segundos antes de ligar a resistência
  delay(2000);

  // Liga resistência no máximo; cooler permanece desligado até estabilizar
  dutycycleTemp = 100;
  ledcWrite(PWM_TEMP, (dutycycleTemp * 255) / 100);

  // Cabeçalho CSV para o serial_logger.py
  Serial.println("time_ms,temp_C,vazao_L_min,cooler_pct,res_pct");
}

void loop()
{
  tempoAtual = millis();

  // --- Sensor de fluxo: amostrado a cada 200 ms ---
  if (tempoAtual - tempoAntFluxo >= 200)
  {
    tempoAntFluxo = tempoAtual;

    // Frequência instantânea a partir dos pulsos em 0,2 s
    float frequencia = pulsos / 0.2f;
    float vazaoInst  = frequencia / 7.5f; // L/min (ajuste conforme datasheet)
    pulsos = 0;

    // Acumula para calcular a média no instante da temperatura
    vazaoAcum += vazaoInst;
    nVazao++;
  }

  // --- Sensor de temperatura: amostrado a cada 2000 ms ---
  if (tempoAtual - tempoAntTemp >= 2000)
  {
    tempoAntTemp = tempoAtual;

    // Leitura do NTC e cálculo da temperatura
    int leituraADC = analogRead(SENSOR_TEMP);
    double Vout = (leituraADC * Vs) / resolution;

    if (Vs - Vout < 0.01) Vout = Vs - 0.01;

    double Rt = R1 * Vout / (Vs - Vout);
    temperatura = 1.0 / (1.0 / To + log(Rt / Ro) / Beta);
    temperatura = temperatura - 273.15;

    // Vazão média das amostras acumuladas desde a última leitura de temperatura
    vazao = (nVazao > 0) ? (vazaoAcum / nVazao) : 0.0f;
    vazaoAcum = 0;
    nVazao    = 0;

    estadoResistencia = (dutycycleTemp > 0);

    // Atualiza buffer de estabilização (janela de amostras de temperatura)
    bufferTemp[idxBuf] = temperatura;
    idxBuf = (idxBuf + 1) % JANELA_ESTAB;
    if (idxBuf == 0) bufferCheio = true;

    // Liga cooler no máximo assim que a temperatura estabilizar
    if (!coolerLigado && estaEstabilizado())
    {
      coolerLigado    = true;
      dutycycleCooler = 100;
      ledcWrite(PWM_COOLER, (dutycycleCooler * 255) / 100);
      Serial.println("# ESTABILIZADO - cooler ligado");
    }

    // Exibição Serial em formato CSV (cadência de 2 s)
    Serial.printf("%lu,%.2f,%.2f,%d,%d\n",
                  tempoAtual, temperatura, vazao, dutycycleCooler, dutycycleTemp);
  }
}
