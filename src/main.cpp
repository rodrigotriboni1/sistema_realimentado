#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Pinos
#define PWM_TEMP 14
#define PWM_COOLER 25
#define SENSOR_TEMP 26
#define SENSOR_FLUXO 27

// Configurações de Rede e Servidor
const char* ssid = "SEU_WIFI_SSID";
const char* password = "SEU_WIFI_PASSWORD";
const char* serverName = "http://seusite.com/insert_data.php"; // Substitua pela URL da HostGator

// Variáveis
const int resolution = 4095;                        // Resolução do conversor AD do ESP
volatile int pulsos = 0;                            // Pulsos do sensor de fluxo
unsigned long tempoAnt = 0, tempoAtual = 0, dT = 0; // Variáveis para manipulação do timer
float temperatura = 0, resistencia = 0, vazao = 0;  // Variáveis para cálculo da temperatura e vazão
int dutycycleTemp = 0, dutycycleCooler = 0;         // Duty Cycle do PWM do transistor e do cooler
bool estadoResistencia = false;

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

  // Conexão WiFi
  WiFi.begin(ssid, password);
  Serial.println("Conectando ao WiFi");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Conectado ao IP: ");
  Serial.println(WiFi.localIP());

  dutycycleTemp = 50; // Duty Cycle setado (Exemplo)
  dutycycleCooler = 0; // Exemplo

  ledcAttach(PWM_TEMP, 1000, 8);
  ledcAttach(PWM_COOLER, 1000, 8);

  ledcWrite(PWM_TEMP, (dutycycleTemp * 255) / 100); 
  ledcWrite(PWM_COOLER, (dutycycleCooler * 255) / 100);

  attachInterrupt(digitalPinToInterrupt(SENSOR_FLUXO), lerFluxo, RISING); // Interrupção para sensor de fluxo
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

    // Exibição Serial
    Serial.printf("Temp: %.2f C | Vazao: %.2f L/min | Cooler: %d%% | Resistencia: %s\n", 
                  temperatura, vazao, dutycycleCooler, estadoResistencia ? "ON" : "OFF");

    // Envio HTTP POST
    if(WiFi.status() == WL_CONNECTED){
      HTTPClient http;
      http.begin(serverName);
      http.addHeader("Content-Type", "application/json");

      // Criar JSON manualmente
      String json = "{";
      json += "\"temperatura\":" + String(temperatura) + ",";
      json += "\"fluxo\":" + String(vazao) + ",";
      json += "\"pwm_cooler\":" + String(dutycycleCooler) + ",";
      json += "\"estado_resistencia\":" + String(estadoResistencia); // 1 ou 0
      json += "}";

      int httpResponseCode = http.POST(json);

      if(httpResponseCode > 0){
        String response = http.getString();
        Serial.println(httpResponseCode);
        Serial.println(response);
      } else {
        Serial.print("Erro no envio POST: ");
        Serial.println(httpResponseCode);
      }
      http.end();
    } else {
      Serial.println("WiFi Desconectado");
    }
  }
}
