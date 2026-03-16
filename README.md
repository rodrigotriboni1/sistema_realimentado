# Sistema de Controle Realimentado — ESP32

Sistema de controle em malha fechada com dois controladores PID discretos implementados em um ESP32, utilizando o método ZOH (Zero-Order Hold) para discretização das funções de transferência obtidas no MATLAB.

## Arquitetura do Sistema

| Malha | Variável controlada | Atuador | Sensor | Ts |
|---|---|---|---|---|
| Vazão | Vazão (L/min) | Cooler/Bomba (PWM) | Sensor de fluxo YF-S201 | 0.2 s |
| Temperatura | Temperatura (°C) | Resistência (PWM) | Termistor NTC 10kΩ | 2.0 s |

**Setpoints:** Temperatura = 40.0 °C | Vazão = 1.0 L/min

## Pinagem ESP32

| Pino | Função |
|---|---|
| GPIO 14 | PWM Resistência (temperatura) |
| GPIO 25 | PWM Cooler (vazão) |
| GPIO 26 | Leitura analógica NTC |
| GPIO 27 | Pulsos sensor de fluxo |

---

## 1. Leitura de Temperatura — NTC (Equação Beta de Steinhart-Hart)

### 1.1 Tensão de saída do divisor de tensão

$$V_{out} = \frac{ADC \cdot V_s}{4095}$$

Onde:
- $ADC$ = valor lido pelo conversor A/D (12 bits, 0–4095)
- $V_s = 3.3\,V$ (tensão de referência do ESP32)

### 1.2 Resistência do NTC

$$R_t = R_1 \cdot \frac{V_{out}}{V_s - V_{out}}$$

Onde:
- $R_1 = 10\,k\Omega$ (resistor fixo do divisor de tensão)

### 1.3 Temperatura (equação Beta)

$$T = \frac{1}{\dfrac{1}{T_0} + \dfrac{1}{\beta} \cdot \ln\!\left(\dfrac{R_t}{R_0}\right)}$$

Onde:
- $T_0 = 298.15\,K$ (25 °C, temperatura de referência)
- $R_0 = 10\,k\Omega$ (resistência nominal do NTC a 25 °C)
- $\beta = 3950$ (coeficiente Beta do NTC)
- $T$ = temperatura em Kelvin → converter para Celsius: $T_C = T - 273.15$

---

## 2. Leitura de Vazão — Sensor de Fluxo

### 2.1 Frequência dos pulsos

$$f = \frac{pulsos}{\Delta t}$$

Onde:
- $pulsos$ = contagem acumulada por interrupção (borda de subida)
- $\Delta t$ = intervalo de amostragem em segundos (0.2 s)

### 2.2 Vazão

$$Q = \frac{f}{7.5} \quad \text{(L/min)}$$

Constante 7.5 Hz/(L/min) do sensor YF-S201.

---

## 3. Controladores PID Discretos (Método ZOH)

### Forma geral da função de transferência discreta

$$H(z) = \frac{U(z)}{E(z)} = \frac{b_0 z^2 + b_1 z + b_2}{z^2 + a_1 z + a_2}$$

### Equação de diferenças correspondente

$$u[k] = b_0\,e[k] + b_1\,e[k\!-\!1] + b_2\,e[k\!-\!2] - a_1\,u[k\!-\!1] - a_2\,u[k\!-\!2]$$

Onde:
- $e[k] = SP - PV$ (erro = setpoint − variável de processo)
- $u[k]$ = saída do controlador (duty cycle em %)

A saída é limitada por saturação: $u[k] \in [0,\, 100]$

---

### 3.1 PID de Vazão (PIDF) — Ts = 0.2 s

**Função de transferência (MATLAB/ZOH):**

$$H_F(z) = \frac{0.05\,z^2 - 0.03277\,z + 0.002777}{z^2 - 0.7\,z - 0.3}$$

**Coeficientes:**

| | $b_0$ | $b_1$ | $b_2$ | $a_1$ | $a_2$ |
|---|---|---|---|---|---|
| Numerador | 0.05 | −0.03277 | 0.002777 | — | — |
| Denominador | — | — | — | −0.7 | −0.3 |

**Equação de diferenças:**

$$u_F[k] = 0.05\,e_F[k] - 0.03277\,e_F[k\!-\!1] + 0.002777\,e_F[k\!-\!2] + 0.7\,u_F[k\!-\!1] + 0.3\,u_F[k\!-\!2]$$

**Polos do denominador:**

$$z^2 - 0.7z - 0.3 = (z - 1)(z + 0.3)$$

- Polo em $z = 1$ → integrador puro (garante erro nulo em regime permanente)
- Polo em $z = -0.3$ → estável (dentro do círculo unitário)

---

### 3.2 PID de Temperatura (PIDt) — Ts = 2.0 s

**Função de transferência (MATLAB/ZOH):**

$$H_T(z) = \frac{8.5\,z^2 - 10.99\,z + 2.531}{z^2 - 0.5\,z - 0.5}$$

**Coeficientes:**

| | $b_0$ | $b_1$ | $b_2$ | $a_1$ | $a_2$ |
|---|---|---|---|---|---|
| Numerador | 8.5 | −10.99 | 2.531 | — | — |
| Denominador | — | — | — | −0.5 | −0.5 |

**Equação de diferenças:**

$$u_T[k] = 8.5\,e_T[k] - 10.99\,e_T[k\!-\!1] + 2.531\,e_T[k\!-\!2] + 0.5\,u_T[k\!-\!1] + 0.5\,u_T[k\!-\!2]$$

**Polos do denominador:**

$$z^2 - 0.5z - 0.5 = (z - 1)(z + 0.5)$$

- Polo em $z = 1$ → integrador puro
- Polo em $z = -0.5$ → estável

---

## 4. Conversão Duty Cycle → PWM

$$PWM = \frac{u[k] \cdot 255}{100}$$

Onde:
- $u[k] \in [0, 100]$ (duty cycle em %)
- $PWM \in [0, 255]$ (resolução de 8 bits do `ledcWrite`)

---

## Estrutura de Arquivos

| Arquivo | Descrição |
|---|---|
| `src/main.cpp` | Firmware ESP32 com os dois PIDs |
| `serial_logger.py` | Captura dados da serial e salva em `data/raw/` |
| `plot_ensaio.py` | Gera gráfico do ensaio e salva em `plots/` |
| `plot_ensaio_ft.py` | Gera gráfico do ensaio FT e salva em `plots/` |
| `plot_comparacao_ensaios_ft.py` | Compara ensaios FT e salva em `plots/` |
| `ft_temperatura_fluxo.py` | Identifica FTs, grava CSV em `data/processed/` e gráfico em `plots/` |

### Pastas de dados e saídas

- `data/raw/`: CSVs brutos de aquisição serial.
- `data/processed/`: CSVs processados (identificação/ajustes).
- `plots/`: gráficos gerados pelos scripts.
