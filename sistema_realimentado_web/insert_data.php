<?php
header("Content-Type: application/json");
require 'db_connect.php';

// Verifica se é um POST
if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    // Recebe o JSON bruto da requisição
    $input = file_get_contents("php://input");
    $data = json_decode($input, true);

    // Valida se os campos necessários existem
    if (isset($data['temperatura']) && isset($data['fluxo']) && isset($data['pwm_cooler'])) {
        try {
            $stmt = $pdo->prepare("INSERT INTO measurements (temperatura, fluxo, pwm_cooler, estado_resistencia) VALUES (:temp, :fluxo, :pwm, :res)");
            
            // Estado resistência pode vir como boolean ou int, garantimos int para o banco (1 ou 0)
            $resState = (!empty($data['estado_resistencia'])) ? 1 : 0;

            $stmt->execute([
                ':temp' => $data['temperatura'],
                ':fluxo' => $data['fluxo'],
                ':pwm' => $data['pwm_cooler'],
                ':res' => $resState
            ]);

            http_response_code(201);
            echo json_encode(["status" => "success", "message" => "Dados inseridos com sucesso"]);
        } catch (PDOException $e) {
            http_response_code(500);
            echo json_encode(["status" => "error", "message" => "Erro ao inserir no banco: " . $e->getMessage()]);
        }
    } else {
        http_response_code(400);
        echo json_encode(["status" => "error", "message" => "Dados incompletos. Esperado: temperatura, fluxo, pwm_cooler"]);
    }
} else {
    http_response_code(405);
    echo json_encode(["status" => "error", "message" => "Metodo nao permitido. Use POST."]);
}
?>
