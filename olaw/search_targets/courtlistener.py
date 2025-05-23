import os
import re
import traceback
import requests
import html2text
import logging
from . import SearchTarget

# Configuración de logs
log_file = os.path.join(os.path.dirname(__file__), '../../logs/search.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

class CourtListener(SearchTarget):

    RESULTS_DATA_FORMAT = {
        "id": "",
        "case_name": "",
        "court": "",
        "absolute_url": "",
        "status": "",
        "date_filed": "",
        "text": "",
        "prompt_text": "",
        "ui_text": "",
        "ui_url": "",
    }

    @staticmethod
    def search(search_statement: str):
        api_url = os.environ["COURT_LISTENER_API_URL"]
        base_url = os.environ["COURT_LISTENER_BASE_URL"]
        api_key = os.environ["COURT_LISTENER_API_KEY"]
        max_results = int(os.environ["COURT_LISTENER_MAX_RESULTS"])

        prepared_results = []
        filed_before = None
        filed_after = None

        logging.info(f"🔍 Starting search for: {search_statement}")

        # Validar palabras prohibidas
        prohibited_terms = {"law", "laws", "case", "cases", "precedent", "precedents", "adjudicated"}
        statement_words = set(re.findall(r'\w+', search_statement.lower()))
        if prohibited_terms.intersection(statement_words):
            msg = f"Search statement contains prohibited terms: {prohibited_terms.intersection(statement_words)}"
            logging.warning(f"❌ {msg}")
            raise Exception(msg)

        # Extraer fechas si existen
        if "dateFiled" in search_statement:
            try:
                filed_after = re.findall(r"dateFiled:\[([0-9]{4}-[0-9]{2}-[0-9]{2}) TO", search_statement)[0].replace("-", "/")
                filed_before = re.findall(r"dateFiled:\[[0-9]{4}-[0-9]{2}-[0-9]{2} TO ([0-9]{4}-[0-9]{2}-[0-9]{2})\]", search_statement)[0].replace("-", "/")
            except Exception:
                pass

        headers = {
            "Authorization": f"Token {api_key}"
        }

        # --- Primer intento ---
        try:
            response = requests.get(
                f"{api_url}search/",
                headers=headers,
                timeout=10,
                params={
                    "type": "o",
                    "order": "score desc",
                    "q": search_statement,
                    "filed_after": filed_after,
                    "filed_before": filed_before,
                },
            )

            if response.status_code != 200:
                raise Exception(f"CourtListener API error {response.status_code}: {response.text}")

            raw_results = response.json()

            # Retry si no hay resultados
            if "results" not in raw_results or not raw_results["results"]:
                logging.info("🔁 Retry fallback to keyword-only search")

                fallback_keywords = re.sub(r'[^a-zA-Z0-9 ]', '', search_statement)
                fallback_query = " AND ".join(fallback_keywords.split())

                retry_response = requests.get(
                    f"{api_url}search/",
                    headers=headers,
                    timeout=10,
                    params={
                        "type": "o",
                        "order": "score desc",
                        "q": fallback_query,
                        "filed_after": filed_after,
                        "filed_before": filed_before,
                    },
                )

                if retry_response.status_code == 200:
                    raw_results = retry_response.json()
                    logging.info(f"🔁 Retry fallback found: {len(raw_results.get('results', []))} results")
                else:
                    logging.warning(f"⚠️ Retry failed with status {retry_response.status_code}")

            if "results" not in raw_results:
                raise Exception(f"CourtListener response missing 'results': {raw_results}")

        except Exception as e:
            logging.error(traceback.format_exc())
            raise Exception(f"Failed to fetch results from CourtListener: {str(e)}")

        # --- Procesar resultados ---
        for i in range(0, min(max_results, len(raw_results["results"]))):
            try:
                opinion_metadata = raw_results["results"][i]

                # Validar campos esenciales
                required_fields = ["caseName", "court", "absolute_url", "status", "dateFiled"]
                if not all(field in opinion_metadata for field in required_fields):
                    logging.warning(f"⚠️ Skipped result {i} due to missing fields: {opinion_metadata.keys()}")
                    continue

                # ID: puede venir como "id" o "cluster_id"
                opinion_id = opinion_metadata.get("id") or opinion_metadata.get("cluster_id")
                if not opinion_id:
                    logging.warning(f"⚠️ Skipped result {i} - no 'id' or 'cluster_id'")
                    continue

                opinion = dict(CourtListener.RESULTS_DATA_FORMAT)

                opinion["id"] = opinion_id
                opinion["case_name"] = opinion_metadata["caseName"]
                opinion["court"] = opinion_metadata["court"]
                opinion["absolute_url"] = base_url + opinion_metadata["absolute_url"]
                opinion["status"] = opinion_metadata["status"]
                opinion["date_filed"] = opinion_metadata["dateFiled"]

                opinion_data = requests.get(
                    f"{api_url}opinions/",
                    headers=headers,
                    timeout=10,
                    params={"id": opinion["id"]},
                ).json()

                opinion_data = opinion_data.get("results", [{}])[0]
                opinion["text"] = html2text.html2text(opinion_data.get("html", ""))

                opinion["prompt_text"] = f"[{i+1}] {opinion['case_name']} ({opinion['date_filed'][0:4]}) {opinion['court']}, as sourced from {opinion['absolute_url']}:"
                opinion["ui_text"] = f"[{i+1}] {opinion['case_name']} ({opinion['date_filed'][0:4]}), {opinion['court']}"
                opinion["ui_url"] = opinion["absolute_url"]

                prepared_results.append(opinion)

            except Exception as e:
                logging.warning(f"⚠️ Skipped result {i} due to error: {e}")
                continue

        logging.info(f"✅ Total results returned: {len(prepared_results)}")
        return prepared_results
