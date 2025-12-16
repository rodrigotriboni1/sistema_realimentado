<?php
header("Content-Type: application/json");
header("Access-Control-Allow-Origin: *"); // Permite que o dashboard acesse de qualquer local (útil para testes locais)
require 'db_connect.php';

try {
    // Buscar o dado mais recente (para os cards de status)
    $stmtLatest = $pdo->query("SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1");
    $latest = $stmtLatest->fetch(PDO::FETCH_ASSOC);

    // Buscar histórico recente (últimos 50 pontos para os gráficos)
    $stmtHistory = $pdo->query("SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 50");
    $history = $stmtHistory->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        "latest" => $latest,
        // Invertemos o histórico para a ordem cronológica (Mais antigo -> Mais novo) facilitar o gráfico
        "history" => array_reverse($history) 
    ]);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(["status" => "error", "message" => "Erro ao buscar dados: " . $e->getMessage()]);
}
?>
