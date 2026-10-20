// Model sekcji Ustawienia i wyszukiwarki Ctrl+K okna Retronic (spec 2026-10-19-retronic-okno.md, faza F3).
// Czysta logika bez Quickshella (testy: node --test okno/test/*.test.js). Zapis, walidacja granic, kopia .bak i dziennik "cofnij"
// są w okno_api.py (ustaw / cofnij); tu tylko: polecenia, mapowanie pokrętła na kontrolkę, grupy, filtr, ostrzeżenie o trybie.
//
// Kontrakt (okno_api.py):
//   pokretla --instancja ID   {"pokretla":[{klucz,grupa,typ,min,max,domyslna,biezaca,zmieniona,opis,opcje?}],"grupy":[{nazwa,ile,zmienione}],
//                              "inne_w_pliku":{KLUCZ:wartosc},"ostatnia_zmiana":{czas,po,przed,brak}|null,"blad_pliku","plik"}
//   typ: "przelacznik" (0/1) | "calkowita" | "ulamkowa" | "tekst" (opcje = dozwolone wartości)
//   ustaw --instancja ID KLUCZ=WART ...   {"zmienione":{K:v},"poprzednie":{K:v|null},"bez_zmian":[K]} | {"ok":false,"blad":...}
//   cofnij --instancja ID                 {"przywrocone":{K:v},"usuniete":[K],"cofnieta_zmiana":czas,"pominiete":[...]} | {"ok":false,"blad":...}
//
// Reguła grup: okno bierze grupy z okno_api (jawna tabela prefiks klucza -> grupa, najdłuższy prefiks wygrywa, reszta = Zaawansowane).
// Jedyny dodatek okna: grupa przypięta na górze "Runy (UH)" = klucze UH_* (z "Leczenie i runy"), bo to najczęściej zmieniane pokrętła
// (jaką runę robi postać: UH_CZAR, UH_KLAWISZ, UH_KOSZT, UH_MANA_MIN, UH_AKTYWNY); i grupa "Poza listą" = klucze z na_zywo.json, których
// bot nie zna (tylko odczyt).

var KEY_PATTERN = /^[A-Z][A-Z0-9_]{0,63}$/
var ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,23}$/

var PINNED_GROUP = "Runy (UH)"
var OTHER_GROUP = "Poza listą"
var PINNED_ORDER = ["UH_AKTYWNY", "UH_CZAR", "UH_KLAWISZ", "UH_KOSZT", "UH_MANA_MIN", "UH_MIN_HP", "UH_MOB_DYSTANS"]

// Podpisy wartości, o których wiadomo z repo (tryby.json: `runy` = adori gran, `uh` = adura vita; Karol: adori gran = HMM).
var OPTION_LABELS = { UH_CZAR: { "adori gran": "HMM", "adura vita": "UH" } }

// Klucze zestawu run (wszystkie z grupy "Runy (UH)"): zestaw = te z nich, które tryb z tryby.json ustawia razem z UH_CZAR.
var RUNE_SET_KEYS = ["UH_CZAR", "UH_KLAWISZ", "UH_KOSZT", "UH_MANA_MIN"]

function validId(id) {
  return id === "" || ID_PATTERN.test(String(id))
}

// ---------------------------------------------------------------- tekst: małe litery bez polskich znaków (1:1, długość zachowana)

var FOLD_FROM = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
var FOLD_TO = "acelnoszzacelnoszz"

function fold(text) {
  var s = String(text === undefined || text === null ? "" : text)
  var out = ""
  for (var i = 0; i < s.length; i++) {
    var j = FOLD_FROM.indexOf(s.charAt(i))
    out += j >= 0 ? FOLD_TO.charAt(j) : s.charAt(i)
  }
  return out.toLowerCase()
}

function tokens(query) {
  var q = fold(query).replace(/[_\s]+/g, " ").trim()
  return q === "" ? [] : q.split(" ")
}

// ---------------------------------------------------------------- polecenia (bez powłoki)

function apiCommand(repoDir, args) {
  if (!repoDir) return null
  return ["python3", "-I", repoDir + "/okno_api.py"].concat(args)
}

function pokretlaCommand(repoDir, id) {
  if (!validId(id)) return null
  return apiCommand(repoDir, ["pokretla", "--instancja", String(id)])
}

function cofnijCommand(repoDir, id) {
  if (!validId(id)) return null
  return apiCommand(repoDir, ["cofnij", "--instancja", String(id)])
}

// ---------------------------------------------------------------- liczby i wartości

function roundTo(v, digits) {
  var f = Math.pow(10, digits === undefined ? 4 : digits)
  return Math.round(v * f) / f
}

// Krok suwaka: całkowite 1; ułamkowe zależnie od rozpiętości (0..1,5 -> 0,01; do 25 -> 0,1; więcej -> 1).
function stepFor(p) {
  if (p.typ !== "ulamkowa") return 1
  var span = p.max - p.min
  return span <= 1.5 ? 0.01 : (span <= 25 ? 0.1 : 1)
}

function clamp(p, v) {
  return Math.max(p.min, Math.min(p.max, v))
}

// Wartość przyciągnięta do kroku i zakresu (suwak).
function snap(p, v) {
  var step = stepFor(p)
  var n = Math.round((v - p.min) / step) * step + p.min
  return clamp(p, roundTo(n, 4))
}

function isNumberKnob(p) { return p.typ === "calkowita" || p.typ === "ulamkowa" }

// Rodzaj kontrolki: "przelacznik" | "wybor" | "suwak" | "odczyt" (klucz spoza listy pokręteł: bez edycji).
function controlKind(p) {
  if (p.readonly) return "odczyt"
  if (p.typ === "przelacznik") return "przelacznik"
  if (p.typ === "tekst") return "wybor"
  if (isNumberKnob(p)) return "suwak"
  return "odczyt"
}

function sameValue(a, b) {
  if (typeof a === "boolean") a = a ? 1 : 0
  if (typeof b === "boolean") b = b ? 1 : 0
  if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 1e-9
  return a === b
}

function valueLabel(p, v) {
  var value = v === undefined ? p.biezaca : v
  if (value === null || value === undefined) return "?"
  if (p.typ === "przelacznik") return Number(value) === 1 ? "włączone" : "wyłączone"
  if (typeof value === "number") return String(roundTo(value, 4))
  return String(value)
}

function optionLabel(klucz, opcja) {
  var m = OPTION_LABELS[klucz]
  return m && m[opcja] ? m[opcja] : ""
}

// Pole liczby (wpis z klawiatury) -> {ok, value} | {ok:false, blad}. Granice te same co w bocie; zaplecze sprawdza je jeszcze raz.
function parseInput(p, text) {
  var t = String(text === undefined ? "" : text).trim().replace(",", ".")
  if (!/^-?\d+(\.\d+)?$/.test(t)) return { ok: false, blad: "wpisz liczbę" }
  var n = Number(t)
  if (!isFinite(n)) return { ok: false, blad: "wpisz liczbę" }
  if (p.typ === "calkowita" && Math.floor(n) !== n) return { ok: false, blad: "to pokrętło jest całkowite" }
  if (n < p.min || n > p.max) return { ok: false, blad: "poza zakresem " + p.min + " do " + p.max }
  return { ok: true, value: roundTo(n, 4) }
}

// Argument KLUCZ=WART dla okno_api ustaw. Tekst jako JSON ("adori gran"), liczba ułamkowa zawsze z kropką (typ zostaje float).
// Zwraca null, gdy wartość nie pasuje do pokrętła (zaplecze i tak by ją odrzuciło).
function formatArg(p, value) {
  if (!p || p.readonly || !KEY_PATTERN.test(String(p.klucz))) return null
  if (p.typ === "tekst") {
    if (!p.opcje || p.opcje.indexOf(value) < 0) return null
    return p.klucz + "=" + JSON.stringify(String(value))
  }
  if (typeof value === "boolean") value = value ? 1 : 0
  if (typeof value !== "number" || !isFinite(value)) return null
  if (value < p.min || value > p.max) return null
  if (p.typ === "przelacznik" || p.typ === "calkowita") {
    if (Math.floor(value) !== value) return null
    return p.klucz + "=" + String(value)
  }
  var r = roundTo(value, 4)
  return p.klucz + "=" + (Math.floor(r) === r ? r.toFixed(1) : String(r))
}

// changes: {KLUCZ: wartość}; byKey: {KLUCZ: wpis meta}. Jedno wywołanie = jeden wpis dziennika (jedno "Cofnij").
function ustawCommand(repoDir, id, changes, byKey) {
  if (!validId(id)) return null
  var keys = Object.keys(changes || {})
  if (!keys.length) return null
  var args = ["ustaw", "--instancja", String(id)]
  for (var i = 0; i < keys.length; i++) {
    var a = formatArg(byKey[keys[i]], changes[keys[i]])
    if (a === null) return null
    args.push(a)
  }
  return apiCommand(repoDir, args)
}

// ---------------------------------------------------------------- wpisy, grupy, filtr

// Odpowiedź `pokretla` -> lista wpisów dla widoku: każdy z polem `grupaUI` (grupa w oknie), `readonly`, `indeks` (kolejność).
function allKnobs(data) {
  var out = []
  if (!data) return out
  var list = data.pokretla || []
  for (var i = 0; i < list.length; i++) {
    var p = {}
    for (var k in list[i]) p[k] = list[i][k]
    p.readonly = false
    p.grupaUI = String(p.klucz).indexOf("UH_") === 0 ? PINNED_GROUP : p.grupa
    out.push(p)
  }
  var other = data.inne_w_pliku || {}
  var keys = Object.keys(other).sort()
  for (var j = 0; j < keys.length; j++) {
    out.push({ klucz: keys[j], grupa: OTHER_GROUP, grupaUI: OTHER_GROUP, typ: "odczyt", readonly: true, min: null, max: null,
               domyslna: null, biezaca: other[keys[j]], zmieniona: false,
               opis: "klucz z na_zywo.json spoza listy pokręteł: bot go nie używa, okno tylko go pokazuje" })
  }
  for (var n = 0; n < out.length; n++) out[n].indeks = n
  return out
}

function byKeyMap(knobs) {
  var m = {}
  for (var i = 0; i < knobs.length; i++) m[knobs[i].klucz] = knobs[i]
  return m
}

function isChanged(p) {
  return !p.readonly && p.domyslna !== null && p.domyslna !== undefined && !sameValue(p.biezaca, p.domyslna)
}

function pinnedRank(klucz) {
  var i = PINNED_ORDER.indexOf(klucz)
  return i < 0 ? 999 : i
}

// Grupy do listy po lewej: przypięta "Runy (UH)" pierwsza, potem kolejność z zaplecza, na końcu "Poza listą" (jeśli są takie klucze).
function buildGroups(data, knobs) {
  var order = [PINNED_GROUP]
  var meta = data && data.grupy ? data.grupy : []
  for (var i = 0; i < meta.length; i++) order.push(meta[i].nazwa)
  order.push(OTHER_GROUP)
  var counts = {}
  for (var k = 0; k < knobs.length; k++) {
    var g = knobs[k].grupaUI
    if (!counts[g]) counts[g] = { ile: 0, zmienione: 0 }
    counts[g].ile++
    if (isChanged(knobs[k])) counts[g].zmienione++
  }
  var out = []
  for (var j = 0; j < order.length; j++) {
    var c = counts[order[j]]
    if (c) out.push({ nazwa: order[j], ile: c.ile, zmienione: c.zmienione })
  }
  return out
}

function knobsOfGroup(knobs, group) {
  var out = []
  for (var i = 0; i < knobs.length; i++) if (knobs[i].grupaUI === group) out.push(knobs[i])
  if (group === PINNED_GROUP) {
    out.sort(function (a, b) { return pinnedRank(a.klucz) - pinnedRank(b.klucz) || a.indeks - b.indeks })
  }
  return out
}

// Wynik dopasowania pokrętła do słów zapytania: niższy = lepszy; -1 = brak (każde słowo musi pasować gdzieś).
function matchScore(p, toks) {
  var key = fold(p.klucz)
  var keySpaced = key.replace(/_/g, " ")
  var opis = fold(p.opis)
  var grupa = fold(p.grupaUI) + " " + fold(p.grupa)
  var score = 0
  for (var i = 0; i < toks.length; i++) {
    var t = toks[i]
    if (key.indexOf(t) === 0 || keySpaced.indexOf(t) === 0) score += 0
    else if (key.indexOf(t) >= 0 || keySpaced.indexOf(t) >= 0) score += 1
    else if (opis.indexOf(t) >= 0) score += 2
    else if (grupa.indexOf(t) >= 0) score += 3
    else return -1
  }
  return score
}

// Filtr listy w widoku: opts = {grupa, tekst, tylkoZmienione}. Z tekstem szuka we WSZYSTKICH grupach (wg trafności); bez tekstu bierze grupę.
function filterKnobs(knobs, opts) {
  var toks = tokens(opts.tekst || "")
  var out = []
  if (toks.length) {
    var scored = []
    for (var i = 0; i < knobs.length; i++) {
      var s = matchScore(knobs[i], toks)
      if (s >= 0) scored.push({ p: knobs[i], s: s })
    }
    scored.sort(function (a, b) { return a.s - b.s || a.p.indeks - b.p.indeks })
    for (var j = 0; j < scored.length; j++) out.push(scored[j].p)
  } else {
    out = knobsOfGroup(knobs, opts.grupa)
  }
  if (opts.tylkoZmienione) out = out.filter(isChanged)
  return out
}

function indexOfKey(list, klucz) {
  for (var i = 0; i < list.length; i++) if (list[i].klucz === klucz) return i
  return -1
}

// ---------------------------------------------------------------- Ctrl+K

var PALETTE_LIMIT = 40

// Źródła palety: pokrętła (z wartością), mapy i tryby (Enter = przejście do sekcji Mapa i tryb). mapy = odpowiedź `mapy-tryby` albo null.
function paletteItems(knobs, mapy) {
  var items = []
  for (var i = 0; i < knobs.length; i++) {
    var p = knobs[i]
    items.push({ rodzaj: "pokretlo", klucz: p.klucz, tytul: p.klucz, opis: p.opis || "", grupa: p.grupaUI, p: p, indeks: items.length })
  }
  var maps = mapy && mapy.mapy ? mapy.mapy : []
  for (var m = 0; m < maps.length; m++) {
    items.push({ rodzaj: "mapa", klucz: maps[m].nazwa, tytul: maps[m].nazwa, opis: maps[m].opis || "", grupa: "Mapa i tryb · mapa", p: null, indeks: items.length })
  }
  var modes = mapy && mapy.tryby ? mapy.tryby : []
  for (var t = 0; t < modes.length; t++) {
    items.push({ rodzaj: "tryb", klucz: modes[t].nazwa, tytul: "tryb " + modes[t].nazwa, opis: modes[t].opis || "", grupa: "Mapa i tryb · tryb", p: null, indeks: items.length })
  }
  return items
}

function itemScore(item, toks) {
  var key = fold(item.klucz)
  var title = fold(item.tytul)
  var opis = fold(item.opis)
  var grupa = fold(item.grupa) + (item.p ? " " + fold(item.p.grupa) : "")
  var spaced = key.replace(/_/g, " ")
  var score = 0
  for (var i = 0; i < toks.length; i++) {
    var t = toks[i]
    if (key.indexOf(t) === 0 || spaced.indexOf(t) === 0) score += 0
    else if (key.indexOf(t) >= 0 || spaced.indexOf(t) >= 0 || title.indexOf(t) >= 0) score += 1
    else if (opis.indexOf(t) >= 0) score += 2
    else if (grupa.indexOf(t) >= 0) score += 3
    else return -1
  }
  // pokrętła przed mapami i trybami przy równej trafności
  return score * 3 + (item.rodzaj === "pokretlo" ? 0 : 1)
}

// Wyniki palety. Puste zapytanie = podpowiedź: pokrętła przypiętej grupy Runy (UH). Nazwa, opis i grupa; słowa w dowolnej kolejności.
function searchPalette(items, query, limit) {
  var max = limit || PALETTE_LIMIT
  var toks = tokens(query)
  var out = []
  if (!toks.length) {
    for (var i = 0; i < items.length && out.length < max; i++) {
      if (items[i].rodzaj === "pokretlo" && items[i].grupa === PINNED_GROUP) out.push(items[i])
    }
    out.sort(function (a, b) { return pinnedRank(a.klucz) - pinnedRank(b.klucz) || a.indeks - b.indeks })
    return out
  }
  var scored = []
  for (var j = 0; j < items.length; j++) {
    var s = itemScore(items[j], toks)
    if (s >= 0) scored.push({ it: items[j], s: s })
  }
  scored.sort(function (a, b) { return a.s - b.s || a.it.indeks - b.it.indeks })
  for (var k = 0; k < scored.length && out.length < max; k++) out.push(scored[k].it)
  return out
}

function escapeHtml(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

// Tekst z wyróżnionymi słowami zapytania (StyledText: <font color>). Wyróżnia nakładające się trafienia jednym przebiegiem.
function highlight(text, toks, color) {
  var s = String(text === undefined || text === null ? "" : text)
  if (!toks || !toks.length) return escapeHtml(s)
  var f = fold(s)
  var mark = []
  for (var i = 0; i < s.length; i++) mark.push(false)
  for (var t = 0; t < toks.length; t++) {
    var from = 0
    while (toks[t] !== "" && (from = f.indexOf(toks[t], from)) >= 0) {
      for (var c = from; c < from + toks[t].length; c++) mark[c] = true
      from += toks[t].length
    }
  }
  var out = ""
  var on = false
  for (var j = 0; j < s.length; j++) {
    if (mark[j] && !on) { out += '<font color="' + color + '">'; on = true }
    if (!mark[j] && on) { out += "</font>"; on = false }
    out += escapeHtml(s.charAt(j))
  }
  if (on) out += "</font>"
  return out
}

// ---------------------------------------------------------------- tryb nadpisuje pokrętła przy starcie (uruchom.sh -> tryb.py)

// Pokrętła, które wybrane tryby ustawią przy następnym starcie. Tryby scalane od lewej do prawej (późniejszy wygrywa), jak w tryb.py.
// tryby = lista z `mapy-tryby` ({nazwa, pokretla}); lastModes = nazwy z ostatni_start[.<id>].env. -> {KLUCZ: {tryb, wartosc}}
function modeSettings(tryby, lastModes) {
  var byName = {}
  var list = tryby || []
  for (var i = 0; i < list.length; i++) byName[list[i].nazwa] = list[i]
  var out = {}
  var names = lastModes || []
  for (var j = 0; j < names.length; j++) {
    var t = byName[names[j]]
    if (!t || !t.pokretla) continue
    for (var k in t.pokretla) out[k] = { tryb: t.nazwa, wartosc: t.pokretla[k] }
  }
  return out
}

// Konflikty: pokrętła, którym tryb przy następnym starcie ustawi INNĄ wartość niż bieżąca (zmiana z okna zostanie nadpisana).
function modeConflicts(settings, byKey) {
  var out = []
  var keys = Object.keys(settings || {}).sort()
  for (var i = 0; i < keys.length; i++) {
    var p = byKey[keys[i]]
    if (!p || p.readonly) continue
    if (!sameValue(p.biezaca, settings[keys[i]].wartosc)) {
      out.push({ klucz: keys[i], tryb: settings[keys[i]].tryb, wartosc: settings[keys[i]].wartosc, biezaca: p.biezaca })
    }
  }
  return out
}

function conflictFor(conflicts, klucz) {
  for (var i = 0; i < conflicts.length; i++) if (conflicts[i].klucz === klucz) return conflicts[i]
  return null
}

function conflictText(c, p) {
  return "tryb „" + c.tryb + "” przy następnym starcie ustawi " + c.klucz + " = " + valueLabel(p, c.wartosc) + " (teraz " + valueLabel(p) + ")"
}

// Linia ostrzeżenia nad listą: które tryby z ostatniego startu nadpisują ile pokręteł. "" gdy nic.
function conflictSummary(conflicts, lastModes) {
  if (!conflicts.length) return ""
  var modes = {}
  for (var i = 0; i < conflicts.length; i++) modes[conflicts[i].tryb] = true
  var names = Object.keys(modes)
  var keys = conflicts.slice(0, 4).map(function (c) { return c.klucz }).join(", ")
  var more = conflicts.length > 4 ? " i " + (conflicts.length - 4) + " więcej" : ""
  return "Ostatni start użył trybu " + names.join(", ") + ": przy następnym starcie (uruchom.sh) nadpisze " + conflicts.length + " pokręteł z tej listy ("
         + keys + more + "). Zmiana tutaj działa teraz w locie, ale po restarcie tryb ją przywróci."
}

// ---------------------------------------------------------------- zestawy run (z trybów)

// Tryby z tryby.json, które ustawiają UH_CZAR: gotowy zestaw (czar, hotkey, koszt, mana) do jednego kliknięcia. byKey sprawdza,
// że każda wartość przejdzie walidację pokrętła (inaczej klucz jest pomijany, a zestaw bez UH_CZAR odpada).
function runePresets(tryby, byKey) {
  var out = []
  var list = tryby || []
  for (var i = 0; i < list.length; i++) {
    var pk = list[i].pokretla || {}
    if (pk.UH_CZAR === undefined) continue
    var pary = {}
    for (var k = 0; k < RUNE_SET_KEYS.length; k++) {
      var key = RUNE_SET_KEYS[k]
      if (pk[key] !== undefined && formatArg(byKey[key], pk[key]) !== null) pary[key] = pk[key]
    }
    if (pary.UH_CZAR === undefined) continue
    var parts = [pary.UH_CZAR]
    if (pary.UH_KLAWISZ !== undefined) parts.push(pary.UH_KLAWISZ)
    if (pary.UH_KOSZT !== undefined) parts.push("koszt " + pary.UH_KOSZT)
    if (pary.UH_MANA_MIN !== undefined) parts.push("mana od " + pary.UH_MANA_MIN)
    var name = optionLabel("UH_CZAR", pary.UH_CZAR)
    out.push({ tryb: list[i].nazwa, pary: pary, tytul: (name ? name + " (" + pary.UH_CZAR + ")" : pary.UH_CZAR), opis: parts.join(" · ") })
  }
  return out
}

function presetActive(preset, byKey) {
  var keys = Object.keys(preset.pary)
  for (var i = 0; i < keys.length; i++) {
    var p = byKey[keys[i]]
    if (!p || !sameValue(p.biezaca, preset.pary[keys[i]])) return false
  }
  return true
}

// ---------------------------------------------------------------- wyniki zapisu

// Lokalna poprawka danych po udanym `ustaw` (natychmiastowy obraz; prawdę i tak dociąga kolejny odczyt `pokretla`).
function applyChanges(data, zmienione) {
  if (!data || !data.pokretla) return data
  var copy = {}
  for (var k in data) copy[k] = data[k]
  copy.pokretla = data.pokretla.map(function (p) {
    if (!(p.klucz in zmienione)) return p
    var q = {}
    for (var f in p) q[f] = p[f]
    q.biezaca = zmienione[p.klucz]
    q.zmieniona = !sameValue(q.biezaca, q.domyslna)
    return q
  })
  return copy
}

function shortValue(p, v) {
  if (v === null || v === undefined) return "domyślna"
  return p ? valueLabel(p, v) : String(v)
}

// "UH_CZAR: adura vita → adori gran" (do trzech zmian, reszta jako "+N").
function describeChange(zmienione, poprzednie, byKey) {
  var keys = Object.keys(zmienione || {})
  var parts = []
  for (var i = 0; i < keys.length && i < 3; i++) {
    var p = byKey[keys[i]]
    parts.push(keys[i] + ": " + shortValue(p, (poprzednie || {})[keys[i]]) + " → " + shortValue(p, zmienione[keys[i]]))
  }
  return parts.join(" · ") + (keys.length > 3 ? " · +" + (keys.length - 3) : "")
}

function describeUndo(wynik, byKey) {
  var parts = []
  var rest = wynik.przywrocone || {}
  var keys = Object.keys(rest)
  for (var i = 0; i < keys.length && i < 3; i++) parts.push(keys[i] + " → " + shortValue(byKey[keys[i]], rest[keys[i]]))
  var gone = wynik.usuniete || []
  for (var j = 0; j < gone.length && parts.length < 3; j++) parts.push(gone[j] + " → domyślna")
  var more = keys.length + gone.length - parts.length
  return parts.join(" · ") + (more > 0 ? " · +" + more : "")
}

function timeOf(czas) {
  var c = String(czas || "")
  return c.length >= 19 ? c.substring(11, 16) : c
}

// Podpis przycisku "Cofnij ostatnią": co dokładnie cofnie (z dziennika zaplecza). null = nie ma co cofać.
function undoLabel(ostatnia, byKey) {
  if (!ostatnia || !ostatnia.po) return null
  var keys = Object.keys(ostatnia.po)
  if (!keys.length) return null
  var przed = ostatnia.przed || {}
  var parts = []
  for (var i = 0; i < keys.length && i < 2; i++) {
    parts.push(keys[i] + " " + shortValue(byKey[keys[i]], przed[keys[i]]) + " ← " + shortValue(byKey[keys[i]], ostatnia.po[keys[i]]))
  }
  return parts.join(", ") + (keys.length > 2 ? " +" + (keys.length - 2) : "") + " · " + timeOf(ostatnia.czas)
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    PINNED_GROUP: PINNED_GROUP, OTHER_GROUP: OTHER_GROUP, RUNE_SET_KEYS: RUNE_SET_KEYS,
    validId: validId, fold: fold, tokens: tokens, pokretlaCommand: pokretlaCommand, cofnijCommand: cofnijCommand,
    ustawCommand: ustawCommand, formatArg: formatArg, parseInput: parseInput, stepFor: stepFor, snap: snap, clamp: clamp,
    roundTo: roundTo, controlKind: controlKind, sameValue: sameValue, valueLabel: valueLabel, optionLabel: optionLabel,
    allKnobs: allKnobs, byKeyMap: byKeyMap, isChanged: isChanged, buildGroups: buildGroups, knobsOfGroup: knobsOfGroup,
    matchScore: matchScore, filterKnobs: filterKnobs, indexOfKey: indexOfKey, paletteItems: paletteItems,
    searchPalette: searchPalette, highlight: highlight, modeSettings: modeSettings, modeConflicts: modeConflicts,
    conflictFor: conflictFor, conflictText: conflictText, conflictSummary: conflictSummary, runePresets: runePresets,
    presetActive: presetActive, applyChanges: applyChanges, describeChange: describeChange, describeUndo: describeUndo,
    undoLabel: undoLabel
  }
}
