import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pdf2image import convert_from_path
import pytesseract

BASE_URL = "https://vision.davivienda.com"
PAGE_URL = "https://vision.davivienda.com/en-que-invertir/acciones/inversionistas-de-acciones"

PDF_FOLDER = "data_raw/pdf/"
CSV_FOLDER = "data_raw/csv_mensual/"
BASE_CONSOLIDADA = "data_processed/base_consolidada.csv"
LOG_FILE = "logs/procesados.txt"

os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs("logs", exist_ok=True)

def obtener_articulo_espanol():
    response = requests.get(PAGE_URL)
    soup = BeautifulSoup(response.text, "lxml")

    meses_es = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre",
        "noviembre", "diciembre"
    ]

    links = soup.find_all("a", href=True)
    articulos_validos = []

    for link in links:
        href = link["href"].lower()

        if "inversionistas-acciones" in href:
            if any(mes in href for mes in meses_es):
                if not href.startswith("http"):
                    href = urljoin(BASE_URL, href)

                articulos_validos.append(href)

    if articulos_validos:
        return articulos_validos[0]

    return None


def obtener_pdf_desde_articulo(url_articulo):
    response = requests.get(url_articulo)
    soup = BeautifulSoup(response.text, "lxml")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" in href:
            if not href.startswith("http"):
                href = urljoin(BASE_URL, href)
            return href

    return None


def ya_procesado(nombre_pdf):
    if not os.path.exists(LOG_FILE):
        return False

    with open(LOG_FILE, "r") as f:
        procesados = f.read().splitlines()

    return nombre_pdf in procesados


def registrar_procesado(nombre_pdf):
    with open(LOG_FILE, "a") as f:
        f.write(nombre_pdf + "\n")


def descargar_pdf(url_pdf):
    nombre_pdf = url_pdf.split("/")[-1]
    ruta = os.path.join(PDF_FOLDER, nombre_pdf)

    response = requests.get(url_pdf)
    with open(ruta, "wb") as f:
        f.write(response.content)

    return ruta, nombre_pdf


def extraer_texto_primera_pagina(ruta_pdf):
    paginas = convert_from_path(ruta_pdf, first_page=1, last_page=1)
    imagen = paginas[0]
    texto = pytesseract.image_to_string(imagen, lang="spa")
    return texto


def texto_a_dataframe(texto):
    lineas = texto.split("\n")
    datos = []

    for linea in lineas:
        linea = linea.strip()

        # Detectar líneas que tengan números
        if re.search(r"\d", linea):
            partes = re.split(r"\s{2,}", linea)

            if len(partes) >= 2:
                datos.append(partes)

    if not datos:
        return None

    df = pd.DataFrame(datos)
    df["fecha_proceso"] = pd.Timestamp.today()

    return df


def guardar_csv_mensual(df, nombre_pdf):
    nombre_csv = nombre_pdf.replace(".pdf", ".csv")
    ruta_csv = os.path.join(CSV_FOLDER, nombre_csv)
    df.to_csv(ruta_csv, index=False)
    return ruta_csv


def actualizar_base_consolidada(df):
    if os.path.exists(BASE_CONSOLIDADA):
        base = pd.read_csv(BASE_CONSOLIDADA)
        base = pd.concat([base, df], ignore_index=True)
    else:
        base = df

    base.to_csv(BASE_CONSOLIDADA, index=False)


def main():
    print("Buscando artículo en español...")
    articulo = obtener_articulo_espanol()

    if not articulo:
        print("No se encontró artículo válido.")
        return

    print("Buscando PDF...")
    pdf_url = obtener_pdf_desde_articulo(articulo)

    if not pdf_url:
        print("No se encontró PDF.")
        return

    ruta_pdf, nombre_pdf = descargar_pdf(pdf_url)

    if ya_procesado(nombre_pdf):
        print("PDF ya procesado.")
        return

    print("Aplicando OCR...")
    texto = extraer_texto_primera_pagina(ruta_pdf)

    print("Convirtiendo a DataFrame...")
    df = texto_a_dataframe(texto)

    if df is None:
        print("No se pudo estructurar la tabla.")
        return

    print("Guardando CSV mensual...")
    guardar_csv_mensual(df, nombre_pdf)

    print("Actualizando base consolidada...")
    actualizar_base_consolidada(df)

    registrar_procesado(nombre_pdf)

    print("Proceso completo exitosamente.")


if __name__ == "__main__":
    main()
