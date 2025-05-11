# Autors: Ronalds Turnis
# Programma veic API pieprasījumus izvēlētajam modeļa veidam, lai veiktu derivātu ģenerēšanu ar pamatapmācītu LVM

import os
import csv
import urllib.parse
import requests
import time

### Parametri, kas tiek mainīti atkarībā no vēlamā mērījuma veida
MODEL_TYPE = "o3-2025-04-16" # Modeļa izvēle: "o3-2025-04-16", "gpt-4.1-2025-04-14", "gemini-2.5-flash" vai "claude-3-7-sonnet"
REASONING = False # Parametrs, kas norāda, vai tiek izmantota spriešanas spēja. Strādā tikai "gemini-2.5-flash" un "claude-3-7-sonnet"
ZERO_SHOT = False # Parametrs, kas norāda, vai tiek izpildīts bez-piemēru (True) vai dažu piemēru (False) mācīšanās scenārijs
###

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

# Iespējamie pārveidojumu veidi un tiem atbilstošie pieci piemēri
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

# Uzvednes izveidošana atkarībā no bez-piemēru vai dažu piemēru scenārija
def prompt(lemma, examples, semantic_category_1, semantic_category_2):
    FEW_SHOT_PROMPT = f"Tev ir doti atvasinājumu piemēri {examples}. "
    INITIAL_PROMPT = (
        f"Dotā lemma ir '{lemma}' ar semantisko kategoriju '{semantic_category_1}'. " 
        f"Izveido no šīs lemmas vienu vai vairākus atvasinājumus, kas ir ar semantisko kategoriju '{semantic_category_2}' " 
        "(locījumi nav jāsniedz) latviešu valodā un īsi paskaidro, kādas morfoloģiskās izmaiņas ir nepieciešamas, lai to panāktu. "
        "Atbildē katrai rindai ir jābūt tikai un vienīgi šādā formātā bez jebkāda cita formatējuma: '<Atvasinājums>, <Paskaidrojums>'."
    )
    return INITIAL_PROMPT if ZERO_SHOT else FEW_SHOT_PROMPT+INITIAL_PROMPT

def get_examples(semantic_category_1, semantic_category_2):
    # Atlasām tikai tos pārveidojumus, kas sakrīt ar veicamo
    for cat1, cat2, examples in POSSIBLE_TRANSFORMATIONS:
        if cat1 == semantic_category_1 and cat2 == semantic_category_2:
            return list(examples)
    return []

# Funkcija, kas sadala API atbildi pa rindām, izvadot sarakstu ar pāriem formātā: (kandidāts, paskaidrojums)
def parse_response_lines(response):
    lines = [line.strip() for line in response.splitlines() if line.strip()]

    parsed: list[tuple[str, str]] = []
    for line in lines:
        parts = [part.strip() for part in line.split(",", 1)]
        if len(parts) >= 2:
            parsed.append((parts[0], parts[1]))
        else:
            parsed.append((parts[0], ""))

    return parsed

# Funkcija, kas validē kandidātu, izmantojot korpusa API
def validate_word(word):
    encoded_word = urllib.parse.quote(word)
    url = ("https://nosketch.korpuss.lv/bonito/run.cgi/view?"
           "corpname=CommonCrawl&format=json&pagesize=2&fromp=0&attrs=word&"
           "ctxattrs=word%2Ctag&kwicleftctx=5%23&kwicrightctx=5%23&async=0&"
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

results = []

# Iterē caur katru derivējamo lemmu
for lemma in lemmas:
    word = lemma[0]
    semantic_category_1 = lemma[2]
    semantic_category_2 = lemma[3]
    
    # Izvēlas mērķa semantisko kategoriju un tam atbilstošos piemērus
    examples = get_examples(semantic_category_1, semantic_category_2)

    # Veic izsaukumu modelim atkarībā no izveidotās uzvednes
    print(prompt(word, examples, semantic_category_1, semantic_category_2))
    response = call_model(prompt(word, examples, semantic_category_1, semantic_category_2))
    print("Rezultāts:")
    print(response)
    time.sleep(1)

    # Izveido derīga formāta pārus no atbildēm
    parsed_list = parse_response_lines(response)
       
    # Validē katru kandidātu pret korpusu kolekciju un pievieno rezultātu sarakstam
    for derived_word, explanation in parsed_list:
        typ, freq = validate_word(derived_word)
        results.append({
            "Lemma": word,
            "Semantiskā_kat_1": semantic_category_1,
            "Kandidāts": derived_word,
            "Semantiskā_kat_2": semantic_category_2,
            "Paskaidrojums": explanation,
            "Biežums": freq,
            "Tips": typ,
            "Grupa": lemma[1]
        })

# Saglabā rezultātus TSV failā, kas ir formātā '<metode/modelis_eksperiments>.tsv'
EXPERIMENT = "zero-shot" if ZERO_SHOT else "few-shot"
REASON = "reasoning" if REASONING else "non-reasoning"
MODEL = f"{MODEL_TYPE}_{REASON}" if MODEL_TYPE == "gemini-2.5-flash" or MODEL_TYPE == "claude-3-7-sonnet" else MODEL_TYPE
output_tsv = f"derivation_results/{MODEL}_{EXPERIMENT}.tsv"

with open(output_tsv, "w", newline="", encoding="utf-8-sig") as tsvfile:
    writer = csv.writer(tsvfile, delimiter="\t")
    header = ["Lemma", "Semantiskā_kat_1", "Kandidāts", "Semantiskā_kat_2", "Paskaidrojums", "Biežums", "Tips", "Grupa"]
    writer.writerow(header)
    
    for row in results:
        out_row = [row["Lemma"], row["Semantiskā_kat_1"], row["Kandidāts"], row["Semantiskā_kat_2"], 
                   row["Paskaidrojums"], row["Biežums"], row["Tips"], row["Grupa"]]
        writer.writerow(out_row)

print(f"Rezultāti saglabāti TSV failā: {output_tsv}")
