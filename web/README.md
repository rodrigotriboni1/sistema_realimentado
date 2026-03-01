# Plataforma Ensaios Térmicos — Fase 1 + 2 + 3

Interface web para importar CSVs, visualizar gráficos, obter G_T(s)/G_F(s), **controle manual** (Fase 2) e **monitor em tempo real** (Fase 3).

## Como rodar

1. Crie um ambiente virtual (opcional):
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```

2. Instale as dependências:
   ```bash
   cd web
   pip install -r requirements.txt
   ```

3. Inicie o servidor. Na **raiz do projeto** (pasta `sistema_realimentado`):
   ```powershell
   cd web\backend
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   (Use `python -m uvicorn` se o comando `uvicorn` não for reconhecido.)

4. Abra no navegador: **http://localhost:8000**

## Uso

- **Monitor em tempo real (Fase 3)**: a página conecta-se ao backend por WebSocket. Para ver dados ao vivo, rode a **ponte** `serial_to_api.py` na raiz do projeto (com o ESP32 ligado na serial). Nenhuma alteração no firmware do ESP32 — ele continua só enviando pela Serial.
- **Controle (Fase 2)**: use os sliders ou botões para definir resistência e cooler (0–100%). O ESP32, na mesma rede, consulta a API a cada 3 s e aplica os valores.
- **Enviar e salvar**: escolha um arquivo CSV (colunas: `timestamp`, `temperatura_C`, `vazao_L_min`, `cooler_%`, `resistencia`) e clique em "Enviar e salvar".
- **Testes salvos**: lista de testes; use "Atualizar lista" para recarregar.
- **Análise**: selecione um teste e o tipo (Temperatura ou Fluxo), depois "Analisar". O gráfico e a função de transferência FOPDT aparecem abaixo.

## Monitor em tempo real (Fase 3)

O ESP32 permanece **apenas com Serial** (sem WiFi/HTTP para esta fase). Os dados chegam à web através de uma **ponte** no PC:

1. Inicie o backend (passos acima).
2. Na **raiz do projeto** (sistema_realimentado), instale dependências se necessário: `pip install pyserial requests`.
3. Configure porta e URL por variáveis de ambiente ou argumentos:
   - `COM_PORT` (ou `-p`): porta serial, ex. `COM6`.
   - `BACKEND_URL` (ou `-u`): URL do backend, ex. `http://127.0.0.1:8000`.
   - Exemplo: `python serial_to_api.py -p COM6 -u http://127.0.0.1:8000`
4. Com o ESP32 conectado na serial e enviando dados no formato esperado (`Temp: ... | Vazao: ... | Cooler: ... | Resistencia: ...`), execute:  
   `python serial_to_api.py`
5. Abra a plataforma no navegador; a seção "Monitor em tempo real" conecta-se ao WebSocket e exibe os valores e o gráfico ao vivo.

## Controle remoto (ESP32)

Para o ESP32 controlar resistência e cooler pela plataforma:

1. **Rede**: o backend deve ser acessível pelo ESP32 e pelo navegador. Inicie o servidor com `--host 0.0.0.0` (já indicado acima) para aceitar conexões na LAN.

2. **IP do servidor**: no PC onde o backend roda, descubra o IP local (ex.: `ipconfig` no Windows; o ESP32 e o navegador devem usar esse IP). Exemplo: `192.168.1.10`.

3. **Configuração no ESP32**: em `src/main.cpp` ajuste:
   - `ssid` e `password`: sua rede WiFi;
   - `serverUrl`: o endereço do backend, ex. `http://192.168.1.10:8000` (sem barra no final).

4. **Mesma rede**: o ESP32 e o PC do backend precisam estar na mesma rede (ou o ESP32 precisa conseguir acessar o IP/porta do backend, por exemplo via túnel se estiver em outra rede).

## Configuração do backend (variáveis de ambiente)

- **CORS_ORIGINS**: origens permitidas para CORS, separadas por vírgula. Padrão: `*`. Em produção, use ex.: `CORS_ORIGINS=http://localhost:8000,https://seu-dominio.com`.
- **MAX_UPLOAD_BYTES**: tamanho máximo de upload de CSV em bytes. Padrão: 10485760 (10 MB).

## Troubleshooting

### "Acesso negado" ou "PermissionError" ao abrir a porta serial (COM)

- Feche o Monitor Serial do Arduino IDE (ou qualquer outro programa que use a mesma porta).
- Desconecte e reconecte o cabo USB do ESP32.
- Confirme a porta em "Gerenciador de Dispositivos" (Windows) ou `ls /dev/tty*` (Linux).
- No Windows, execute o terminal ou o script como **Administrador** se a porta exigir permissões elevadas.

### Servidor indisponível no navegador

- Verifique se o backend está rodando (`python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000` na pasta `web/backend`).
- Se estiver em outra máquina, use o IP correto (ex.: `http://192.168.1.10:8000`).

### ESP32 não conecta ao WiFi

- O firmware usa timeout de 15 s; após isso o ESP32 segue operando com PWMs em 0% até a próxima resposta válida da API. Verifique SSID, senha e se o backend está acessível no IP configurado em `serverUrl`.
