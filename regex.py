# Autors: Ronalds Turnis
# Programma veic API pieprasījumus izvēlētajam modeļa veidam, lai veiktu vispārīgu regulāro izteiksmju ģenerēšanu ar pamatapmācītu LVM

import os
import csv
import urllib.parse
import requests
import re
import time

### Parametri, kas tiek mainīti atkarībā no vēlamā mērījuma veida
MODEL_TYPE = "claude-3-7-sonnet" # Modeļa izvēle: "o3-2025-04-16", "gpt-4.1-2025-04-14", "gemini-2.5-flash" vai "claude-3-7-sonnet"
REASONING = False # Parametrs, kas norāda, vai tiek izmantota spriešanas spēja. Strādā tikai "gemini-2.5-flash" un "claude-3-7-sonnet"
###

REASON = "reasoning" if REASONING else "non-reasoning"
MODEL = f"{MODEL_TYPE}_{REASON}" if MODEL_TYPE == "gemini-2.5-flash" or MODEL_TYPE == "claude-3-7-sonnet" else MODEL_TYPE

if MODEL_TYPE == "o3-2025-04-16" or MODEL_TYPE == "gpt-4.1-2025-04-14":
    from openai import OpenAI

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key is None:
        raise ValueError("Lūdzu uzstādiet OPENAI_API_KEY vides mainīgo!")
    client = OpenAI()

    def call_model(prompt):
        return client.responses.create(model=MODEL_TYPE, input=prompt).output_text

elif MODEL_TYPE == "gemini-2.5-flash":
    from google import genai

    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key is None:
        raise ValueError("Lūdzu uzstādiet GEMINI_API_KEY vides mainīgo!")
    client = genai.Client(api_key=gemini_api_key)
    REASONING_TOKENS = 1024 if REASONING else 0

    def call_model(prompt):
        return client.models.generate_content(
                model='gemini-2.5-flash-preview-04-17',                                 
                contents=prompt, 
                config=genai.types.GenerateContentConfig(thinking_config=genai.types.ThinkingConfig(thinking_budget=REASONING_TOKENS))
               ).text.strip()

elif MODEL_TYPE == "claude-3-7-sonnet":
    import anthropic

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_api_key is None:
        raise ValueError("Lūdzu uzstādiet ANTHROPIC_API_KEY vides mainīgo!")
    client = anthropic.Anthropic()
    thinking = { "type": "enabled", "budget_tokens": 1024 } if REASONING else { "type": "disabled" }

    def call_model(prompt):
        return client.messages.create(
                model="claude-3-7-sonnet-20250219", 
                max_tokens=1536, 
                messages=[{"role": "user", "content": prompt}], 
                thinking=thinking
               ).content[1 if REASONING else 0].text
else:
    raise ValueError("Nepareizs MODEL_TYPE!")

# Vērtēšanas datu kopa formātā <lemma, lemmu grupas apzīmējums, sākotnējā semantiskā kategorija, mērķa semantiskā kategorija>
lemmas = [
    ("veikt", "V", "Darīt", "Rezultāts"),
    ("zvaigzne", "V", "Priekšmets", "Ietver nosaukto"),
    ("pūst", "V", "Būt procesā", "Process"),
    ("riebt", "V", "Būt stāvoklī", "Stāvoklis"),
    ("medicīna", "V", "Abstrakts nojēgums", "Saistīts ar nosaukto"),
    ("skriet", "V", "Darīt", "Darītājs (dzīvs)"),
    ("ideja", "V", "Abstrakts nojēgums", "Saistīts ar nosaukto"),

    ("nest", "I", "Darīt", "Darbība"),
    ("iet", "I", "Būt procesā", "Process"),
    ("ir", "I", "Būt stāvoklī", "Stāvoklis"),

    ("atklusināt", "J", "Darīt", "Instruments"),
    ("sejauts", "J", "Priekšmets", "Ietver nosaukto"),
    ("telpiskot", "J", "Būt procesā", "Process"),
    ("sliecināt", "J", "Būt stāvoklī", "Stāvoklis"),
    ("aizstājeklis", "J", "Abstrakts nojēgums", "Saistīts ar nosaukto"),

    ("tērbstīt", "N", "Darīt", "Vieta (lietv)"),
    ("plakstule", "N", "Priekšmets", "Ietver nosaukto"),
    ("glimžēt", "N", "Būt procesā", "Process"),
    ("skurpelīgs", "N", "Būt stāvoklī", "Stāvoklis"),
    ("zvilgsme", "N", "Abstrakts nojēgums", "Saistīts ar nosaukto")
]

# Iespējamie pārveidojumu veidi un tiem atbilstošie pieci piemēri (tādi paši tiek izmantoti arī regex metodei)
POSSIBLE_TRANSFORMATIONS = [
    ("Darīt", "Darbība", {("aizsargāt", "aizsardzība"),
                          ("brīdināt", "brīdināšana"),
                          ("uzvarēt", "uzvarēšana"),
                          ("draudēt", "draudēšana"),
                          ("uzskatīt", "uzskatīt")}),
       
    ("Darīt", "Rezultāts", {("ierosināt", "ierosme"),
                            ("skolot", "skolojums"),
                            ("maksāt", "maksājums"),
                            ("dziedāt", "dziesma"),
                            ("izpildīt", "izpildījums")}),

    ("Darīt", "Darītājs (dzīvs)", {("tulkot", "tulks"),
                                   ("ārstēt", "ārsts"),
                                   ("maksāt", "maksātājs"),
                                   ("aizliegt", "aizliedzējs"),
                                   ("skriet", "skrējējs")}),

    ("Priekšmets", "Ietver nosaukto", {("mežģīne", "mežģīņots"),
                                       ("mīkla", "mīklains"),
                                       ("zvaigzne", "zvaigžņots"),
                                       ("ķiploks", "ķiplokots"),
                                       ("poga", "pogains")}),

    ("Būt procesā", "Process", {("skriet", "skrējums"),
                                ("aizsākt", "aizsākšana"),
                                ("sākt", "sākšana"),
                                ("iegūt", "iegūšana"),
                                ("identificēt", "identificēšanās")}),

    ("Būt stāvoklī", "Stāvoklis", {("draudēt", "draudi"),
                                   ("vajadzēt", "vajadzēšana"),
                                   ("veikties", "veiksme"),
                                   ("kontrolēt", "kontrole"),
                                   ("pielūgt", "pielūgšana")}),

    ("Abstrakts nojēgums", "Saistīts ar nosaukto", {("statistika", "statistisks"),
                                                    ("ģenētika", "ģenētisks"),
                                                    ("ķīmija", "ķīmisks"),
                                                    ("sabiedrība", "sabiedrisks"),
                                                    ("tehnika", "tehnisks")}),

    ("Darīt", "Vieta (lietvārds)", {("dzīt", "dzītuve"),
                                ("lūgt", "lūgtuve"),
                                ("ražot", "ražotava"),
                                ("ēst", "ēdnīca"),
                                ("dzīvot", "dzīvoklis")}),

    ("Darīt", "Cits", {("vest", "vezums"),
                       ("dziedāt", "dziedāšana"),
                       ("zīst", "zīdeklis"),
                       ("aizsargāt", "aizsardzība"),
                       ("kaitēt", "kaitēklis")}),
                       
    ("Darīt", "Instruments", {("dzirdēt", "dzirdeklis"),
                              ("redzēt", "redzoklis"),
                              ("kliegt", "kliedzamais"),
                              ("miglot", "miglotājs"),
                              ("aizsargāt", "aizsargs")})
]

# Uzvednes izveidošana
def prompt(examples, semantic_category_1, semantic_category_2):
    return (
        f"Doti pāri {examples}, kas veic vārdu atvasināšanu no semantiskās kategorijas {semantic_category_1} "
        f"uz semantisko kategoriju {semantic_category_2}. Iegūsti no šiem pāriem vispārējus latviešu valodas pārveidojumu "
         "likumus un uzraksti pēc iespējas visaptverošākus sed likumus formātā s#^(.*?){vecais}$#\\1{jaunais}#. "
         "Likums drīkst saturēt tieši vienu notveramo grupu (.*?), un aizvietošanas daļā izmanto tikai \\1 + fiksētu sufiksu. " 
         "Nekad neraksti otru \\1 un neievieto SOH simbolu. Atbildē drīkst būt tikai un vienīgi teksta formātā, kur katrs likums "
         "ir atsevišķā rindā. Rinda sākas ar 's#' un beidzas ar '#', bez jebkāda cita teksta vai formatējuma."
    )

# Funkcija, kas sadala API atbildi pa rindām
def parse_response_lines(response):
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    return lines

# Funkcija, kas sadala regulāro izteiksmi divās daļās (pattern un replacement)
def extract_pattern_replacement(rule_str: str):
    rule_str = rule_str.replace("\x01", r"\1")
    m = re.match(r'^s#(.*?)#(.*?)#$', rule_str)
    if not m:
        return None, None
    pattern, repl = m.group(1), m.group(2)
    try:
        re.compile(pattern)
    except re.error:
        return None, None
    return pattern, repl

# Funkcija, kas, ja tas ir iespējams, piemēro regulāro izteiksmi lemmai un iegūst kandidātu
def apply_regex_to_lemma(lemma, rule_str):
    pattern, repl = extract_pattern_replacement(rule_str)
    if not pattern or not re.search(pattern, lemma):
        return ""
    return re.sub(pattern, repl, lemma)

# Funkcija, kas validē kandidātu, izmantojot korpusa API
def validate_word(word):
    encoded_word = urllib.parse.quote(word)
    url = (f"https://nosketch.korpuss.lv/bonito/run.cgi/view?"
           f"corpname=CommonCrawl&format=json&pagesize=2&fromp=0&attrs=word&"
           f"ctxattrs=word%2Ctag&kwicleftctx=5%23&kwicrightctx=5%23&async=0&"
           f"q=q[lc%3D%22{encoded_word}%22+|+lemma_lc%3D%22{encoded_word}%22]")

    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            freq = r.json().get("fullsize", 0)
            if freq == 0:
                typ = "F" # nav sastopams
            elif 1 <= freq <= 5:
                typ = "M" # maz sastopams - nepieciešama manuāla pārbaude
            else:
                typ = "T" # daudz sastopams
            return typ, freq
        return "validation_error", None
    except Exception as e:
        print(f"Validācijas kļūda vārdam '{word}': {e}")
        return "validation_error", None

# Palīgfunkcija pareizam formātam TSV failā
CTRL = {chr(i) for i in range(32)} | {chr(127)}

def safe_rule(rule: str) -> str:
    out = []
    for ch in rule:
        if ch in CTRL:
            out.append(ch.encode('unicode_escape').decode())  # \x01
        else:
            out.append(ch)
    return "".join(out)

results = []

# Iterē caur katru pārveidojuma veidu un tā piemēriem
for semantic_category_1, semantic_category_2, examples in POSSIBLE_TRANSFORMATIONS:
    # Izsauc modeli ar konkrētā pārveidojuma veida piemēriem
    print(prompt(examples, semantic_category_1, semantic_category_2))
    response = call_model(prompt(examples, semantic_category_1, semantic_category_2))
    print("Atbilde:")
    print(response)
    time.sleep(1)
        
    # Izveido sarakstu ar derīga formāta regulārajām izteiksmēm
    rules = parse_response_lines(response)

    # Ieraksta visus ģenerētos likumus failā, kas vēlāk tiek lietoti rezultātiem
    rules_tsv = f"regex_results/{MODEL}_rules.tsv"
    with open(rules_tsv, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter="\t")
        for rule in rules:
            writer.writerow([semantic_category_1, semantic_category_2, safe_rule(rule)])

    # Iterē caur katru vērtēšanas datu kopas elementu
    for lemma in lemmas:
        # Iterē caur katru ģenerēto regulāro izteiksmi
        for rule in rules:
            # Ja lemmai mērķa semantiskā kategorija nesakrīt ar pārveidojuma veidu, izlaižam to
            if semantic_category_1 != lemma[2] and semantic_category_2 != lemma[3]:
                continue

            # Piemēro regulāro izteiksmi
            derived_word = apply_regex_to_lemma(lemma[0], rule)

            # Ja kandidātu nevar iegūt, turpinām ar nākamo vārdu
            if not derived_word:
                continue

            # Kandidāta pārbaude pret korpusu kolekcijas API
            typ, freq = validate_word(derived_word)
            
            # Pievieno rezultātu sarakstam
            results.append({
                "Lemma": lemma[0],
                "Semantiskā_kat_1": lemma[2],
                "Reg. izteiksme": rule,
                "Kandidāts": derived_word,
                "Semantiskā_kat_2": semantic_category_2,
                "Biežums": freq,
                "Tips": typ,
                "Grupa": lemma[1]
            })

# Saglabā rezultātus TSV failā, kas ir formātā '<metode/modelis>.tsv'
output_tsv = f"regex_results/{MODEL}.tsv"

with open(output_tsv, "w", newline="", encoding="utf-8-sig") as tsvfile:
    writer = csv.writer(tsvfile, delimiter="\t")
    writer.writerow(["Lemma", "Semantiskā_kat_1", "Reg. izteiksme", "Kandidāts", "Semantiskā_kat_2", "Biežums", "Tips", "Grupa"])
    for row in results:
        writer.writerow([row["Lemma"], row["Semantiskā_kat_1"], safe_rule(row["Reg. izteiksme"]), row["Kandidāts"],
                        row["Semantiskā_kat_2"], row["Biežums"], row["Tips"], row["Grupa"]])

print(f"Rezultāti saglabāti TSV failā: {output_tsv}")
