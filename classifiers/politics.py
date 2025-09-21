import regex as re
import unicodedata

PARTIES = [
    "ΔΗΣΥ","ΑΚΕΛ","ΔΗΚΟ","ΕΔΕΚ","ΔΗΠΑ","ΕΛΑΜ","Οικολόγοι","Volt","ΑΛΜΑ","Κοινωνική Συμμαχία"
]
ELECTION_TERMS = [
    "εκλογ", "ψηφοδελτ", "υποψ", "προεκλογ", "δημοσκοπ", "κατάλογ", "ανακήρυξ", "έδρα", "περιφέρ",
    "βουλευτ", "ευρωεκλ", "δημοτικές εκλογές", "debate", "exit poll", "ποσοστ", "σταυρός προτιμήσεως"
]

CANDIDATE_HINTS = [
    "Αβέρωφ", "Χριστοδουλίδης", "Μαυρογιάννης", "Νεοφύτου", "Μιχαηλίδης", "Ζαμπάς", "Προδρόμου"
]

def _normalize(text: str) -> str:
    text = unicodedata.normalize('NFD', text.lower())
    return ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')

def is_election_related(text: str, url: str|None=None):
    t = _normalize((text or '') + ' ' + (url or ''))
    score = 0
    labels = []
    for kw in ELECTION_TERMS:
        if re.search(_normalize(kw), t):
            score += 1
    for p in PARTIES:
        if re.search(_normalize(p), t):
            score += 2
            labels.append(p)
    for c in CANDIDATE_HINTS:
        if re.search(_normalize(c), t):
            score += 1
            labels.append(c)
    ok = score >= 2
    return ok, sorted(set(labels))
