<?php
// CRITICAL: Atualize estas credenciais com os dados do seu banco na HostGator
$host = "localhost"; 
$dbname = "nome_do_banco"; 
$username = "usuario_do_banco"; 
$password = "senha_do_banco";

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    // Definir timezone se necessário
    // date_default_timezone_set('America/Sao_Paulo');
} catch (PDOException $e) {
    die(json_encode(["error" => "Falha na conexão com o banco de dados: " . $e->getMessage()]));
}
?>
