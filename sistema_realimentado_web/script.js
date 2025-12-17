// Configuração Global dos Gráficos
const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        x: {
            ticks: { maxTicksLimit: 10 }
        }
    },
    animation: { duration: 0 } // Desativar animação para updates em tempo real mais fluidos
};

// Inicialização dos Gráficos
const ctxTemp = document.getElementById('chartTemp').getContext('2d');
const chartTemp = new Chart(ctxTemp, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Temperatura (°C)',
            borderColor: '#e74c3c',
            backgroundColor: 'rgba(231, 76, 60, 0.2)',
            fill: true,
            data: []
        }]
    },
    options: commonOptions
});

const ctxFluxo = document.getElementById('chartFluxo').getContext('2d');
const chartFluxo = new Chart(ctxFluxo, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Fluxo (L/min)',
            borderColor: '#3498db',
            backgroundColor: 'rgba(52, 152, 219, 0.2)',
            fill: true,
            data: []
        }]
    },
    options: commonOptions
});

const ctxCooler = document.getElementById('chartCooler').getContext('2d');
const chartCooler = new Chart(ctxCooler, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Cooler PWM (%)',
            borderColor: '#2980b9',
            data: []
        }]
    },
    options: {
        ...commonOptions,
        scales: { y: { min: 0, max: 100 } }
    }
});

const ctxRes = document.getElementById('chartRes').getContext('2d');
const chartRes = new Chart(ctxRes, {
    type: 'line', // Stepped line para estados binários
    data: {
        labels: [],
        datasets: [{
            label: 'Resistência (ON/OFF)',
            borderColor: '#c0392b',
            data: [],
            stepped: true
        }]
    },
    options: {
        ...commonOptions,
        scales: { y: { min: 0, max: 1.2, ticks: { stepSize: 1 } } }
    }
});

// Função de Atualização
async function fetchData() {
    try {
        // Tenta buscar do backend. 
        // Se estiver testando localmente sem PHP rodando, isso vai falhar (CORS ou 404),
        // então certifique-se que o PHP está rodando ou simule dados.
        const response = await fetch('get_data.php');
        const data = await response.json();

        updateDashboard(data);
    } catch (error) {
        console.error("Erro ao buscar dados:", error);
    }
}

function updateDashboard(data) {
    if (!data.latest) return;

    // Atualiza Cards
    const latest = data.latest;

    // Formata valores
    const temp = parseFloat(latest.temperatura).toFixed(1);
    const fluxo = parseFloat(latest.fluxo).toFixed(1);
    const cooler = parseInt(latest.pwm_cooler);
    const res = parseInt(latest.estado_resistencia);

    document.getElementById('val-temp').innerText = `${temp} °C`;
    document.getElementById('val-fluxo').innerText = `${fluxo} L/min`;
    document.getElementById('val-cooler').innerText = `${cooler} %`;
    document.getElementById('val-res').innerText = res ? "ON" : "OFF";

    // Lógica de Cores/Status
    const statusTemp = document.getElementById('status-temp');
    if (temp > 40) { // Exemplo de limite
        statusTemp.innerText = "ALERTA: Alta Temp!";
        statusTemp.className = "status status-alert";
        document.querySelector('.card-temp').style.borderColor = "#c0392b";
    } else {
        statusTemp.innerText = "Estável";
        statusTemp.className = "status status-ok";
        document.querySelector('.card-temp').style.borderColor = "#2ecc71";
    }

    // Atualiza Gráficos (Histórico)
    // Limpa arrays
    const labels = data.history.map(item => {
        // Formata hora HH:MM:SS
        const date = new Date(item.timestamp);
        return date.toLocaleTimeString();
    });

    chartTemp.data.labels = labels;
    chartTemp.data.datasets[0].data = data.history.map(i => i.temperatura);
    chartTemp.update();

    chartFluxo.data.labels = labels;
    chartFluxo.data.datasets[0].data = data.history.map(i => i.fluxo);
    chartFluxo.update();

    chartCooler.data.labels = labels;
    chartCooler.data.datasets[0].data = data.history.map(i => i.pwm_cooler);
    chartCooler.update();

    chartRes.data.labels = labels;
    chartRes.data.datasets[0].data = data.history.map(i => i.estado_resistencia);
    chartRes.update();
}

// Atualizar a cada 2 segundos
setInterval(fetchData, 2000);
fetchData(); // Primeira chamada imediata
