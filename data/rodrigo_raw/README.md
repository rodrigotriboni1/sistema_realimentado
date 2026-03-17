# CSVs organizados dos ensaios

## Ordem sugerida de uso

1. `01_ensaio_temperatura_resistencia_degrau.csv`
   - Aquece o sistema com resistência ligada e cooler desligado.
   - Base para análise térmica do aquecimento.

2. `02_ensaio_fluxo_cooler_100_resistencia_off.csv`
   - Mede a resposta de fluxo com cooler a 100% e resistência desligada.
   - Base para análise de vazão.

3. `03_ensaio_resistencia_100_para_cooler_100.csv`
   - Ensaio transitório: primeiro aquece, depois resfria/força fluxo com cooler máximo.

4. `04_ensaio_ft_final_pid_zoh_40C_1Lmin.csv`
   - Ensaio final de malha fechada com PID discreto.
   - Gráfico associado: `grafico_dados_ensaio_ft_final.png`

5. `05_ensaio_variacao_setpoint_40C_com_sp_vazao_5Lmin.csv`
   - Ensaio com alteração de setpoints.

6. `06_ensaio_perfil_setpoints_40_50_35.csv`
   - Perfil em três etapas de temperatura.
   - Gráfico associado: `grafico_ensaio_ft.png`

## Arquivos que parecem versões antigas, intermediárias ou redundantes

- `dados_ensaio_ft_2.csv`
- `dados_ensaio_ftbom.csv`
- `dados_temperatura_ambiente.csv`
- `dados_ensaio_degrau_cooler.csv`

Esses arquivos não parecem ser a base principal dos gráficos enviados nesta conversa.
Eles foram deixados fora da pasta organizada para evitar confusão, mas continuam disponíveis no diretório original.
