import os
import traceback
import json
import re

from flask import current_app, jsonify, request
from openai import OpenAI
import ollama

from olaw.utils import list_available_models, get_limiter

API_EXTRACT_SEARCH_STATEMENT_RATE_LIMIT = os.environ["API_EXTRACT_SEARCH_STATEMENT_RATE_LIMIT"]

# 🧠 Prompt embebido con instrucciones precisas para coincidencia exacta
EXTRACT_SEARCH_STATEMENT_PROMPT = """You are a legal assistant. Your job is to analyze a user message and generate a legal search query compatible with the CourtListener API.

Return only a JSON object with the following format:
{
  "search_statement": "...",
  "search_target": "courtlistener"
}

Instructions:

1. If the user message involves a case name (e.g., Kramer v. Kramer), format it exactly using caseName:("...").

2. Always use 'v.' (with period) to separate parties. Never use 'vs', 'vs.', or 'versus'.

3. Include dateFiled:[YYYY-MM-DD TO YYYY-MM-DD] if a year is mentioned.

4. NEVER use the words: law, laws, case, cases, precedent, precedents, adjudicated.

Example:
User: Was the case Kramer versus Kramer decided in 1979?
Output:
{
  "search_statement": "caseName:(\\"Kramer v. Kramer\\") AND dateFiled:[1979-01-01 TO 1979-12-31]",
  "search_target": "courtlistener"
}

Now analyze this message:"""


@current_app.route("/api/extract-search-statement", methods=["POST"])
@get_limiter().limit(API_EXTRACT_SEARCH_STATEMENT_RATE_LIMIT)
def post_extract_search_statement():
    available_models = list_available_models()
    input = request.get_json()
    temperature = 0.0
    output = ""
    timeout = 30

    # --- Validar mensaje ---
    if "message" not in input:
        return jsonify({"error": "No message provided."}), 400

    message = str(input["message"]).strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    # 🔁 Preprocesar: reemplazar 'vs', 'vs.', 'versus' por 'v.'
    message = re.sub(r'\b(vs\.?|versus)\b', 'v.', message, flags=re.IGNORECASE)

    # --- Validar temperatura ---
    if "temperature" in input:
        try:
            temperature = float(input["temperature"])
            assert temperature >= 0.0
        except Exception:
            return jsonify({"error": "temperature must be a float >= 0.0."}), 400

    # --- Construir prompt final ---
    prompt = f"{EXTRACT_SEARCH_STATEMENT_PROMPT}\n{message}"

    # --- Determinar modelo a usar ---
    model = input.get("model", "")
    if not model:
        if os.getenv("OPENAI_API_KEY"):
            model = "openai/gpt-4"
        elif os.getenv("OLLAMA_API_URL"):
            model = "ollama/mistral"
        else:
            return jsonify({"error": "No model provided and no provider (OpenAI/Ollama) configured."}), 400

    if model not in available_models:
        return jsonify({"error": f"Requested model '{model}' is invalid or not available."}), 400

    # --- Ejecutar inferencia ---
    try:
        if model.startswith("openai") or os.getenv("OPENAI_API_KEY"):
            openai_client = OpenAI()

            response = openai_client.chat.completions.create(
                model=model.replace("openai/", ""),
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=timeout,
            )

            output = json.loads(response.model_dump_json())["choices"][0]["message"]["content"]

        elif model.startswith("ollama") or os.getenv("OLLAMA_API_URL"):
            ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

            ollama_client = ollama.Client(
                host=ollama_url,
                timeout=timeout,
            )

            response = ollama_client.chat(
                model=model.replace("ollama/", ""),
                options={"temperature": temperature},
                format="json",
                messages=[{"role": "user", "content": prompt}],
            )

            output = response["message"]["content"]

        else:
            return jsonify({"error": "No valid provider configured (OpenAI or Ollama)."}), 500

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": f"Could not run completion against {model or 'default provider'}."}), 500

    # --- Validar formato del output ---
    try:
        output = json.loads(output)
        assert "search_statement" in output
        assert isinstance(output["search_statement"], str) or output["search_statement"] is None
        assert isinstance(output["search_target"], str) or output["search_target"] is None
        assert len(output.keys()) == 2
    except Exception:
        current_app.logger.error("❌ Invalid model output:\n" + str(output))
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": f"{model} returned invalid JSON or missing keys."}), 500

    return jsonify(output), 200
