# Autors: Ronalds Turnis
# Programma sagatavo transformera modeļa apmācības datus, filtrējot korpusa datu kopu

import csv
import string

# Atgriež True, ja līnija satur derīgus datus, izņemot XML birkas un tukšas rindas.
def is_not_token_line(line):
    stripped = line.strip()
    return stripped and not stripped.startswith("<")

 # Atgriež True, ja jebkurā no vārdiem ir vismaz viens alfabēta burts un tā garums ir vismaz 2 simboli, un vārds nesastāv tikai no pieturzīmēm.
def is_valid_word(word):
    if len(word) < 2:
        return False
    if not any(c.isalpha() for c in word):
        return False
    if all(c in string.punctuation for c in word):
        return False
    return True

# Ja ievades datnes līnija satur vismaz trīs daļas, ņem pirmo un pēdējo lauku kā locījumu vai derivātu un lemmu, un ieraksta tos CSV formāta datnē.
def process_file(input_path, output_csv):
    results = []
    with open(input_path, 'r', encoding='utf-8') as fin:
        for line in fin:
            if is_not_token_line(line):
                parts = line.strip().split()
                if len(parts) >= 3:
                    word = parts[0]
                    lemma = parts[-1]
                    if word.lower() != lemma.lower() and is_valid_word(word) and is_valid_word(lemma):
                        results.append((word, lemma))

    # Saglabā rezultātus CSV failā
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Word", "Lemma"])
        writer.writerows(results)
    print(f"Datu attīrīšana pabeigta, rezultāts saglabāts CSV failā: {output_csv}")

if __name__ == '__main__':
    input_file = "LVK2022-t2.2.1.vert"
    output_csv = "LVK2022_filtrets.csv"
    process_file(input_file, output_csv)
