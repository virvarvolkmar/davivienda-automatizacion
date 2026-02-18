import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pdf2image import convert_from_path
import pytesseract

# ==============================
# CONFIGURACIÓN
# ==============================

BASE_URL = "https://vision.davivienda.com"

PDF_FOLDER = "data_raw/pdf/"
CSV_FOLDER = "data_raw/csv_mensual/"
BASE_CONSOLIDADA = "data_processed/base_consolidada.csv"
LOG_FILE = "logs/procesados.txt"

os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs("data_processed", exist_ok=True)
os.makedirs("logs", exist_ok=True)


# ==============================
# 1️⃣ OBTENER ÚLTIMO ARTÍCULO DESDE API
# ==============================

def obtener_ultimo_articulo_api():
    url_api = "https://apis-vision.davivienda.com/api/vd/site/report/get_reports_by_category"

    payload = {
        "id_category": 89,
        "language": "ES",
        "limit": 4,
        "page": 1
    }

    try:
        response = requests.post(url_api, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error consultando API: {e}")
        return None

    reportes = data.get("data", {}).get("reports", [])

    if not reportes:
        print("No se encontraron reportes en la API.")
        return None

    # Filtrar solo español
    reportes_es = [r for r in reportes if r.get("language") == "ES"]

    if not reportes_es:
        print("No se encontraron reportes en español.")
        return None

    ultimo = reportes_es[0]

    seo_url = ultimo.get("seo_url")

    if not seo_url:
        print("No se encontró seo_url en el reporte.")
        return None

    url_articulo = urljoin(BASE_URL, seo_url)

    print(f"Artículo encontrado: {url_articulo}")

    return url_articulo


# ==============================
# 2️⃣ BUSCAR PDF DENTRO DEL ARTÍCULO
# ==============================

def obtener_pdf_desde_articulo(url_articulo):
    try:
        response = requests.get(url_articulo, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Error entrando al artículo: {e}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if ".pdf" in href.lower():
            if not href.startswith("http"):
                href = urljoin(BASE_URL, href)

            print(f"PDF encontrado: {href}")
            return href

    print("No se encontró ningún PDF dentro del artículo.")
    return None


# ==============================
# 3️⃣ CONTROL DE PROCESADOS
# ==============================

def ya_procesado(nombre_pdf):
    if not os.path.exists(LOG_FILE):
        return False

    with open(LOG_FILE, "r") as f:
        procesados = f.read().splitlines()

    return nombre_pdf in procesados


def registrar_procesado(nombre_pdf):
    with open(LOG_FILE, "a") as f:
        f.write(nombre_pdf + "\n")


# ==============================
# 4️⃣ DESCARGA PDF
# ==============================

def descargar_pdf(url_pdf):
    nombre_pdf = url_pdf.split("/")[-1]
    ruta = os.path.join(PDF_FOLDER, nombre_pdf)

    try:
        response = requests.get(url_pdf, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error descargando PDF: {e}")
        return None, None

    with open(ruta, "wb") as f:
        f.write(response.content)

    print(f"PDF descargado en: {ruta}")

    return ruta, nombre_pdf


# ==============================
# 5️⃣ OCR PRIMERA PÁGINA
# ==============================

def extraer_texto_primera_pagina(ruta_pdf):
    try:
        paginas = convert_from_path(ruta_pdf, first_page=1, last_page=1)
        imagen = paginas[0]
        texto = pytesseract.image_to_string(imagen, lang="spa")
        return texto
    except Exception as e:
        print(f"Error aplicando OCR: {e}")
        return None


# ==============================
# 6️⃣ CONVERTIR TEXTO A DATAFRAME
# ==============================

def texto_a_dataframe(texto):
    if not texto:
        return None

    lineas = texto.split("\n")
    datos = []

    for linea in lineas:
        linea = linea.strip()

        if re.search(r"\d", linea):
            partes = re.split(r"\s{2,}", linea)

            if len(partes) >= 2:
                datos.append(partes)

    if not datos:
        return None

    df = pd.DataFrame(datos)
    df["fecha_proceso"] = pd.Timestamp.today()

    return df


# ==============================
# 7️⃣ GUARDAR CSV MENSUAL
# ==============================

def guardar_csv_mensual(df, nombre_pdf):
    nombre_csv = nombre_pdf.replace(".pdf", ".csv")
    ruta_csv = os.path.join(CSV_FOLDER, nombre_csv)

    df.to_csv(ruta_csv, index=False)

    print(f"CSV mensual guardado en: {ruta_csv}")

    return ruta_csv


# ==============================
# 8️⃣ ACTUALIZAR BASE CONSOLIDADA
# ==============================

def actualizar_base_consolidada(df):
    if os.path.exists(BASE_CONSOLIDADA):
        base = pd.read_csv(BASE_CONSOLIDADA)
        base = pd.concat([base, df], ignore_index=True)
    else:
        base = df

    base.to_csv(BASE_CONSOLIDADA, index=False)

    print("Base consolidada actualizada.")


# ==============================
# 9️⃣ MAIN
# ==============================

def main():

    print("Consultando API oficial...")
    url_articulo = obtener_ultimo_articulo_api()

    if not url_articulo:
        print("Proceso detenido.")
        return

    print("Buscando PDF dentro del artículo...")
    pdf_url = obtener_pdf_desde_articulo(url_articulo)

    if not pdf_url:
        print("Proceso detenido.")
        return

    ruta_pdf, nombre_pdf = descargar_pdf(pdf_url)

    if not ruta_pdf:
        print("Proceso detenido.")
        return

    if ya_procesado(nombre_pdf):
        print("PDF ya procesado anteriormente.")
        return

    print("Aplicando OCR...")
    texto = extraer_texto_primera_pagina(ruta_pdf)

    if not texto:
        print("No se pudo extraer texto.")
        return

    print("Convirtiendo texto a DataFrame...")
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


# ==============================

if __name__ == "__main__":
    main()
