import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://vision.davivienda.com"
PAGE_URL = "https://vision.davivienda.com/en-que-invertir/acciones/inversionistas-de-acciones"

PDF_FOLDER = "data_raw/pdf/"
LOG_FILE = "logs/procesados.txt"

os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs("logs", exist_ok=True)


def obtener_articulo_espanol():
    """
    Busca el artículo más reciente en español
    Ignora artículos en inglés
    """
    response = requests.get(PAGE_URL)
    soup = BeautifulSoup(response.text, "lxml")

    links = soup.find_all("a", href=True)

    articulos_validos = []

    for link in links:
        href = link["href"]
        texto = link.get_text(strip=True)

        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)

        # Condiciones para artículo en español
        if (
            "Inversionistas" in texto
            and "Foreign" not in texto
            and "/en/" not in href
        ):
            articulos_validos.append(href)

    if articulos_validos:
        return articulos_validos[0]

    return None


def obtener_pdf_desde_articulo(url_articulo):
    """
    Entra al artículo y busca el link del PDF
    """
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

    return nombre_pdf


def main():
    print("Buscando artículo en español...")
    articulo = obtener_articulo_espanol()

    if not articulo:
        print("No se encontró artículo válido.")
        return

    print("Artículo encontrado:", articulo)

    print("Buscando PDF dentro del artículo...")
    pdf_url = obtener_pdf_desde_articulo(articulo)

    if not pdf_url:
        print("No se encontró PDF.")
        return

    nombre_pdf = pdf_url.split("/")[-1]

    if ya_procesado(nombre_pdf):
        print("PDF ya fue procesado anteriormente.")
        return

    print("Descargando PDF...")
    descargar_pdf(pdf_url)

    registrar_procesado(nombre_pdf)

    print("Proceso completado correctamente.")


if __name__ == "__main__":
    main()

