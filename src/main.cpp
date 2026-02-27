#include <Arduino.h>

// Pinos
#define PWM_TEMP 14
#define PWM_COOLER 25
#define SENSOR_TEMP 26
#define SENSOR_FLUXO 27

// Variáveis
const int resolution = 4095;                        // Resolução do conversor AD do ESP
volatile int pulsos = 0;                            // Pulsos do sensor de fluxo
unsigned long tempoAnt = 0, tempoAtual = 0, dT = 0; // Variáveis para manipulação do timer
float temperatura = 0, resistencia = 0, vazao = 0;  // Variáveis para cálculo da temperatura e vazão
int dutycycleTemp = 0, dutycycleCooler = 0;         // Duty Cycle do PWM do transistor e do cooler
bool estadoResistencia = false;

// Ensaio: 0=aguardando estabilização, 1=cooler ligado, coletando até novo regime
int faseEnsaio = 0;  // 0=FASE_ESTABILIZACAO, 1=FASE_COOLER_LIGADO
const int N_AMOSTRAS_ESTAB = 30;                    // Amostras para verificar estabilização
float historicoTemp[N_AMOSTRAS_ESTAB];
int idxHistorico = 0;
bool historicoPreenchido = false;

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

void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_TEMP, INPUT);
  pinMode(SENSOR_FLUXO, INPUT);
  pinMode(PWM_TEMP, OUTPUT);
  pinMode(PWM_COOLER, OUTPUT);

  dutycycleTemp = 100;   // Resistência PWM máximo
  dutycycleCooler = 0;   // Cooler desligado

  ledcAttach(PWM_TEMP, 1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP, 255);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);

  Serial.println("Ensaio iniciado: Resistencia 100% | Cooler 0% | Aguardando estabilizacao...");
}

void loop()
{
  tempoAtual = millis();
  dT = tempoAtual - tempoAnt;

  // Tempo de Amostragem 2000ms = 2s
  if (dT >= 2000)
  {
    tempoAnt = tempoAtual;

    // Leitura do NTC e cálculo da temperatura
    int leituraADC = analogRead(SENSOR_TEMP);
    double Vout = (leituraADC * Vs) / resolution;
    
    // Evita divisão por zero se Vout for muito próximo de Vs
    if(Vs - Vout < 0.01) Vout = Vs - 0.01;
    
    double Rt = R1 * Vout / (Vs - Vout);
    temperatura = 1 / (1 / To + log(Rt / Ro) / Beta);
    temperatura = temperatura - 273.15;

    // Cálculo da vazão (Simplificado: 1 pulso = X ml -> Ajustar conforme sensor)
    // Exemplo genérico: Frequência (Hz) = 7.5 * Q (L/min) -> Q = F / 7.5
    // Pulsos em 2 segundos -> Freq = pulsos / 2
    float frequencia = pulsos / 2.0; 
    vazao = frequencia / 7.5; // L/min (Ajuste conforme datasheet do sensor)
    
    pulsos = 0;

    // Estado da Resistência (Baseado no DutyCycle > 0)
    estadoResistencia = (dutycycleTemp > 0);

    // Lógica do ensaio: verificar estabilização e ligar cooler
    if (faseEnsaio == 0) {
      historicoTemp[idxHistorico] = temperatura;
      idxHistorico++;
      if (idxHistorico >= N_AMOSTRAS_ESTAB) {
        historicoPreenchido = true;
        idxHistorico = 0;
      }
      if (historicoPreenchido) {
        float tempMin = historicoTemp[0], tempMax = historicoTemp[0];
        for (int i = 1; i < N_AMOSTRAS_ESTAB; i++) {
          if (historicoTemp[i] < tempMin) tempMin = historicoTemp[i];
          if (historicoTemp[i] > tempMax) tempMax = historicoTemp[i];
        }
        if ((tempMax - tempMin) < 0.3f) {
          faseEnsaio = 1;
          dutycycleCooler = 100;
          ledcWrite(PWM_COOLER, 255);
          Serial.println("Temperatura estabilizada! Cooler ligado 100% - coleta ate novo regime");
        }
      }
    }

    // Exibição Serial
    Serial.printf("Temp: %.2f C | Vazao: %.2f L/min | Cooler: %d%% | Resistencia: %s\n", 
                  temperatura, vazao, dutycycleCooler, estadoResistencia ? "ON" : "OFF");
  }
}
