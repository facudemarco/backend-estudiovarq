"""Aplica al ReplyHandler dos arreglos:
1) 404 de "Read Lead por Telefono" no mata el workflow: onError=continueErrorOutput
   + rama que responde amistosamente al número no registrado y loguea el evento.
2) "Procesar Respuesta Wizard" deja de usar regex: un LLM (OpenRouter) normaliza
   la respuesta libre según la pregunta; fallback a texto crudo si el LLM falla.

Modelo LLM: google/gemma-4-31b-it:free (gratuito, servido por Google AI Studio).
Los :free de OpenRouter tienen rate limits -> retryOnFail 5x5s en el chainLlm.
Idempotente: si los nodos ya existen, actualiza modelo/retries sin duplicarlos.
"""
import json
import os
import requests

N8N_BASE = "https://n8n.iwebtecnology.com/api/v1"
N8N_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
WF_ID = "Pb3sx6n97pbvLDFH"
BACKEND = os.getenv("BACKEND_URL", "https://api-estudiovarq.iwebtecnology.com")
SECRET_CRED = {"id": "lR6ya95Eh7j2TOEZ", "name": "EstudioVARq Secret"}
OPENROUTER_CRED = {"id": "zJwflhAo7Ip9wSMb", "name": "OpenRouter account"}
HTTP_HEADERS = [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "X-Secret", "value": "={{ $credentials.httpHeaderAuth ? $credentials.httpHeaderAuth.value : '' }}"},
]

QUEST_PRE = """const QUEST = [
  null,
  { text: '¿Qué tipo de obra estás buscando?\\n\\n1. Obra nueva\\n2. Reforma\\n3. Ampliación\\n4. Otro (escribilo)' },
  { text: '¿Qué tipo de vivienda estás buscando?\\n\\n1. Departamento\\n2. Casa\\n3. PH\\n4. Otro (escribilo)' },
  { text: '¿Ya tenés el terreno para construir o la casa que quieras remodelar?\\n\\n1. Sí\\n2. No\\n3. Otro (escribilo)' },
  { text: '¿En qué zona se encuentra? Nuestra área de trabajo es CABA y el AMBA.\\n\\nEscribinos la zona 🗺️' },
  { text: '¿Cuántos M2 aproximados es la superficie a intervenir?\\n\\nEscribinos los metros cuadrados 📏' },
  { text: '¿Qué tipo de servicio estás buscando?\\n\\n1. Planos\\n2. Construcción\\n3. Todo\\n4. Otro (escribilo)' },
  { text: '¿En qué creés que podemos ayudarte?\\n\\nEscribinos tu idea ✍️' },
  { text: '¿Cuál es el presupuesto de inversión disponible para afrontar el proyecto?\\n\\n1. 30.000 - 50.000 USD\\n2. 50.000 - 100.000 USD\\n3. Más de 100.000 USD\\n4. Otro (escribilo)' },
  { text: '¿Cuándo quisieras ponerte en marcha para iniciar el proyecto?\\n\\nEscribinos tu fecha estimada 🗓️' },
];
"""

ARMAR_PROMPT_JS = QUEST_PRE + r'''const lead = $json;
const textRaw = String($('Preparar Datos Reply').first().json.text || '');
const q = Number(lead.question_index) || 1;
const pregunta = QUEST[q] ? QUEST[q].text : 'Cuéntanos más';
const prompt = `Normalizá la respuesta de un usuario de WhatsApp a una pregunta de un formulario.\n\nPregunta: ${pregunta}\nRespuesta del usuario: "${textRaw}"\n\nRespondé ÚNICAMENTE con un JSON válido (sin markdown, sin explicaciones) con esta forma: {"answer": "texto normalizado"}\n- Si la respuesta coincide con una opción numerada de la pregunta, "answer" es el texto de esa opción (ej. para "Sii, me interesa" y la opción 1. Sí, answer = "Sí").\n- Si la pregunta pide un número (m2, presupuesto), incluí además "usd": <monto numérico en dólares> (0 si no aplica).\n- Si no coincide con ninguna opción, "answer" es la respuesta del usuario corregida ortográficamente.`;
return [{ json: { prompt, q, phone: lead.phone, name: lead.name, lead } }];'''

PROCESAR_JS = QUEST_PRE + r'''const llmItem = $json;
const lead = $('Armar Prompt Wizard').first().json.lead;
const textRaw = String($('Preparar Datos Reply').first().json.text || '');
const q = Number(lead.question_index) || 1;

let ans = '';
let usd = 0;
let llmOk = false;
if (!llmItem.error && llmItem.output) {
  const raw = String(llmItem.output).trim();
  try {
    const o = JSON.parse(raw);
    ans = String(o.answer ?? '').trim();
    usd = Number(o.usd) || 0;
    llmOk = !!ans;
  } catch (e) {
    ans = raw;
    llmOk = !!ans;
  }
}
if (!llmOk) ans = textRaw;

function parseUsd(t) {
  if (/mas de|más de|100000|100\.000/.test(t) && !/50/.test(t)) return 150000;
  if (/50/.test(t) && /100/.test(t)) return 75000;
  if (/30/.test(t) && /50/.test(t)) return 40000;
  const m = String(t).match(/\d[\d.,]*k?/);
  if (m) return parseFloat(m[0].replace(/,/g, '.').replace('k', '000')) || 0;
  return 0;
}

const next_index = q + 1;
const complete = next_index > 9;
const q_field = 'q' + q;
const presupuesto_usd = q === 8 ? (usd || parseUsd(ans)) : parseUsd(String(lead.q8 || ''));
const ans_update = { [q_field]: String(ans), question_index: next_index };
const sheet_row = Object.assign({}, lead, ans_update);

const out = {
  lead_id: lead.lead_id,
  phone: lead.phone,
  name: lead.name,
  q_field, answer: String(ans),
  sheet_update: ans_update,
  complete,
  next_message: complete ? null : QUEST[next_index].text,
  sheet_row,
  calificacion_sheet_row: null,
};

if (complete) {
  const zona = lead.q4 || '';
  const AMBA = /caba|buenos aires|amba|pilar|la plata|san isidro|vicente lopez|moron|quilmes|avellaneda|lanus|lomas|tigre|san martin|tres de febrero|moreno|merlo|hurlingham|ituzaingo|escobar|malvinas|echeverria|san fernando|san miguel/.test(String(zona).toLowerCase());
  const cualificado = presupuesto_usd >= 30000 && AMBA;
  out.calificacion = {
    cualificado,
    razon_no_cual: !cualificado ? (presupuesto_usd < 30000 ? 'presupuesto menor a 30k USD' : 'fuera de CABA/AMBA') : '',
    etapa_seg: cualificado ? '6h' : 'm1',
    prox_seg_ts: $now.plus(cualificado ? { hours: 6 } : { months: 1 }).toISO(),
    status: cualificado ? 'cualificado' : 'no_cualificado',
    sheet_update: {
      status: cualificado ? 'cualificado' : 'no_cualificado',
      cualificado: cualificado ? 'si' : 'no',
      razon_no_cual: !cualificado ? (presupuesto_usd < 30000 ? 'presupuesto menor a 30k USD' : 'fuera de CABA/AMBA') : '',
      etapa_seg: cualificado ? '6h' : 'm1',
      prox_seg_ts: $now.plus(cualificado ? { hours: 6 } : { months: 1 }).toISO(),
    },
    close_message: cualificado
      ? `¡Perfecto ${lead.name}! 🎉 Con toda esta info, te voy a pasar los próximos pasos para coordinar la llamada con un arquitecto. 📅`
      : `¡Gracias ${lead.name}! 🙌 Quedó registrada tu información. Cualquier cosa, escribinos cuando quieras. ¡Éxitos con tu proyecto!`
  };
  out.calificacion_sheet_row = Object.assign({}, sheet_row, out.calificacion.sheet_update);
}

return [{ json: out }];'''

RESP_404_JS = r'''const phone = $json.phone || $json.error?.phone || '';
const message = 'Hola 👋 Recibimos tu mensaje, pero tu número no está registrado en nuestro sistema. Si completaste el formulario, escribinos desde el número que usaste para registrarte.';
return [{ json: { phone, message } }];'''


def _id(prefix: str) -> str:
    return f"{prefix}-0001-0001-0001-000000000001"


def _code_node(name: str, js: str, position: list) -> dict:
    return {
        "parameters": {"language": "javaScript", "mode": "runOnceForAllItems", "jsCode": js},
        "id": _id("rc-" + name[:8]),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
    }


def _http_node(name: str, method: str, url: str, json_body: str, position: list) -> dict:
    node = {
        "parameters": {
            "method": method,
            "url": url,
            "sendHeaders": True,
            "headerParameters": {"parameters": HTTP_HEADERS},
            "options": {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000},
        },
        "id": _id("rh-" + name[:8]),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": position,
        "credentials": {"httpHeaderAuth": SECRET_CRED},
    }
    if method == "POST":
        node["parameters"]["sendBody"] = True
        node["parameters"]["contentType"] = "json"
        node["parameters"]["specifyBody"] = "json"
        node["parameters"]["jsonBody"] = json_body
    return node


def apply(raw: dict) -> dict:
    wf = json.loads(json.dumps(raw))
    nodes = wf["nodes"]
    names = {n["name"] for n in nodes}

    # --- 1) Fix 404: Read Lead por Telefono con error output ---
    for n in nodes:
        if n["name"] == "Read Lead por Telefono":
            n["onError"] = "continueErrorOutput"

    if "Armar Respuesta Lead No Encontrado" not in names:
        nodes.append(_code_node("Armar Respuesta Lead No Encontrado", RESP_404_JS, [700, 420]))
    if "Enviar Respuesta Lead No Encontrado" not in names:
        nodes.append(_http_node(
            "Enviar Respuesta Lead No Encontrado", "POST", f"{BACKEND}/send",
            "={{ JSON.stringify({ phone: $json.phone, message: $json.message }) }}", [1020, 340]))
    if "Loguear Lead No Encontrado" not in names:
        nodes.append(_http_node(
            "Loguear Lead No Encontrado", "POST", f"{BACKEND}/crm/events",
            "={{ JSON.stringify({ phone: $json.phone, step: 'reply_lead_no_encontrado' }) }}", [1020, 480]))

    # --- 2) Rediseño LLM ---
    if "Armar Prompt Wizard" not in names:
        nodes.append(_code_node("Armar Prompt Wizard", ARMAR_PROMPT_JS, [200, -160]))
    if "OpenRouter Chat Model" not in names:
        nodes.append({
            "parameters": {"model": "google/gemma-4-31b-it:free"},
            "id": _id("rm-" + "OpenRouter".lower()[:8]),
            "name": "OpenRouter Chat Model",
            "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
            "typeVersion": 1,
            "position": [-120, -80],
            "credentials": {"openRouterApi": OPENROUTER_CRED},
        })
    else:
        for n in nodes:
            if n["name"] == "OpenRouter Chat Model":
                n["parameters"] = {"model": "google/gemma-4-31b-it:free"}
    if "LLM Interpretar Respuesta" not in names:
        nodes.append({
            "parameters": {"promptType": "define", "text": "={{ $json.prompt }}"},
            "id": _id("rl-" + "LLMInterp".lower()[:8]),
            "name": "LLM Interpretar Respuesta",
            "type": "@n8n/n8n-nodes-langchain.chainLlm",
            "typeVersion": 1.9,
            "position": [440, -160],
            "onError": "continueErrorOutput",
            "retryOnFail": True,
            "maxTries": 5,
            "waitBetweenTries": 5000,
        })
    else:
        for n in nodes:
            if n["name"] == "LLM Interpretar Respuesta":
                n["onError"] = "continueErrorOutput"
                n["retryOnFail"] = True
                n["maxTries"] = 5
                n["waitBetweenTries"] = 5000

    for n in nodes:
        if n["name"] == "Procesar Respuesta Wizard":
            n["parameters"] = {"language": "javaScript", "mode": "runOnceForAllItems", "jsCode": PROCESAR_JS}

    # --- 3) Conexiones ---
    conn = wf.setdefault("connections", {})

    conn["Read Lead por Telefono"] = {
        "main": [
            [{"node": "IF lead encontrado", "type": "main", "index": 0}],
            [{"node": "Armar Respuesta Lead No Encontrado", "type": "main", "index": 0}],
        ]
    }

    conn["Armar Respuesta Lead No Encontrado"] = {
        "main": [
            [
                {"node": "Enviar Respuesta Lead No Encontrado", "type": "main", "index": 0},
                {"node": "Loguear Lead No Encontrado", "type": "main", "index": 0},
            ]
        ]
    }

    if "IF status wizard" in conn:
        conn["IF status wizard"]["main"] = [
            [{"node": "Armar Prompt Wizard", "type": "main", "index": 0}],
            [{"node": "IF lead cualificado", "type": "main", "index": 0}],
        ]

    conn["Armar Prompt Wizard"] = {
        "main": [[{"node": "LLM Interpretar Respuesta", "type": "main", "index": 0}]]
    }
    conn["OpenRouter Chat Model"] = {
        "ai_languageModel": [[{"node": "LLM Interpretar Respuesta", "type": "ai_languageModel", "index": 0}]]
    }
    conn["LLM Interpretar Respuesta"] = {
        "main": [
            [{"node": "Procesar Respuesta Wizard", "type": "main", "index": 0}],
            [{"node": "Procesar Respuesta Wizard", "type": "main", "index": 0}],
        ]
    }
    return wf


def publish() -> None:
    headers = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}
    raw = requests.get(f"{N8N_BASE}/workflows/{WF_ID}", headers=headers, timeout=30).json()
    new = apply(raw)
    r = requests.put(f"{N8N_BASE}/workflows/{WF_ID}",
                     json={"name": raw.get("name"), "settings": raw.get("settings") or {},
                           "nodes": new["nodes"], "connections": new["connections"]},
                     headers=headers, timeout=30)
    r.raise_for_status()
    print("PUT ok")


if __name__ == "__main__":
    publish()
