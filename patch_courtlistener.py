#!/usr/bin/env python3
import re
import requests

# Ruta al archivo
file_path = '/home/ubuntu/olaw/olaw/search_targets/courtlistener.py'

# Leer el archivo original
with open(file_path, 'r') as file:
    content = file.read()

# Nuevo código con autenticación por API Key
new_search_request = (
    'raw_results = requests.get(\n'
    '    f"{api_url}search/",\n'
    '    headers={"Authorization": f"Token {api_key}"},\n'
    '    timeout=30\n'
    ')'
)

new_opinion_request = (
    'opinion_data = requests.get(\n'
    '    f"{api_url}opinions/",\n'
    '    headers={"Authorization": f"Token {api_key}"},\n'
    '    timeout=30\n'
    ')'
)

# Reemplazos con la nueva versión
updated_content = content.replace(
    'raw_results = requests.get(\n    f"{api_url}search/",\n    timeout=30)',
    new_search_request
)

updated_content = updated_content.replace(
    'opinion_data = requests.get(\n    f"{api_url}opinions/",\n    timeout=30)',
    new_opinion_request
)

# Escribir el contenido actualizado en el archivo
with open(file_path, 'w') as file:
    file.write(updated_content)

print("✅ CourtListener API client actualizado para usar la API Key.")
