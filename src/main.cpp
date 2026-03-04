#include <Arduino.h>

// Pinos
#define PWM_TEMP 14
#define PWM_COOLER 25
#define SENSOR_TEMP 26
#define SENSOR_FLUXO 27

// Variáveis
const int resolution = 4095;
volatile int pulsos = 0;
unsigned long tempoAnt = 0, tempoAtual = 0, dT = 0;
float temperatura = 0, vazao = 0;
bool estadoResistencia = false;

// Constantes do NTC
double Vs = 3.3;
double R1 = 10000;
double Beta = 3950;
double To = 298.15;
double Ro = 10000;

// Setpoints
float spTemperatura = 40.0;  // Setpoint de temperatura (°C)
float spVazao = 1.0;         // Setpoint de vazão (L/min)

// --- PID Vazão (PIDF): Ts = 2s ---
// H(z) = (0.076z² - 0.08423z + 0.02334) / (z² - 1.6z + 0.6)
const float bF0 =  0.076,   bF1 = -0.08423, bF2 =  0.02334;
const float aF1 = -1.6,     aF2 =  0.6;
float eF[3] = {0, 0, 0};   // e[k], e[k-1], e[k-2]
float uF[3] = {0, 0, 0};   // u[k], u[k-1], u[k-2]

// --- PID Temperatura (PIDt): Ts = 2s ---
// H(z) = (8.5z² - 10.99z + 2.531) / (z² - 0.5z - 0.5)
const float bT0 =  8.5,     bT1 = -10.99,   bT2 =  2.531;
const float aT1 = -0.5,     aT2 = -0.5;
float eT[3] = {0, 0, 0};
float uT[3] = {0, 0, 0};

// Rotina da interrupção que realiza leitura do sensor de fluxo
void IRAM_ATTR lerFluxo()
{
  pulsos++;
}

float saturar(float valor, float minimo, float maximo)
{
  if (valor > maximo) return maximo;
  if (valor < minimo) return minimo;
  return valor;
}

void setup()
{
  Serial.begin(115200);

  pinMode(SENSOR_TEMP, INPUT);
  pinMode(SENSOR_FLUXO, INPUT);
  pinMode(PWM_TEMP, OUTPUT);
  pinMode(PWM_COOLER, OUTPUT);

  ledcAttach(PWM_TEMP, 1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP, 0);
  ledcWrite(PWM_COOLER, 0);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING);
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
    
    float frequencia = pulsos / 2.0;
    vazao = frequencia / 7.5;
    pulsos = 0;

    // ---- PID Vazão ----
    eF[0] = spVazao - vazao;
    uF[0] = bF0*eF[0] + bF1*eF[1] + bF2*eF[2] - aF1*uF[1] - aF2*uF[2];
    uF[0] = saturar(uF[0], 0, 100);

    eF[2] = eF[1];  eF[1] = eF[0];
    uF[2] = uF[1];  uF[1] = uF[0];

    int dutycycleCooler = (int)uF[0];
    ledcWrite(PWM_COOLER, (dutycycleCooler * 255) / 100);

    // ---- PID Temperatura ----
    eT[0] = spTemperatura - temperatura;
    uT[0] = bT0*eT[0] + bT1*eT[1] + bT2*eT[2] - aT1*uT[1] - aT2*uT[2];
    uT[0] = saturar(uT[0], 0, 100);

    eT[2] = eT[1];  eT[1] = eT[0];
    uT[2] = uT[1];  uT[1] = uT[0];

    int dutycycleTemp = (int)uT[0];
    ledcWrite(PWM_TEMP, (dutycycleTemp * 255) / 100);

    estadoResistencia = (dutycycleTemp > 0);

    Serial.printf("Temp: %.2f C | Vazao: %.2f L/min | DC_Cooler: %d%% | DC_Resist: %d%% | Resistencia: %s\n",
                  temperatura, vazao, dutycycleCooler, dutycycleTemp, estadoResistencia ? "ON" : "OFF");
  }
}
