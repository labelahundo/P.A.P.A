<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Registros de Baliza</title>
    <style>
        table, th, td {
            border: 1px solid #333;
            border-collapse: collapse;
            padding: 6px;
        }
    </style>
</head>
<body>
    <h2>Filtro de Registros</h2>
    <form method="GET">
        <label for="fecha">Fecha:</label>
        <input type="date" name="fecha" id="fecha">

        <label for="hora">Hora:</label>
        <input type="time" name="hora" id="hora">

        <label for="tipo">Tipo:</label>
        <select name="tipo" id="tipo">
            <option value="">Todos</option>
            <option value="general">General</option>
            <option value="baliza">Baliza</option>
        </select>

        <label for="tabla">Selecciona la tabla:</label>
        <select name="tabla" id="tabla">
            <option value="msg">Mensaje (Msg)</option>
            <option value="registro_general">Registro General</option>
            <!-- Añade más tablas aquí si es necesario -->
        </select>

        <input type="submit" value="Filtrar">
    </form>

    <?php
    // Conexión
    $conn = new mysqli("localhost", "val_read", "123", "baliza");
    if ($conn->connect_error) {
        die("Conexión fallida: " . $conn->connect_error);
    }

    // Filtros
    $fecha = $_GET['fecha'] ?? '';
    $hora = $_GET['hora'] ?? '';
    $tipo = $_GET['tipo'] ?? '';
    $tabla = $_GET['tabla'] ?? 'msg';  // Definir una tabla por defecto (msg)

    $conditions = [];
    if ($fecha) $conditions[] = "fecha = '$fecha'";
    if ($hora) $conditions[] = "hora = '$hora'";

    // Selección de la tabla
    if ($tabla == 'msg') {
        $sql = "SELECT * FROM msg";
        if ($conditions) {
            $sql .= " WHERE " . implode(" AND ", $conditions);
        }
        $sql .= " ORDER BY fecha DESC, hora DESC LIMIT 100";
        $result = $conn->query($sql);

        echo "<h3>Registros de Baliza (Msg)</h3><table><tr><th>ID</th><th>Módulo</th><th>Fecha</th><th>Hora</th><th>Problema</th><th>Magnitud</th></tr>";
        while ($row = $result->fetch_assoc()) {
            echo "<tr>
                <td>{$row['ID_msg']}</td>
                <td>{$row['ID_modulo']}</td>
                <td>{$row['fecha']}</td>
                <td>{$row['hora']}</td>
                <td>{$row['problema']}</td>
                <td>{$row['magnitud']}</td>
            </tr>";
        }
        echo "</table>";
    } elseif ($tabla == 'registro_general') {
        $sql = "SELECT * FROM registro_general";
        if ($conditions) {
            $sql .= " WHERE " . implode(" AND ", $conditions);
        }
        $sql .= " ORDER BY fecha DESC, hora DESC LIMIT 100";
        $result = $conn->query($sql);

        echo "<h3>Registros Generales</h3><table><tr><th>ID</th><th>Módulo</th><th>Fecha</th><th>Hora</th><th>Temp</th><th>Hum</th><th>Pres</th><th>VOC</th><th>X</th><th>Y</th><th>Z</th></tr>";
        while ($row = $result->fetch_assoc()) {
            echo "<tr>
                <td>{$row['ID_registro']}</td>
                <td>{$row['ID_modulo']}</td>
                <td>{$row['fecha']}</td>
                <td>{$row['hora']}</td>
                <td>{$row['temp']}</td>
                <td>{$row['hum']}</td>
                <td>{$row['pres']}</td>
                <td>{$row['VOC']}</td>
                <td>{$row['x']}</td>
                <td>{$row['y']}</td>
                <td>{$row['z']}</td>
            </tr>";
        }
        echo "</table>";
    }

    // Agrega más condiciones y tablas si lo necesitas, de acuerdo con las tablas que tengas en tu base de datos.

    $conn->close();
    ?>
</body>
</html>
