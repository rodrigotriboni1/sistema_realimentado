#include <Arduino.h>

// --- Pinos ---
const int PIN_NTC = 26;
const int PIN_COOLER = 25;

// --- Configuração do PWM (Cooler) ---
// O ESP32 usa canais LEDC para gerar PWM
const int PWM_CHANNEL = 0;  // Canal 0 (0 a 15)
const int PWM_FREQ = 25000; // Frequência (25kHz é bom para ventoinhas para evitar zumbido)
const int PWM_RES = 8;      // Resolução de 8 bits (Valores de 0 a 255)

// --- Parâmetros do NTC (Mesmos de antes) ---
const float BETA = 3950.0;
const float R_SERIE = 10000.0;
const float R_NTC_25 = 10000.0;
const float T0_KELVIN = 298.15;

void setup()
{
  Serial.begin(115200);
  analogReadResolution(12);

  // --- Configuração do PWM para o Cooler ---
  // Nota: Se estiver usando a versão mais recente do ESP32 Core (v3.0+),
  // a função mudou para ledcAttach(PIN_COOLER, PWM_FREQ, PWM_RES);
  // Mas no PlatformIO padrão geralmente usa-se a sintaxe abaixo:

  ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_COOLER, PWM_CHANNEL);

  Serial.println("Sistema de Controle de Temperatura Iniciado");
}

void loop()
{
  // --- 1. Leitura da Temperatura (Código anterior) ---
  float leituraADC = 0;
  for (int i = 0; i < 10; i++)
  {
    leituraADC += analogRead(PIN_NTC);
    delay(5);
  }
  leituraADC /= 10.0;

  float resistenciaAtual = R_SERIE / ((4095.0 / leituraADC) - 1.0);
  float temperaturaK = 1.0 / ((1.0 / T0_KELVIN) + (log(resistenciaAtual / R_NTC_25) / BETA));
  float temperaturaC = temperaturaK - 273.15;

  // --- 2. Lógica de Controle do Cooler ---
  int velocidadeCooler = 255; // 0 a 255

  // Exemplo de lógica:
  // < 30°C -> Desligado (0)
  // > 30°C -> Começa a girar devagar
  // > 40°C -> Velocidade Máxima (255)

  // Envia o sinal para o pino D25
  ledcWrite(PWM_CHANNEL, velocidadeCooler);

  // --- 3. Debug ---
  Serial.print("Temp: ");
  Serial.print(temperaturaC, 1); // 1 casa decimal
  Serial.print(" °C | Cooler PWM: ");
  Serial.println(velocidadeCooler);

  delay(500);
}