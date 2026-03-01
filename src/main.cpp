#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Pinos
#define PWM_TEMP 14
#define PWM_COOLER 25
#define SENSOR_TEMP 26
#define SENSOR_FLUXO 27

// WiFi e API (ajuste para sua rede e IP do servidor)
const char* ssid = "SUA_REDE";
const char* password = "SUA_SENHA";
const char* serverUrl = "http://192.168.1.10:8000";  // IP do PC onde roda o backend

// Variáveis
const int resolution = 4095;
volatile int pulsos = 0;
unsigned long tempoAnt = 0, tempoAtual = 0, dT = 0;
float temperatura = 0, resistencia = 0, vazao = 0;
int dutycycleTemp = 0, dutycycleCooler = 0;
bool estadoResistencia = false;

// Polling da API a cada 3 s.
// Sem WiFi ou se GET falhar: mantemos os últimos PWMs aplicados (ou 0% até primeira resposta válida).
unsigned long lastControlPoll = 0;
const unsigned long CONTROL_POLL_MS = 3000;

// Timeout de conexão WiFi (ms); após isso segue sem travar (Serial e PWMs em 0 até API responder).
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 15000;

// Constantes do NTC
double Vs = 3.3;
double R1 = 10000;
double Beta = 3950;
double To = 298.15;
double Ro = 10000;

void IRAM_ATTR lerFluxo() {
  pulsos++;
}

// Parse simples de JSON: "resistencia":N ou "cooler":N
int parseJsonInt(const char* json, const char* key) {
  String s = String(json);
  String k = String(key);
  int idx = s.indexOf(k);
  if (idx < 0) return -1;
  idx = s.indexOf(':', idx);
  if (idx < 0) return -1;
  idx++;
  while (idx < (int)s.length() && (s[idx] == ' ' || s[idx] == '\t')) idx++;
  int val = 0;
  bool neg = false;
  if (idx < (int)s.length() && s[idx] == '-') { neg = true; idx++; }
  while (idx < (int)s.length() && s[idx] >= '0' && s[idx] <= '9') {
    val = val * 10 + (s[idx] - '0');
    idx++;
  }
  return neg ? -val : val;
}

void pollControl() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(serverUrl) + "/api/control";
  http.begin(url);
  int code = http.GET();

  if (code == HTTP_CODE_OK) {
    String payload = http.getString();
    int r = parseJsonInt(payload.c_str(), "resistencia");
    int c = parseJsonInt(payload.c_str(), "cooler");
    http.end();

    if (r >= 0 && r <= 100 && c >= 0 && c <= 100) {
      dutycycleTemp = r;
      dutycycleCooler = c;
      ledcWrite(PWM_TEMP, (dutycycleTemp * 255) / 100);
      ledcWrite(PWM_COOLER, (dutycycleCooler * 255) / 100);
    }
    // Se parse falhar, mantemos os últimos valores aplicados
  } else {
    http.end();
    // Falha na API: mantemos últimos PWMs (comportamento definido no plano)
  }
}

void setup() {
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

  WiFi.begin(ssid, password);
  Serial.print("Conectando ao WiFi");
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - wifiStart) < WIFI_CONNECT_TIMEOUT_MS) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi timeout. Operando offline; PWMs em 0 até conectar e receber /api/control.");
  }
  Serial.println("Controle via API: GET /api/control a cada 3s");
}

void loop() {
  tempoAtual = millis();
  dT = tempoAtual - tempoAnt;

  // Polling da API de controle a cada 3 s
  if (tempoAtual - lastControlPoll >= CONTROL_POLL_MS) {
    lastControlPoll = tempoAtual;
    pollControl();
  }

  // Amostragem 2 s: sensores e Serial
  if (dT >= 2000) {
    tempoAnt = tempoAtual;

    int leituraADC = analogRead(SENSOR_TEMP);
    double Vout = (leituraADC * Vs) / resolution;
    if (Vs - Vout < 0.01) Vout = Vs - 0.01;
    double Rt = R1 * Vout / (Vs - Vout);
    temperatura = 1 / (1 / To + log(Rt / Ro) / Beta);
    temperatura = temperatura - 273.15;

    float frequencia = pulsos / 2.0f;
    vazao = frequencia / 7.5f;
    pulsos = 0;

    estadoResistencia = (dutycycleTemp > 0);

    Serial.printf("Temp: %.2f C | Vazao: %.2f L/min | Cooler: %d%% | Resistencia: %s\n",
                  temperatura, vazao, dutycycleCooler, estadoResistencia ? "ON" : "OFF");
  }
}
