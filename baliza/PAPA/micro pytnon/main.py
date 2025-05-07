import uasyncio as asyncio
from machine import I2C, UART, Pin
from bme680 import BME680_I2C
from ADXL345 import ADXL345

# === Inicialización de hardware ===
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=100_000)
uart = UART(0, baudrate=115200)
i2c_lock = asyncio.Lock()


# === Inicialización de sensores ===
bme = BME680_I2C(i2c=i2c, address=0x77)
adxl = ADXL345(i2c, 0x53)

# === Variables globales para promedios ===
lecturas = {
    "temp": [], "hum": [], "pres": [], "gas": [],
    "x": [], "y": [], "z": []
}

# Últimos valores para detectar cambios bruscos
ult_x = ult_y = ult_z = 0

async def leer_adxl345():
    global ult_x, ult_y, ult_z
    while True:
        async with i2c_lock:
            x = adxl.xValue
            y = adxl.yValue
            z = adxl.zValue

        dx, dy, dz = abs(x - ult_x), abs(y - ult_y), abs(z - ult_z)
        if dx > 8 or dy > 8 or dz > 8:
            alerta = f"movimiento brusco X:{dx} Y:{dy} Z:{dz}"
            uart.write(f"AT+SEND=102,{len(alerta)},{alerta}\r\n")
            print("[ALERTA] Movimiento brusco:", alerta.strip())

        ult_x, ult_y, ult_z = x, y, z

        # Acumular para promedio
        lecturas["x"].append(x)
        lecturas["y"].append(y)
        lecturas["z"].append(z)

        await asyncio.sleep(1)

async def leer_bme680():
    while True:
        async with i2c_lock:
            temp = bme.temperature
            hum = bme.humidity
            pres = bme.pressure
            gas = bme.gas / 1000 if bme.gas else 0

        print("BME680 → Temp: {:.1f} °C | Hum: {:.1f}% | Pres: {:.1f} hPa | Gas: {:.1f} kh".format(
            temp, hum, pres, gas))

        # Alerta por temperatura crítica
        if temp > 70:
            alerta = f"¡ALERTA! Temperatura muy alta: {temp:.1f} °C\r\n"
            uart.write(f"AT+SEND=102,{len(alerta)},{alerta}")
            print("[ALERTA] Temperatura:", alerta.strip())

        # Acumular para promedio
        lecturas["temp"].append(temp)
        lecturas["hum"].append(hum)
        lecturas["pres"].append(pres)
        lecturas["gas"].append(gas)

        await asyncio.sleep(120)

async def enviar_lora():
    while True:
        await asyncio.sleep(600)  # Esperar 10 minutos

        # Calcular promedios
        promedio = lambda lista: sum(lista) / len(lista) if lista else 0

        temp = promedio(lecturas["temp"])
        hum = promedio(lecturas["hum"])
        pres = promedio(lecturas["pres"])
        gas = promedio(lecturas["gas"])
        x = promedio(lecturas["x"])
        y = promedio(lecturas["y"])
        z = promedio(lecturas["z"])

        paquete = "AVG → T:{:.1f}C H:{:.1f}% P:{:.1f}hPa G:{:.1f}kh X:{:.1f} Y:{:.1f} Z:{:.1f}".format(
            temp, hum, pres, gas, x, y, z)
        mensaje = f"AT+SEND=102,{len(paquete)},{paquete}\r\n"

        uart.write(mensaje)
        print("[LORA] Enviado promedio:", mensaje.strip())

        # Limpiar listas después del envío
        for key in lecturas:
            lecturas[key].clear()

async def recibir_lora():
    while True:
        if uart.any():
            mensaje = uart.readline()
            if mensaje:
                print("LoRa Respuesta:", mensaje.decode().strip())
        await asyncio.sleep(0.1)

# === Función principal ===
async def main():
    asyncio.create_task(leer_adxl345())
    asyncio.create_task(leer_bme680())
    asyncio.create_task(enviar_lora())
    asyncio.create_task(recibir_lora())
    while True:
        await asyncio.sleep(60)

# === Iniciar ejecución ===
asyncio.run(main())

