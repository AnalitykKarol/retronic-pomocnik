// Model statystyk spotkań z graczami (26.10, Karol): dwie linie na karcie postaci (CharCard.qml) i zakładka „Spotkania” (SpotkaniaView.qml).
// Czysta logika bez Quickshella (testy: node --test okno/test/*.test.js). Niczego tu nie liczymy poza prezentacją: licznik n/próg, bywalec, czas na spocie,
// spotkania na godzinę i ostatnio widziany gracz przychodzą z `okno_api.py stan` (pole `spotkania` instancji, tylko z cache, zawsze z bieżącej sesji bota),
// a zmiany spotu i unikane spoty z `okno_api.py spotkania` (spotkania_okno.py).
// Kontrakt `instancja.spotkania`: {dostepne, powod, prog, zrodlo, n, bywalec{nick,n}|null, graczy, spotkan, czas_na_spocie_s, spotkan_na_h|null, ostatni{nick,t}|null, wiek_s}.
// Rozszerzenie 26.10 (Karol): `widziani` (liczba RÓŻNYCH obcych graczy w zasięgu wzroku, >= 1 próbka, od wejścia na obecny spot), `widziani_od` (epoch), `widziani_lista`
// [{nick, probek, pierwszy_t, ostatnio_t}] (najczęściej widziani pierwsi), `widziani_powod` (gdy `widziani` null), `widziani_uwaga`. Stare pola bez zmian; brak pola = „-”.
// Zmiana 26.10 (Karol): `spotkan`, `spotkan_na_h` i `bywalec` to spotkania BEZ minimalnego czasu widoku (1 próbka telemetrii, nowy epizod po 5 min bez gracza). Licznik decyzyjny bota
// (każde spotkanie >= 3 s w widoku, od 27.10; wcześniej 15 s; po `prog` takich nadzorca zmienia spot) to `n`/`prog` oraz `spotkan_prog15` i `bywalec_prog15`; w oknie podpisany „próg”, nigdy „spotkań”.
// Brak danych (bot stoi, inna sesja, jeszcze nie policzone) = „-”, nigdy zera, które udawałyby pomiar.
// `now` we wszystkich funkcjach = Date (odświeżenie stanu), żeby wynik był deterministyczny w testach.

var DASH = "-"
var FALLBACK_PROG = 3

function isNum(v) { return typeof v === "number" && isFinite(v) }
function isList(v) { return v !== null && v !== undefined && typeof v === "object" && typeof v.length === "number" }
function pad2(n) { return (n < 10 ? "0" : "") + n }
function hhmm(date) { return pad2(date.getHours()) + ":" + pad2(date.getMinutes()) }

// Polski zapis dziesiętny z przecinkiem: 0,7 · 12 · 4,8
function decimal(n) {
  if (!isNum(n)) return DASH
  var r = Math.round(n * 10) / 10
  return (r === Math.floor(r) ? String(r) : r.toFixed(1)).replace(".", ",")
}

// "1h 24m", "24m", "<1m"; brak = „-”
function span(sec) {
  if (!isNum(sec) || sec < 0) return DASH
  var m = Math.floor(sec / 60)
  if (m < 1) return "<1m"
  if (m < 60) return m + "m"
  return Math.floor(m / 60) + "h" + (m % 60 > 0 ? " " + (m % 60) + "m" : "")
}

function sectionOf(inst) { return inst && inst.spotkania && typeof inst.spotkania === "object" ? inst.spotkania : null }
function available(inst) { var s = sectionOf(inst); return !!(s && s.dostepne === true) }
function progOf(inst) { var s = sectionOf(inst); return s && isNum(s.prog) && s.prog > 0 ? s.prog : FALLBACK_PROG }

// Licznik osiągnął próg zmiany spotu (n >= próg) -> wyróżnienie kolorem
function isHot(inst) { var s = sectionOf(inst); return !!(s && s.dostepne === true && isNum(s.n) && s.n >= progOf(inst)) }

function regularText(s) {
  return s && s.bywalec && s.bywalec.nick ? s.bywalec.nick + " ×" + s.bywalec.n : ""
}
// Najczęstszy gracz wg licznika bota (>= 3 s w widoku), tylko do porównania
function botRegularText(s) {
  return s && s.bywalec_prog15 && s.bywalec_prog15.nick ? s.bywalec_prog15.nick + " ×" + s.bywalec_prog15.n : ""
}

// Powód braku danych po polsku do podpowiedzi (z API: bot nie działa, dane z innej sesji bota, ...)
function whyText(inst) {
  var s = sectionOf(inst)
  if (!s) return "brak danych o spotkaniach"
  if (s.dostepne === true) return ""
  return s.powod ? String(s.powod) : "brak danych"
}

// Krótki powód braku danych do ostatniej komórki wiersza tabeli (pełny tekst w podpowiedzi i w bloku „Czas i tempo”)
var WHY_SHORT = {
  "bot nie działa": "bot stoi",
  "dane z poprzedniej sesji bota": "inna sesja bota",
  "dane z innej sesji bota": "inna sesja bota",
  "jeszcze nie policzone": "liczę…",
  "instancja główna": "główna",
  "postać stracona": "stracona",
  "dane nieaktualne": "dane nieaktualne",
  "telemetria nieświeża (bot nie pisze)": "brak świeżych danych",
  "brak telemetrii": "brak telemetrii"
}
function whyShort(inst) {
  var w = whyText(inst)
  if (w === "") return ""
  return WHY_SHORT[w] || w
}

// Widziani na obecnym spocie: {ok, count, text, since, names[{nick, probek, last}], tip, why}. `text` = liczba albo „-”; nigdy zera udającego brak pomiaru.
function seenOf(inst) {
  var s = sectionOf(inst)
  var none = { ok: false, count: null, text: DASH, since: "", names: [], tip: "", why: "" }
  if (!s) { none.why = "brak danych o spotkaniach"; return none }
  if (s.dostepne !== true) { none.why = whyText(inst); return none }
  if (!isNum(s.widziani)) { none.why = s.widziani_powod ? String(s.widziani_powod) : "jeszcze nie policzone"; return none }
  var names = []
  var list = isList(s.widziani_lista) ? s.widziani_lista : []
  for (var i = 0; i < list.length; i++) {
    var e = list[i]
    if (!e || !e.nick) continue
    names.push({ nick: String(e.nick), probek: isNum(e.probek) ? e.probek : 0, last: isNum(e.ostatnio_t) ? hhmm(new Date(e.ostatnio_t * 1000)) : "" })
  }
  var since = isNum(s.widziani_od) ? hhmm(new Date(s.widziani_od * 1000)) : ""
  var tip = "Widziani na tym spocie" + (since !== "" ? " od " + since : "") + ": " + s.widziani + " (różni obcy gracze w zasięgu wzroku, choćby na chwilę)"
  if (names.length > 0) {
    var parts = []
    for (var j = 0; j < names.length; j++) parts.push(names[j].nick + (names[j].last !== "" ? " (ostatnio " + names[j].last + ")" : ""))
    tip += "\n" + parts.join(", ") + (s.widziani > names.length ? ", …" : "")
  }
  if (s.widziani_uwaga) tip += "\n" + String(s.widziani_uwaga)
  return { ok: true, count: s.widziani, text: String(s.widziani), since: since, names: names, tip: tip, why: "" }
}

// Linie karty postaci: `👥 spotkań 6 · próg 0/3 · Vados ×6`, `na spocie 1h 24m · 0,7/h` i `👁 widziani 7 · od 10:10`. Karta bez pola `spotkania` (stary stan) = bez linii (shown false).
// „spotkań” = bez minimalnego czasu widoku; „próg n/3” = licznik decyzyjny bota. Brak danych: `👥 spotkań -` i `na spocie - · -/h`. hot = licznik bota >= próg.
// `tip` = podpowiedź karty (powód braku danych albo objaśnienie liczników i widzianych).
function cardLines(inst) {
  var s = sectionOf(inst)
  if (!s) return { shown: false, meet: "", time: "", hot: false, ok: false, why: "", seen: "", seenOk: false, seenTip: "", tip: "" }
  var sn = seenOf(inst)
  var seenLine = "👁 widziani " + sn.text + (sn.ok && sn.since !== "" ? " · od " + sn.since : "")
  if (s.dostepne !== true) {
    var why = whyText(inst)
    return { shown: true, meet: "👥 spotkań " + DASH, time: "na spocie " + DASH + " · " + DASH + "/h", hot: false, ok: false, why: why, seen: seenLine, seenOk: false, seenTip: "",
             tip: "brak danych o spotkaniach: " + why }
  }
  var prog = progOf(inst)
  var n = isNum(s.n) ? s.n : 0
  var reg = regularText(s)
  var bot = botRegularText(s)
  var tip = "Spotkań: " + (isNum(s.spotkan) ? s.spotkan : DASH) + " (gracz w zasięgu wzroku choćby na chwilę; ten sam gracz liczy się znów po 5 minutach bez niego)" +
            "\nPróg " + n + "/" + prog + ": licznik bota, spotkanie liczy się po 3 s w widoku; po " + prog + ". spotkaniu tego samego gracza nadzorca zmienia spot" +
            (bot !== "" ? " (najczęściej: " + bot + ")" : "") +
            "\n" + (sn.ok ? sn.tip : "widziani: " + sn.why)
  return {
    shown: true,
    meet: "👥 spotkań " + (isNum(s.spotkan) ? s.spotkan : DASH) + " · próg " + n + "/" + prog + (reg !== "" ? " · " + reg : ""),
    time: "na spocie " + span(s.czas_na_spocie_s) + " · " + (isNum(s.spotkan_na_h) ? decimal(s.spotkan_na_h) : DASH) + "/h",
    hot: n >= prog, ok: true, why: "", seen: seenLine, seenOk: sn.ok, seenTip: sn.ok ? sn.tip : "widziani: " + sn.why, tip: tip
  }
}

// Blok SPOTKANIA w tabeli Przegląd (26.10): dwie linie jak na karcie postaci, te same helpery. Linia 1: `👥 spotkań 6 · 👁 widziani 2`, linia 2: `próg 0/3 · Vados ×6`.
// Postać poza grą, Karol gra bez bota albo brak sekcji: „—” z podpowiedzią „brak sesji bota” (nie zgadujemy liczb); inny powód braku danych (np. „jeszcze nie policzone”) idzie do podpowiedzi.
// -> {ok, line1, line2, tip, hot}. `inGame` z wiersza Przeglądu (false = offline).
function przegladCell(inst, inGame) {
  var none = function (tip) { return { ok: false, line1: "—", line2: "", tip: tip, hot: false } }
  if (inGame === false) return none("brak sesji bota")
  var s = sectionOf(inst)
  if (!s) return none("brak danych o spotkaniach")
  if (s.dostepne !== true) {
    var why = whyText(inst)
    return none(why === "bot nie działa" ? "brak sesji bota" : "brak danych o spotkaniach: " + why)
  }
  var l = cardLines(inst)
  var sn = seenOf(inst)
  var reg = regularText(s)
  return {
    ok: true,
    line1: "👥 spotkań " + (isNum(s.spotkan) ? s.spotkan : DASH) + " · 👁 widziani " + sn.text,
    line2: "próg " + (isNum(s.n) ? s.n : 0) + "/" + progOf(inst) + (reg !== "" ? " · " + reg : ""),
    tip: l.tip, hot: l.hot
  }
}

// ---------------------------------------------------------------- zakładka: tabela per postać

// jak Model.nickOf / Prz.rowOf: nick z procesu bota albo logu klienta, inaczej id instancji
function nickOf(inst) {
  if (!inst) return ""
  return inst.nick ? String(inst.nick) : (inst.id === "" ? "główna" : String(inst.id))
}

function stateText(inst) {
  var p = inst && inst.przeglad
  if (p && p.stan === "bot_dziala") return "bot działa"
  if (p && p.stan === "alarm") return "alarm"
  return "bot stoi"
}

// Jeden wiersz tabeli: POSTAĆ · NA SPOCIE · GRACZY · WIDZIANI · SPOTKAŃ · PRÓG BOTA n/próg · /H · BYWALEC. Brak danych = „-” w każdej komórce, powód w `why`.
function rowOf(inst) {
  var s = sectionOf(inst)
  var ok = available(inst)
  var prog = progOf(inst)
  return {
    id: inst.id, nick: nickOf(inst), idLabel: inst.id === "" ? "główna" : inst.id,
    ok: ok, hot: isHot(inst), why: whyText(inst), whyShort: whyShort(inst), state: stateText(inst), source: ok ? (s.zrodlo || "") : "",
    onSpot: ok ? span(s.czas_na_spocie_s) : DASH,
    players: ok && isNum(s.graczy) ? String(s.graczy) : DASH,
    seen: seenOf(inst).text, seenTip: seenOf(inst).ok ? seenOf(inst).tip : "",
    meet: ok ? (isNum(s.n) ? s.n : 0) + "/" + prog : DASH,
    meetings: ok && isNum(s.spotkan) ? s.spotkan : null,
    spots: ok && isNum(s.spotkan) ? String(s.spotkan) : DASH,
    botRegular: ok && botRegularText(s) !== "" ? botRegularText(s) : DASH,
    perHour: ok && isNum(s.spotkan_na_h) ? decimal(s.spotkan_na_h) : DASH,
    regular: ok && regularText(s) !== "" ? regularText(s) : DASH
  }
}

// Wiersze w kolejności listy `instances` (Backend.visibleInstances: stracone ukryte jak w reszcie okna, sortowanie jak w Przeglądzie).
function rowsOf(instances) {
  var out = []
  for (var i = 0; i < (instances || []).length; i++) out.push(rowOf(instances[i]))
  return out
}

// Podsumowanie nad tabelą: ile postaci ma dane i ile z nich osiągnęło próg
function summaryOf(instances) {
  var withData = 0
  var hot = 0
  for (var i = 0; i < (instances || []).length; i++) {
    if (available(instances[i])) withData++
    if (isHot(instances[i])) hot++
  }
  return { total: (instances || []).length, withData: withData, hot: hot }
}

// ---------------------------------------------------------------- czas i tempo wybranej postaci

function tempoOf(inst) {
  var s = sectionOf(inst)
  var ok = available(inst)
  var p = inst && inst.przeglad
  var live = !!(p && (p.stan === "bot_dziala" || p.stan === "alarm"))
  var expH = live && p && isNum(p.exp_h) ? p.exp_h : null
  var zabH = live && p && isNum(p.zab_h) ? p.zab_h : null
  return {
    ok: ok, nick: nickOf(inst),
    onSpot: ok ? span(s.czas_na_spocie_s) : DASH,
    perHour: ok && isNum(s.spotkan_na_h) ? decimal(s.spotkan_na_h) : DASH,
    perHourNote: ok && !isNum(s.spotkan_na_h) ? "po 10 minutach na spocie" : "",
    seen: seenOf(inst).text, seenSince: seenOf(inst).since ? "od " + seenOf(inst).since : "", seenWhy: ok && !seenOf(inst).ok ? seenOf(inst).why : "",
    seenNames: seenOf(inst).names.map(function (x) { return x.nick + (x.last !== "" ? " · " + x.last : "") }),
    expH: expH === null ? DASH : String(Math.round(expH)).replace(/\B(?=(\d{3})+(?!\d))/g, " "),
    zabH: zabH === null ? DASH : decimal(zabH),
    why: whyText(inst)
  }
}

// ---------------------------------------------------------------- ostatnio widziany gracz (najświeższy z postaci z danymi)

function lastSeen(instances, now) {
  var best = null
  for (var i = 0; i < (instances || []).length; i++) {
    var inst = instances[i]
    var s = sectionOf(inst)
    if (!available(inst) || !s.ostatni || !isNum(s.ostatni.t) || !s.ostatni.nick) continue
    if (best === null || s.ostatni.t > best.t) best = { nick: String(s.ostatni.nick), t: s.ostatni.t, postac: nickOf(inst) }
  }
  if (best === null) return null
  var d = new Date(best.t * 1000)
  return { nick: best.nick, postac: best.postac, time: hhmm(d), text: best.nick + " · " + hhmm(d) + " · " + best.postac }
}

// ---------------------------------------------------------------- zmiany spotu dziś i unikane spoty (z polecenia `spotkania`)

var STATUS = {
  wykonano: { text: "wykonano", tone: "ok" },
  cien: { text: "tylko zapis", tone: "dim" },
  blad: { text: "błąd", tone: "bad" },
  info: { text: "zostaje", tone: "dim" }
}

function idSet(instances) {
  var set = {}
  for (var i = 0; i < (instances || []).length; i++) set[instances[i].id] = true
  return set
}

// Wiersze „Zmiany spotu”: tylko postacie widoczne w oknie (stracone ukryte). Trasa „z → na”; powrót do miasta nie ma spotu docelowego.
function changeRows(data, instances) {
  var vis = idSet(instances)
  var list = data && isList(data.zmiany) ? data.zmiany : []
  var out = []
  for (var i = 0; i < list.length; i++) {
    var z = list[i]
    if (!z || !vis[z.id]) continue
    var st = STATUS[z.status] || STATUS.info
    var route
    if (z.typ === "powrot") route = (z.z || DASH) + " → miasto"
    else if (z.typ === "brak") route = (z.z || DASH) + " (zostaje)"
    else route = (z.z || DASH) + " → " + (z.na || DASH)
    out.push({
      time: isNum(z.t) ? hhmm(new Date(z.t * 1000)) : DASH, nick: String(z.postac || z.id), route: route, reason: String(z.powod || ""),
      status: st.text, tone: st.tone, repeat: isNum(z.powt) && z.powt > 1 ? z.powt : 1, type: z.typ
    })
  }
  return out
}

// Czas do końca unikania: „2h 10m”, „45m”, „<1m”
function leftText(sec) { return span(sec) }

function avoidRows(data, instances) {
  var vis = idSet(instances)
  var list = data && isList(data.unikane) ? data.unikane : []
  var out = []
  for (var i = 0; i < list.length; i++) {
    var u = list[i]
    if (!u || !vis[u.id] || !isNum(u.zostalo_s) || u.zostalo_s <= 0) continue
    out.push({ nick: String(u.postac || u.id), spot: String(u.jaskinia || u.mapa), map: String(u.mapa || ""), player: String(u.nick || ""), left: leftText(u.zostalo_s), leftSec: u.zostalo_s })
  }
  return out
}

// Podtytuł zakładki: próg z API (SPOTKAN_MAX bota), nie na sztywno
function subtitleOf(data) {
  var prog = data && isNum(data.prog) ? data.prog : FALLBACK_PROG
  return "gracze na spocie od ostatniego startu bota (spotkanie = choćby na chwilę) · po " + prog + ". spotkaniu tego samego gracza (>= 3 s w widoku) nadzorca zmienia spot"
}

// Stopka z ograniczeniami (z API; gdy brak odpowiedzi, stały zapis)
function limitsOf(data) {
  return data && isList(data.granice) && data.granice.length ? Array.prototype.slice.call(data.granice) : [
    "Spotkania liczone od ostatniego startu bota, tylko na spocie; spotkanie = gracz w zasięgu wzroku choćby na chwilę.",
    "„Próg bota” to licznik decyzyjny bota (>= 3 s w widoku), dlatego bywa mniejszy niż „spotkań”."
  ]
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    DASH: DASH, WHY_SHORT: WHY_SHORT, whyShort: whyShort, decimal: decimal, span: span, sectionOf: sectionOf, available: available, progOf: progOf, isHot: isHot, whyText: whyText, seenOf: seenOf,
    cardLines: cardLines, botRegularText: botRegularText, przegladCell: przegladCell, rowOf: rowOf, rowsOf: rowsOf, summaryOf: summaryOf, tempoOf: tempoOf, lastSeen: lastSeen,
    changeRows: changeRows, avoidRows: avoidRows, subtitleOf: subtitleOf, limitsOf: limitsOf, leftText: leftText, STATUS: STATUS
  }
}
