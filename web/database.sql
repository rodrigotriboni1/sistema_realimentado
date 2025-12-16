CREATE TABLE IF NOT EXISTS measurements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    temperatura FLOAT NOT NULL,
    fluxo FLOAT NOT NULL,
    pwm_cooler INT NOT NULL,
    estado_resistencia BOOLEAN NOT NULL,
    INDEX (timestamp)
);
