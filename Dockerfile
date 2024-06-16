# Usa una imagen base oficial de Python
FROM python:3.9-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia el archivo de requisitos (si tienes dependencias externas) y el script a la imagen
COPY requirements.txt requirements.txt
COPY main.py main.py

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Crea el directorio para almacenar las versiones
RUN mkdir -p versions