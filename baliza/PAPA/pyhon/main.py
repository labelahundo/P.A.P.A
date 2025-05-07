import pymysql
import random
import time
import serial
import asyncio
from datetime import datetime
import re

# Configuración
PUERTO = 'COM9'
BAUDIOS = 115200
MI_DIRECCION = '102'

class ReceptorDatos:
    def __init__(self):
        # Conexion a la base de datos
        self.conn = pymysql.connect(
            host='localhost',
            user='val_ins',
            password='123',
            database='baliza'
        )
        self.cursor = self.conn.cursor()
        
        # Conexion al puerto serie
        self.uart = serial.Serial(PUERTO, BAUDIOS, timeout=2)
        print(f"Conexin serial establecida en {PUERTO} a {BAUDIOS} baudios")

    def insertar_modulo(self, id_modulo):
        """Insertar un nuevo módulo con ubicación aleatoria"""
        try:
            ubicacion = f"Ubicacion_{random.randint(1, 100)}"
            query = "INSERT INTO modulos (ID_modulo, ubicacion) VALUES (%s, %s)"
            self.cursor.execute(query, (id_modulo, ubicacion))
            self.conn.commit()
            print(f"Módulo {id_modulo} registrado en ubicación {ubicacion}")
            return True
        except pymysql.IntegrityError:
            print(f"Módulo {id_modulo} ya existe en la base de datos")
            return True
        except Exception as e:
            print(f"Error al insertar módulo {id_modulo}: {e}")
            return False

    def enviar_confirmacion(self, direccion, tipo_mensaje):
        """Enviar  de confirmación al módulo"""
        try:
            fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mensaje = f"{fecha_hora}||{tipo_mensaje}"
            comando = f"AT+SEND={direccion},{len(mensaje)},{mensaje}\r\n"
            self.uart.write(comando.encode('utf-8'))
            print(f"ACK enviado a {direccion} para mensaje tipo {tipo_mensaje}")
            return True
        except Exception as e:
            print(f"Error al enviar ACK: {e}")
            return False

    def guardar_datos_generales(self, direccion, fecha, hora, datos):
        """Guardar datos tipo 1 en registro_general"""
        try:
            query = """
            INSERT INTO registro_general 
            (ID_modulo, fecha, hora, temp, hum, pres, VOC, x, y, z) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores = (
                direccion, fecha, hora,
                datos.get('temp'), datos.get('hum'), datos.get('pres'), datos.get('voc'),
                datos.get('x'), datos.get('y'), datos.get('z')
            )
            self.cursor.execute(query, valores)
            self.conn.commit()
            print(f"Datos generales guardados para módulo {direccion}")
            return True
        except Exception as e:
            print(f"Error al guardar datos generales: {e}")
            return False

    def guardar_alerta(self, direccion, fecha, hora, tipo, datos):
        """Guardar alertas tipo 2 y 3 en msg"""
        try:
            if tipo == '2':
                problema = "alta_temp"
                magnitud = datos.get('temp')
            else:  # tipo 3
                problema = "movimiento"
                magnitud = datos.get('magnitud')
            
            query = """
            INSERT INTO msg 
            (ID_modulo, fecha, hora, problema, magnitud) 
            VALUES (%s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (direccion, fecha, hora, problema, magnitud))
            self.conn.commit()
            print(f"Alerta tipo {tipo} guardada para módulo {direccion}")
            return True
        except Exception as e:
            print(f"Error al guardar alerta: {e}")
            return False

    async def procesar_mensaje_tipo1(self, direccion, fecha, hora, datos):
        """Procesar mensajes tipo 1 (datos generales)"""
        try:
            # Extraer datos del formato: T:val C H:val% P:valhPa G:valkh X:val Y:val Z:val
            datos_dict = {}
            partes = datos.split()
            
            for parte in partes:
                if ':' in parte:
                    clave, valor = parte.split(':', 1)
                    clave = clave.lower()
                    # Eliminar unidades y convertir a float
                    valor = float(re.sub(r'[^0-9.-]', '', valor))
                    datos_dict[clave] = valor
            
            if not {'t', 'h', 'p', 'g', 'x', 'y', 'z'}.issubset(datos_dict.keys()):
                print("Faltan datos en el mensaje tipo 1")
                return False
            
            return self.guardar_datos_generales(
                direccion, fecha, hora,
                {'temp': datos_dict['t'], 'hum': datos_dict['h'], 'pres': datos_dict['p'],
                 'voc': datos_dict['g'], 'x': datos_dict['x'], 'y': datos_dict['y'], 'z': datos_dict['z']}
            )
        except Exception as e:
            print(f"Error al procesar mensaje tipo 1: {e}")
            return False

    async def procesar_mensaje_tipo2(self, direccion, fecha, hora, datos):
        """Procesar mensajes tipo 2 (alerta temperatura)"""
        try:
            temp = float(re.sub(r'[^0-9.-]', '', datos.split()[0]))
            return self.guardar_alerta(
                direccion, fecha, hora, '2',
                {'temp': temp}
            )
        except Exception as e:
            print(f"Error al procesar mensaje tipo 2: {e}")
            return False

    async def procesar_mensaje_tipo3(self, direccion, fecha, hora, datos):
        """Procesar mensajes tipo 3 (alerta movimiento)"""
        try:
            # Extraer valores X, Y, Z del formato: X:val Y:val Z:val
            valores = re.findall(r"[-+]?\d*\.\d+|\d+", datos)
            if len(valores) >= 3:
                magnitud = (sum(float(v)**2 for v in valores[:3]))**0.5
            else:
                magnitud = None
            
            return self.guardar_alerta(
                direccion, fecha, hora, '3',
                {'magnitud': magnitud}
            )
        except Exception as e:
            print(f"Error al procesar mensaje tipo 3: {e}")
            return False

    async def procesar_mensaje_tipo4(self, direccion, fecha, hora):
        """Procesar mensajes tipo 4 (registro/emparejamiento)"""
        try:
            # Verificar si el módulo ya esta registrado
            self.cursor.execute("SELECT 1 FROM modulos WHERE ID_modulo = %s", (direccion,))
            if not self.cursor.fetchone():
                if not self.insertar_modulo(direccion):
                    return False
            
            # Enviar confirmación
            return self.enviar_confirmacion(direccion, '4')
        except Exception as e:
            print(f"Error al procesar mensaje tipo 4: {e}")
            return False

    async def manejar_mensaje(self, mensaje):
        """Manejar mensajes entrantes y dirigirlos al procesador adecuado"""
        if not mensaje.startswith("+RCV="):
            return False
            
        try:
            # Parsear el mensaje LoRa
            payload = mensaje[5:].strip()
            partes = payload.split(',', 2)
            
            if len(partes) < 3:
                print("Formato de mensaje invalido (partes insuficientes)")
                return False
                
            direccion = partes[0].strip()
            longitud = partes[1].strip()
            contenido = partes[2].strip()
            
            # Validar dirección y longitud
            if not direccion.isdigit() or not longitud.isdigit():
                print("Dirección o longitud invlidas")
                return False
                
            # Parsear contenido: fecha_hora|tipo|datos
            match = re.search(r"([\d\-]+\s[\d:]+)\s*\|(\d)\|(.*)", contenido)
            if not match:
                print("Formato de contenido invalido")
                return False
                
            fecha_hora, tipo, datos = match.groups()
            fecha, hora = fecha_hora.split()
            
            # Procesar según el tipo de mensaje
            if tipo == '1':
                exito = await self.procesar_mensaje_tipo1(direccion, fecha, hora, datos)
            elif tipo == '2':
                exito = await self.procesar_mensaje_tipo2(direccion, fecha, hora, datos)
            elif tipo == '3':
                exito = await self.procesar_mensaje_tipo3(direccion, fecha, hora, datos)
            elif tipo == '4':
                exito = await self.procesar_mensaje_tipo4(direccion, fecha, hora)
            else:
                print(f"Tipo de mensaje desconocido: {tipo}")
                return False
            
            # Enviar confirmación para tipos 1, 2 y 3
            if exito and tipo in ('1', '2', '3'):
                return self.enviar_confirmacion(direccion, tipo)
            
            return exito
                
        except Exception as e:
            print(f"Error al manejar mensaje: {e}")
            return False

    async def escuchar_mensajes(self):
        """Bucle principal para escuchar mensajes"""
        print("Iniciando servidor. Esperando mensajes...")
        while True:
            await asyncio.sleep(0.1)
            if self.uart.in_waiting:
                try:
                    raw = self.uart.readline()
                    
                    # Solo continuar si la línea tiene algo y parece comenzar como mensaje válido
                    if b'+RCV=' in raw:
                        try:
                            mensaje = raw.decode('utf-8').strip()
                            if mensaje.startswith("+RCV="):
                                print(f"Mensaje recibido: {mensaje}")
                                await self.manejar_mensaje(mensaje)
                            else:
                                print(f"Mensaje no relevante: {mensaje}")
                        except UnicodeDecodeError:
                            print(f"Error de decodificación: bytes no válidos -> {raw}")
                    else:
                        try:
                            # Intentar decodificar cualquier otra cosa para depuración
                            otro = raw.decode('utf-8', errors='ignore').strip()
                            if otro:
                                print(f"Mensaje no procesado: {otro}")
                        except Exception:
                            print(f"Bytes ignorados: {raw}")
                            
                except Exception as e:
                    print(f"Error al procesar mensaje: {e}")


    async def cerrar(self):
        """Cerrar conexiones adecuadamente"""
        self.uart.close()
        self.cursor.close()
        self.conn.close()
        print("Conexiones cerradas correctamente")

async def main():
    receptor = ReceptorDatos()
    try:
        await receptor.escuchar_mensajes()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
    except Exception as e:
        print(f"Error crítico: {e}")
    finally:
        await receptor.cerrar()

if __name__ == '__main__':
    asyncio.run(main())


