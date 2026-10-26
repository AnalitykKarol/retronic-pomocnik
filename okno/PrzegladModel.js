// Model widoku Przegląd, kart offline i bloku „Ostatnio znane” okna Retronic (spec wtyczka-paska/specs/2026-10-22-retronic-przeglad.md, F2).
// Czysta logika bez Quickshella (testy: node --test okno/test/*.test.js). Plik osobny od RetronicModel.js celowo: tamten jest wspólny
// z paskiem (symlink do wtyczka-paska/), a Przegląd jest tylko w oknie.
//
// Kontrakt (okno_api.py stan, ZAMROŻONY w F1): każda instancja ma `przeglad` (stan, w_grze, test, zab_h, exp_h, dane_wiek_s, na_spocie_od,
// ostatni_alarm, alarm_24h, koniec_sesji, nadzor{aktywny,powod,do,zrodlo}, stop{auto,reczny}) i `ostatnie` (null albo obiekt `ostatnie.KLUCZE`,
// pola nieznane = null; u bota po restarcie jeszcze nie zapisanego całość null). Niczego tu nie liczymy poza prezentacją: stany i nadzór są z API.
// `now` we wszystkich funkcjach = Date (odświeżenie stanu), żeby wynik był deterministyczny w testach.

var STAN_ORDER = { alarm: 0, bot_dziala: 1, karol_gra: 2, zatrzymany: 3, zawieszony: 4, offline: 5 }
var STAN_PILL = {
  bot_dziala: { label: "bot działa", tone: "ok" },
  karol_gra: { label: "Karol gra", tone: "cyan" },
  zatrzymany: { label: "zatrzymany", tone: "warn" },
  alarm: { label: "alarm", tone: "bad" },
  zawieszony: { label: "zawieszony", tone: "mag" },
  offline: { label: "offline", tone: "dim" }
}
// stan -> ton kropki (zasada specu: „Karol gra” nigdy czerwony ani bursztynowy); offline i zawieszony na karcie = szara kropka jak dziś
var STAN_DOT = { bot_dziala: "ok", karol_gra: "cyan", zatrzymany: "warn", alarm: "bad", zawieszony: "dim2", offline: "dim2" }
var MISSING = "—"
var APPROX = "~"                // przedrostek wartości przybliżonych (ostatnie.przyblizone, np. max_hp z backfillu)
var CITY_LABEL = { thais: "Thais", edron: "Edron", rook: "Rookgaard", kazordoon: "Kazordoon", carlin: "Carlin", venore: "Venore" }
var SOURCE_LABEL = {
  bot: "telemetrię bota", logowanie: "logowanie", stop: "zapis STOP", backfill: "uzupełnienie z telemetrii (backfill)", reczny: "ręczny wpis"
}
var END_LABEL = {
  alarm_stop: { text: "ALARM → STOP", tone: "bad" },
  wylogowanie: { text: "wylogowanie", tone: "fg2" },
  znikniecie: { text: "bot zniknął bez zapisu końca", tone: "dim" }
}

function pad2(n) { return (n < 10 ? "0" : "") + n }
function isNum(v) { return typeof v === "number" && isFinite(v) }
function isList(v) { return v !== null && v !== undefined && typeof v === "object" && typeof v.length === "number" }

function plural(n, one, few, many) {
  if (n === 1) return one
  var last = n % 10
  var lastTwo = n % 100
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return few
  return many
}

// ---------------------------------------------------------------- czas

function hhmm(date) { return pad2(date.getHours()) + ":" + pad2(date.getMinutes()) }
function ddmm(date) { return pad2(date.getDate()) + "." + pad2(date.getMonth() + 1) }

function dayStart(date) { return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() }

// "20:14" (dziś), "wczoraj 20:14", "20.10 20:14" (starsze); null/niepoprawne = "—".
function whenLabel(epochS, now) {
  if (!isNum(epochS)) return MISSING
  var d = new Date(epochS * 1000)
  var diffDays = Math.round((dayStart(now) - dayStart(d)) / 86400000)
  if (diffDays === 0) return hhmm(d)
  if (diffDays === 1) return "wczoraj " + hhmm(d)
  return ddmm(d) + " " + hhmm(d)
}

// "38 min", "1 h 12 min"; poniżej minuty "<1 min"
function spanLabel(sec) {
  if (!isNum(sec) || sec < 0) return MISSING
  var m = Math.floor(sec / 60)
  if (m < 1) return "<1 min"
  if (m < 60) return m + " min"
  var h = Math.floor(m / 60)
  return h + " h" + (m % 60 > 0 ? " " + (m % 60) + " min" : "")
}

// "(21.10, 23 h temu)": data i wiek (minuty, godziny, dni)
function agoLabel(epochS, now) {
  if (!isNum(epochS)) return ""
  var d = new Date(epochS * 1000)
  var sec = Math.max(0, (now.getTime() - d.getTime()) / 1000)
  var age = sec < 3600 ? Math.floor(sec / 60) + " min" : (sec < 48 * 3600 ? Math.floor(sec / 3600) + " h" : Math.floor(sec / 86400) + " dni")
  return "(" + ddmm(d) + ", " + age + " temu)"
}

// "2026-10-24 08:30" (nadzor_do z profilu) -> "24.10 08:30"
function doLabel(text) {
  var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(text || ""))
  return m ? m[3] + "." + m[2] + " " + m[4] + ":" + m[5] : String(text || "")
}

function doShort(text) {
  var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(text || ""))
  return m ? m[3] + "." + m[2] : String(text || "")
}

// ---------------------------------------------------------------- pola instancji

function przegladOf(inst) { return inst && inst.przeglad && typeof inst.przeglad === "object" ? inst.przeglad : null }
function ostatnieOf(inst) { return inst && inst.ostatnie && typeof inst.ostatnie === "object" ? inst.ostatnie : null }

function stanOf(inst) {
  var p = przegladOf(inst)
  return p && STAN_ORDER[p.stan] !== undefined ? p.stan : "offline"
}

function isTest(inst) { var p = przegladOf(inst); return !!(p && p.test === true) }
function inGame(inst) { var p = przegladOf(inst); return !!(p && p.w_grze === true) }

// Stany z profilu (Karol 24.10), osobne od stanu z API; pierwszeństwo: stracona > bank > rezerwa. Żaden z nich nie jest „zawieszony do …”.
//  stracona = postać stracona (profil.json `stracony`, np. Dawajkesh i Invincible 24.10): nie wraca do puli, stan ostateczny, także gdy klient wciąż stoi na ekranie logowania
//  bank     = postać-bank (profil.json `rola: "bank"`, np. Kutangen: trzyma złoto, nie expi); pigułka „bank” tylko poza grą, w grze zostaje żywy stan
//  rezerwa  = poza nadzorem z profilu bez terminu, bez roli i bez `stracony`
function isLost(inst) { var p = przegladOf(inst); return !!(p && p.stracony === true) }

function isBank(inst) { var p = przegladOf(inst); return !!(p && p.rola === "bank" && !isLost(inst)) }

function isReserve(inst) {
  var p = przegladOf(inst)
  return !!(p && p.stan === "zawieszony" && !(p.nadzor && p.nadzor.do) && !isLost(inst) && !isBank(inst))
}

// stracona w grze (klient na ekranie logowania) to dla Przeglądu postać poza grą: bez pasków HP/MP, nie „Karol gra”, nie w „W GRZE”
function isOffline(inst) { return !inGame(inst) || isLost(inst) }

function stanDotTone(inst) { return isLost(inst) ? STAN_DOT.offline : STAN_DOT[stanOf(inst)] }

function pillOf(inst) {
  var stan = stanOf(inst)
  if (isLost(inst)) return { label: "stracona", tone: "bad" }
  if (isBank(inst) && !inGame(inst)) return { label: "bank", tone: "blue" }
  if (isReserve(inst)) return { label: "rezerwa", tone: "dim" }
  return STAN_PILL[stan]
}

function poz3(inst) {
  var o = ostatnieOf(inst)
  var live = inst && inst.panel && isList(inst.panel.pozycja) ? inst.panel.pozycja : null
  var p = inGame(inst) && live ? live : (o && isList(o.poz) ? o.poz : null)
  return p && p.length >= 3 ? [p[0], p[1], p[2]] : null
}

function floorLabel(inst) {
  var p = poz3(inst)
  if (p) return "z" + p[2]
  var o = ostatnieOf(inst)
  return o && isNum(o.pietro) ? "z" + o.pietro : ""
}

function cityName(name) {
  var k = String(name || "")
  return CITY_LABEL[k.toLowerCase()] || (k ? k.charAt(0).toUpperCase() + k.substring(1) : "")
}

// Miasto/depo: z panelu (na żywo, gdy w grze) albo z ostatnie (offline). {city, depo}
function cityOf(inst) {
  var o = ostatnieOf(inst)
  if (inGame(inst) && inst.panel && typeof inst.panel === "object") return { city: inst.panel.w_miescie || null, depo: inst.panel.w_depo === true }
  return o ? { city: o.miasto || null, depo: o.w_depo === true } : { city: null, depo: false }
}

// "32368, 32239, z8" | "Edron · depo z8" | "—"
function whereLabel(inst) {
  var c = cityOf(inst)
  var p = poz3(inst)
  var fl = floorLabel(inst)
  if (c.city) return cityName(c.city) + (c.depo ? " · depo" + (fl ? " " + fl : "") : (p ? " · " + p[0] + ", " + p[1] + ", " + fl : ""))
  if (p) return p[0] + ", " + p[1] + ", " + fl
  return MISSING
}

function spotOf(inst) {
  var o = ostatnieOf(inst)
  return inst && inst.mapa ? String(inst.mapa) : (o && o.mapa ? String(o.mapa) : "")
}

function modeOf(inst) {
  var o = ostatnieOf(inst)
  var t = inst && isList(inst.tryb) && inst.tryb.length ? inst.tryb : (o && isList(o.tryb) ? o.tryb : [])
  var out = []
  for (var i = 0; i < t.length; i++) out.push(t[i])
  return out.join(", ")
}

function levelOf(inst) {
  var o = ostatnieOf(inst)
  var live = inGame(inst) && inst.gracz && isNum(inst.gracz.level) ? inst.gracz : null
  if (live) return { level: Math.floor(live.level), pct: isNum(live.level_procent) ? Math.round(live.level_procent) : null }
  if (inGame(inst) && isNum(inst.level)) return { level: Math.floor(inst.level), pct: isNum(inst.level_procent) ? Math.round(inst.level_procent) : null }
  if (o && isNum(o.level)) return { level: Math.floor(o.level), pct: isNum(o.level_proc) ? Math.round(o.level_proc) : null }
  return { level: null, pct: null }
}

// „lvl 10” na karcie postaci (online z gracza, offline z ostatnie); brak = ""
function levelText(inst) {
  var lv = levelOf(inst)
  return lv.level === null || lv.level < 1 ? "" : "lvl " + lv.level
}

function mlLabel(inst) {
  var o = ostatnieOf(inst)
  return o && isNum(o.ml) ? String(o.ml) : "?"
}

// Procent do następnego ML (jak levelOf.pct): tylko odczyt z pamięci gry (ml_zrodlo "pamiec") i ml_proc 0..100; inaczej null.
function mlPctOf(inst) {
  var o = ostatnieOf(inst)
  return o && isNum(o.ml) && o.ml_zrodlo === "pamiec" && isNum(o.ml_proc) && o.ml_proc >= 0 && o.ml_proc <= 100 ? Math.round(o.ml_proc) : null
}

function approx(o, field) { return !!(o && isList(o.przyblizone) && Array.prototype.indexOf.call(o.przyblizone, field) >= 0) }

// Pasek zasobu (HP/MP): na żywo (bieżące/max, ułamek) albo offline „max N” (bez paska).
function resource(inst, curKey, maxKey) {
  var o = ostatnieOf(inst)
  var g = inst && inst.gracz
  if (inGame(inst) && g && isNum(g[curKey]) && isNum(g[maxKey]) && g[maxKey] > 0) {
    return { live: true, cur: g[curKey], max: g[maxKey], frac: Math.max(0, Math.min(1, g[curKey] / g[maxKey])), text: "", approx: false }
  }
  if (!inGame(inst) && o && isNum(o[maxKey])) {
    var ap = approx(o, maxKey)
    return { live: false, cur: null, max: o[maxKey], frac: 0, text: "max " + (ap ? APPROX : "") + o[maxKey], approx: ap }
  }
  return { live: false, cur: null, max: null, frac: 0, text: MISSING, approx: false }
}

function numOrDash(v) { return isNum(v) ? String(Math.round(v)) : MISSING }

function groupDigits(n) {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ")
}

// Blanki i gotowe runy z otwartych kontenerów (okno_api `runy`, odczyt pamięci przez gniazdo bota; 25.10). Brak odczytu = "—".
function runyText(inst) {
  var r = inst && inst.runy
  if (!r || typeof r !== "object" || !isNum(r.blanki)) return ""
  var out = ["bl " + r.blanki]
  var ks = Object.keys(r.runy || {}).sort()
  for (var i = 0; i < ks.length; i++) out.push(ks[i] + " " + r.runy[ks[i]])
  return out.join(" · ")
}
function runyLow(inst) { var r = inst && inst.runy; return !!(r && isNum(r.blanki) && r.blanki < 5) }

// Liczba spotkań z graczami (okno_api `spotkania`, ta sama sekcja co karta) albo null, gdy brak danych (bot stoi, inna sesja, jeszcze nie policzone)
function spotkanKey(inst) {
  var s = inst && inst.spotkania
  return s && typeof s === "object" && s.dostepne === true && isNum(s.spotkan) ? s.spotkan : null
}

function expH(inst) { var p = przegladOf(inst); return p && isNum(p.exp_h) ? p.exp_h : null }
function zabH(inst) { var p = przegladOf(inst); return p && isNum(p.zab_h) ? p.zab_h : null }

// Tempo bieżącej sesji bota jednej postaci (widok Sesja gry, blok na górze): te same expH/zabH co kolumny Przeglądu, ta sama zasada „poza grą = brak”
// (offline, zawieszona, Karol nie gra botem bez telemetrii: null). Tekst: groupDigits (jak kafelek „Exp/h razem”), brak = „—”. Niczego nie liczymy.
function sessionRate(inst) {
  var e = inGame(inst) ? expH(inst) : null
  var z = inGame(inst) ? zabH(inst) : null
  return {
    expH: e, zabH: z,
    expText: e === null ? MISSING : groupDigits(e),
    zabText: z === null ? MISSING : groupDigits(z)
  }
}

// „Ostatnio online”: w_grze_t (ostatnia chwila w grze), potem dane_t (ostatnie dane z gry), na końcu zapisano.
function lastDataT(inst) {
  var o = ostatnieOf(inst)
  if (!o) return null
  if (isNum(o.w_grze_t)) return o.w_grze_t
  if (isNum(o.dane_t)) return o.dane_t
  return isNum(o.zapisano) ? o.zapisano : null
}

// Kiedy bot/gra weszły w stan „stoi”: czas pliku STOP z ostatnie (jeśli jest)
function stopT(inst) {
  var o = ostatnieOf(inst)
  return o && o.stop && isNum(o.stop.t) ? o.stop.t : null
}

function sinceText(inst, now) {
  var p = przegladOf(inst)
  var stan = stanOf(inst)
  var o = ostatnieOf(inst)
  if (isLost(inst)) return ""
  if (stan === "bot_dziala" || stan === "alarm") {
    if (o && o.sesja && isNum(o.sesja.start) && o.sesja.koniec === null && p && isNum(p.dane_wiek_s) && p.dane_wiek_s <= 300) {
      return spanLabel((now.getTime() / 1000) - o.sesja.start)
    }
    return ""
  }
  if (stan === "karol_gra" || stan === "zatrzymany") {
    var t = stopT(inst)
    return t === null ? "" : "od " + whenLabel(t, now)
  }
  if (stan === "zawieszony" && p && p.nadzor && p.nadzor.do) return "do " + doLabel(p.nadzor.do)
  return ""
}

// Kolumna „NA SPOCIE / OSTATNI”: {pre, main, post} (pre przygaszone, main wyraźne, post przygaszone)
function spotTimeOf(inst, now) {
  var p = przegladOf(inst)
  var stan = isLost(inst) ? "offline" : stanOf(inst)
  if (stan === "bot_dziala" || stan === "alarm") {
    if (p && isNum(p.na_spocie_od)) {
      var from = new Date(p.na_spocie_od * 1000)
      return { pre: "od", main: hhmm(from), post: "(" + spanLabel((now.getTime() / 1000) - p.na_spocie_od) + ")" }
    }
    return { pre: "", main: MISSING, post: "", dim: true }
  }
  if (stan === "karol_gra" || stan === "zatrzymany") {
    var t = stopT(inst)
    return t === null ? { pre: "bot stoi", main: "", post: "" } : { pre: "bot stoi od", main: whenLabel(t, now), post: "" }
  }
  var last = lastDataT(inst)
  return last === null ? { pre: "", main: MISSING, post: "", dim: true } : { pre: "ostatnio", main: whenLabel(last, now), post: "" }
}

function stripAlarm(text) { return String(text || "").replace(/^ALARM:\s*/i, "") }

// Ostatni alarm: {time, text, tone} albo null. Ton: bad, gdy stan alarm albo alarm młodszy niż 24 h; starszy przygaszony.
function alarmOf(inst, now) {
  var p = przegladOf(inst)
  if (!p || !p.ostatni_alarm || typeof p.ostatni_alarm !== "object") return null
  var a = p.ostatni_alarm
  var fresh = p.stan === "alarm" || p.alarm_24h === true
  return { time: whenLabel(a.t, now), text: stripAlarm(a.tekst) || String(a.kod || ""), tone: fresh ? "bad" : "dim" }
}

// Nadzór: tak | nie · profil | do 24.10 08:30 | wstrzymany · STOP ręczny
function supervisionOf(inst) {
  var p = przegladOf(inst)
  if (!p || !p.nadzor) return { text: MISSING, tone: "dim2" }
  var n = p.nadzor
  if (isLost(inst)) return { text: "stracona", tone: "bad" }
  if (isBank(inst) && n.aktywny === false) return { text: "bank", tone: "blue" }
  if (n.aktywny === false) {
    if (n.do) return { text: "do " + doLabel(n.do), tone: "mag" }
    var why = { profil: "profil", konfiguracja: "konfiguracja", test: "test", brak_profilu: "brak profilu", glowna: "główna" }[n.zrodlo]
    return { text: "nie · " + (why || String(n.zrodlo || "poza nadzorem")), tone: "dim" }
  }
  if (p.stop && p.stop.reczny === true) return { text: "wstrzymany · STOP ręczny", tone: "warn" }
  return { text: "tak", tone: "ok" }
}

// ---------------------------------------------------------------- wiersz tabeli

function rowOf(inst, now) {
  var lv = levelOf(inst)
  var alarm = alarmOf(inst, now)
  var p = przegladOf(inst)
  var stan = stanOf(inst)
  var off = isOffline(inst)
  return {
    id: inst.id,
    nick: inst.nick ? String(inst.nick) : (inst.id === "" ? "główna" : String(inst.id)),
    idLabel: inst.id === "" ? "główna" : String(inst.id),
    stan: stan,
    inGame: !off,
    test: isTest(inst),
    reserve: isReserve(inst),
    lost: isLost(inst),
    bank: isBank(inst),
    order: STAN_ORDER[isLost(inst) ? "offline" : stan],
    dot: stanDotTone(inst),
    pill: pillOf(inst),
    since: sinceText(inst, now),
    spot: spotOf(inst),
    floor: floorLabel(inst),
    mode: modeOf(inst),
    level: lv.level,
    levelPct: lv.pct,
    ml: mlLabel(inst),
    mlPct: mlPctOf(inst),
    hp: resource(inst, "hp", "max_hp"),
    mana: resource(inst, "mana", "max_mana"),
    where: whereLabel(inst),
    whereCity: !off && !!cityOf(inst).city,
    spotTime: spotTimeOf(inst, now),
    zabH: off ? null : zabH(inst),
    expH: off ? null : expH(inst),
    runy: off ? "" : runyText(inst),
    runyLow: off ? false : runyLow(inst),
    spotkan: off ? null : spotkanKey(inst),                  // 26.10: liczba spotkań (bez progu) z sekcji `spotkania`; brak danych = null (klucz sortowania „spotkań ↓”)
    alarm: alarm,
    alarmFlag: !!(p && (p.stan === "alarm" || p.alarm_24h === true)),
    supervision: supervisionOf(inst),
    lastT: off ? lastDataT(inst) : now.getTime() / 1000       // „ostatnio aktywna” do sortowania: w grze = teraz, poza grą = chwila wyjścia z gry
  }
}

function rowsOf(instances, now) {
  var out = []
  for (var i = 0; i < instances.length; i++) out.push(rowOf(instances[i], now))
  return out
}

// ---------------------------------------------------------------- sortowanie (25.10: „sortowanie po lvl i wybór sortowania, domyślnie po lvlu”)

// Jedno ustawienie sortowania dla Przeglądu (grupy tabeli) i dla listy postaci w pasku bocznym (proste i spójne: ta sama kolejność wszędzie).
// Brak danych (poziom, exp/h, HP% poza grą, czas) zawsze ląduje na końcu, niezależnie od kierunku. Remis: wyższy poziom, wyższy % do następnego poziomu,
// nazwa alfabetycznie, id, potem kolejność wejściowa (stabilnie). Filtry i ukrywanie straconych działają przed sortowaniem (sortujemy to, co widoczne).
var DEFAULT_SORT = "level"
var SORTS = [
  { key: "level", label: "w grze, poziom ↓" },
  { key: "nazwa", label: "nazwa A→Z" },
  { key: "exp_h", label: "exp/h ↓" },
  { key: "stan", label: "stan" },
  { key: "hp", label: "HP% ↑" },
  { key: "ostatnio", label: "ostatnio ↓" },
  { key: "spotkan", label: "spotkań ↓" }
]

// klucz sortowania, jeśli znany; inaczej null (do odczytu zapisanego wyboru z pliku)
function validSort(key) {
  var k = String(key === undefined || key === null ? "" : key).replace(/^\s+|\s+$/g, "")
  for (var i = 0; i < SORTS.length; i++) if (SORTS[i].key === k) return k
  return null
}

// a, b liczby albo brak (null/undefined/NaN); brak zawsze na końcu, także przy desc
function cmpNum(a, b, desc) {
  var ma = !isNum(a)
  var mb = !isNum(b)
  if (ma || mb) return ma === mb ? 0 : (ma ? 1 : -1)
  if (a === b) return 0
  return (a < b) !== desc ? -1 : 1
}

// polskie litery sortują się jak podstawowe (ł po l, nie za z), niezależnie od ustawień językowych systemu; remis rozstrzyga zapis dokładny
var PL_FOLD = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z" }
function foldText(v) {
  return String(v === undefined || v === null ? "" : v).toLowerCase().replace(/[ąćęłńóśźż]/g, function (ch) { return PL_FOLD[ch] })
}

function cmpText(a, b) {
  var x = foldText(a)
  var y = foldText(b)
  if (x !== y) return x < y ? -1 : 1
  var rx = String(a === undefined || a === null ? "" : a).toLowerCase()
  var ry = String(b === undefined || b === null ? "" : b).toLowerCase()
  return rx < ry ? -1 : (rx > ry ? 1 : 0)
}

function levelKey(row) { return isNum(row.level) && row.level >= 1 ? row.level : null }
function hpKey(row) { return row.hp && row.hp.live === true && isNum(row.hp.frac) ? row.hp.frac : null }

function sortPrimary(a, b, key) {
  if (key === "nazwa") return cmpText(a.nick, b.nick)
  if (key === "exp_h") return cmpNum(a.expH, b.expH, true)
  if (key === "stan") return cmpNum(a.order !== undefined ? a.order : STAN_ORDER[a.stan], b.order !== undefined ? b.order : STAN_ORDER[b.stan], false)
  if (key === "hp") return cmpNum(hpKey(a), hpKey(b), false)
  if (key === "ostatnio") return cmpNum(a.lastT, b.lastT, true)
  if (key === "spotkan") return cmpNum(a.spotkan, b.spotkan, true)          // 26.10: najwięcej spotkań pierwsze; brak danych na końcu
  // 26.10 (Karol): domyślnie najpierw postacie w grze, dopiero potem wylogowane; w obu grupach poziom malejąco
  if (a.inGame !== b.inGame) return a.inGame ? -1 : 1
  return cmpNum(levelKey(a), levelKey(b), true)
}

function sortCompare(a, b, key) {
  var d = sortPrimary(a, b, key)
  if (d !== 0) return d
  d = cmpNum(levelKey(a), levelKey(b), true)
  if (d !== 0) return d
  d = cmpNum(a.levelPct, b.levelPct, true)
  if (d !== 0) return d
  d = cmpText(a.nick, b.nick)
  if (d !== 0) return d
  return cmpText(a.id, b.id)
}

// Wspólny silnik: items posortowane wg wiersza rowFn(item); nie zmienia wejścia, stabilny (indeks wejściowy jako ostatni klucz).
function sortWith(items, rowFn, key) {
  var k = validSort(key) || DEFAULT_SORT
  var dec = []
  for (var i = 0; i < items.length; i++) dec.push({ item: items[i], row: rowFn(items[i]), i: i })
  dec.sort(function (a, b) {
    var d = sortCompare(a.row, b.row, k)
    return d !== 0 ? d : a.i - b.i
  })
  var out = []
  for (var j = 0; j < dec.length; j++) out.push(dec[j].item)
  return out
}

function sortRows(rows, key) { return sortWith(rows, function (r) { return r }, key) }

// Lista instancji (pasek boczny) w tej samej kolejności co wiersze Przeglądu; `now` jak w rowOf.
function sortInstances(instances, key, now) { return sortWith(instances, function (inst) { return rowOf(inst, now || new Date()) }, key) }

// ---------------------------------------------------------------- filtry i grupy

var FILTERS = ["wszystkie", "w grze", "z alarmem", "stracone"]

// Stracone (25.10) są domyślnie ukryte: „wszystkie”, „w grze” i „z alarmem” ich nie pokazują, widać je tylko w filtrze „stracone”;
// licznik „wszystkie” (i chipów) liczy więc same postacie nie-stracone, a stracone ma osobny licznik „stracone”.
function passes(row, filter) {
  if (filter === "stracone") return row.lost
  if (row.lost) return false
  if (filter === "w grze") return row.inGame
  if (filter === "z alarmem") return row.alarmFlag
  return true
}

function filterCounts(rows) {
  var c = { "wszystkie": 0, "w grze": 0, "z alarmem": 0, "stracone": 0 }
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].lost) { c["stracone"]++; continue }
    c["wszystkie"]++
    if (rows[i].inGame) c["w grze"]++
    if (rows[i].alarmFlag) c["z alarmem"]++
  }
  return c
}

// Grupy tabeli po filtrze: „W GRZE” (dane na żywo) i „OFFLINE” (ostatnio znane); puste grupy znikają. Wiersze w grupie wg sortKey (domyślnie poziom ↓).
function groupsOf(rows, filter, sortKey) {
  var live = []
  var off = []
  for (var i = 0; i < rows.length; i++) {
    if (!passes(rows[i], filter)) continue
    (rows[i].inGame ? live : off).push(rows[i])
  }
  live = sortRows(live, sortKey)
  off = sortRows(off, sortKey)
  var out = []
  if (live.length) out.push({ key: "gra", title: "W GRZE", count: live.length, note: "dane na żywo, co 2–5 s", rows: live })
  if (off.length) out.push({ key: "offline", title: "OFFLINE", count: off.length, note: "ostatnio znane, wyszarzone; „ostatnio” = chwila wyjścia z gry", rows: off })
  return out
}

// ---------------------------------------------------------------- liczniki

// Do sum nie wchodzą instancje testowe (test:true); są widoczne w tabeli.
// Stracone (25.10) są ukryte, więc nie wchodzą też do „total” ani „offline” (tylko c.lost, osobny chip „stracone”): „W grze 4 / 7” znaczy 7 widocznych postaci.
function countersOf(instances) {
  var c = { inGame: 0, total: 0, bot: 0, karol: 0, stopped: 0, offline: 0, reserve: 0, suspended: 0, lost: 0, bank: 0, expH: 0, expBots: 0, rescue: 0 }
  for (var i = 0; i < instances.length; i++) {
    var inst = instances[i]
    if (isTest(inst)) continue
    var stan = stanOf(inst)
    if (isLost(inst)) { c.lost++; continue }      // stracona: tylko c.lost; bez total/offline, botów/Karola/zatrzymanych, zawieszonych, rezerwy i exp/h
    c.total++
    if (inGame(inst)) c.inGame++
    if (stan === "bot_dziala" || stan === "alarm") c.bot++
    else if (stan === "karol_gra") c.karol++
    else if (stan === "zatrzymany") c.stopped++
    else { c.offline++; if (stan === "zawieszony" && !isBank(inst)) c.suspended++ }
    if (isBank(inst)) c.bank++
    if (isReserve(inst)) c.reserve++
    var e = expH(inst)
    if (e !== null) { c.expH += e; c.expBots++ }
    if (isNum(inst.ratunek_dzis)) c.rescue += inst.ratunek_dzis
  }
  return c
}

function suspendedNote(c) {
  if (c.suspended === 0) return ""
  return "w tym " + c.suspended + " " + plural(c.suspended, "zawieszona", "zawieszone", "zawieszonych")
}

function expBotsNote(c) { return c.expBots + " " + plural(c.expBots, "bot", "boty", "botów") }

function postaciLabel(n) { return n + " " + plural(n, "postać", "postaci", "postaci") }

// ---------------------------------------------------------------- lista postaci w pasku bocznym (stracone ukryte domyślnie)

// Lista instancji do paska bocznego, stopki i wyboru: bez straconych, chyba że showLost (przełącznik „pokaż stracone” w pasku).
function visibleInstances(instances, showLost) {
  if (showLost) return instances
  var out = []
  for (var i = 0; i < instances.length; i++) if (!isLost(instances[i])) out.push(instances[i])
  return out
}

function lostCount(instances) {
  var n = 0
  for (var i = 0; i < instances.length; i++) if (isLost(instances[i])) n++
  return n
}

// Wybór po odświeżeniu stanu / ukryciu straconych: zostaje, gdy wybrana jest na liście widocznych; inaczej pierwsza widoczna (puste = brak zmiany).
// Gdy nic nie jest widoczne (same stracone), zostaje stary wybór (albo pierwsza instancja, gdy starego nie ma), żeby nie zostać bez postaci.
function selectionAfter(instances, selectedId, showLost) {
  var vis = visibleInstances(instances, showLost)
  for (var i = 0; i < vis.length; i++) if (vis[i].id === selectedId) return selectedId
  if (vis.length) return vis[0].id
  for (var j = 0; j < instances.length; j++) if (instances[j].id === selectedId) return selectedId
  return instances.length ? instances[0].id : selectedId
}

// Plakietka pozycji „Przegląd” w pasku bocznym: „4/7 w grze”
function navBadge(instances) {
  var c = countersOf(instances)
  return c.inGame + "/" + c.total + " w grze"
}

// ---------------------------------------------------------------- karta offline w pasku bocznym

function cardMode(inst) {
  var p = przegladOf(inst)
  if (!p) return "legacy"                    // stare API / brak przeglądu: karta jak dotąd
  return p.w_grze === true && !isLost(inst) ? "live" : "offline"
}

// Dwie linie zamiast pasków HP/MP (wysokość jak online: 2 x 14 px).
function cardOffline(inst, now) {
  var o = ostatnieOf(inst)
  var c = cityOf(inst)
  var fl = floorLabel(inst)
  var p = poz3(inst)
  var place
  if (c.city) place = "⌂ " + cityName(c.city) + (c.depo ? " · depo" + (fl ? " " + fl : "") : "")
  else if (p) place = "⌖ " + fl + " · " + p[0] + "," + p[1]
  else place = o ? "⌖ brak pozycji" : "brak ostatnich danych"
  var t = lastDataT(inst)
  var hp = resource(inst, "hp", "max_hp")
  var mp = resource(inst, "mana", "max_mana")
  var pr = przegladOf(inst)
  var right
  if (isLost(inst)) right = { text: "stracona", tone: "bad" }
  else if (isBank(inst)) right = { text: "bank", tone: "blue" }
  else if (isReserve(inst)) right = { text: "rezerwa", tone: "dim" }
  else if (pr && pr.stan === "zawieszony" && pr.nadzor && pr.nadzor.do) right = { text: "do " + doShort(pr.nadzor.do), tone: "mag" }
  else if (pr && pr.stop && pr.stop.reczny === true) right = { text: "STOP ręczny", tone: "warn" }
  else right = { text: "", tone: "dim" }
  return {
    place: place,
    when: t === null ? "" : whenLabel(t, now),
    hp: hp.max === null ? MISSING : String(hp.max),       // na karcie bez „~” (mało miejsca; przybliżenie widać w tabeli i w „Ostatnio znane”)
    mp: mp.max === null ? MISSING : String(mp.max),
    ml: mlLabel(inst),
    mlKnown: !!(o && isNum(o.ml)),
    mlPct: mlPctOf(inst),
    right: right
  }
}

// Podtytuł karty (linia 2): „Karol gra · bot stoi” (cyan) zamiast mapy i trybu
function cardSubtitleTone(inst) { return isLost(inst) ? "bad" : (stanOf(inst) === "karol_gra" ? "cyan" : "dim") }
function cardSubtitleText(inst, fallback) { return isLost(inst) ? "postać stracona" : (stanOf(inst) === "karol_gra" ? "Karol gra · bot stoi" : fallback) }

// ---------------------------------------------------------------- „Ostatnio znane” (Sesja gry)

function expToNext(level) { return 50 * (Math.pow(level + 1, 3) - 6 * Math.pow(level + 1, 2) + 17 * (level + 1) - 12) / 3 }

function koniecLabel(code) { return END_LABEL[code] || { text: MISSING, tone: "dim" } }

// Blok pokazujemy tylko gdy gra nie działa i instancja nie jest główną (główna startuje ręcznie, własny widok).
function lastKnownVisible(inst) {
  if (!inst || inst.id === "") return false
  if (!przegladOf(inst)) return false
  return isLost(inst) || (inst.gra !== true && !inGame(inst))
}

function lastKnown(inst, now) {
  var o = ostatnieOf(inst)
  var pr = przegladOf(inst)
  var t = lastDataT(inst)
  var out = {
    empty: !o,
    title: "OSTATNIO ZNANE",
    sub: o ? "· postać offline, dane z chwili wyjścia" : "· brak zapisanych danych: plik powstanie po pierwszym zapisie bota albo logowaniu",
    online: t === null ? "" : whenLabel(t, now),
    ago: t === null ? "" : agoLabel(t, now),
    stats: [],
    cols: [],
    source: ""
  }
  if (!o) return out
  var lv = levelOf(inst)
  var mlKnown = isNum(o.ml)
  var mlPct = mlPctOf(inst)
  var maxHp = resource(inst, "hp", "max_hp")
  var maxMp = resource(inst, "mana", "max_mana")
  var next = lv.level !== null && isNum(o.exp) ? Math.max(0, Math.round(expToNext(lv.level) - o.exp)) : null
  out.stats = [
    { key: "level", label: "LEVEL", value: lv.level === null ? "?" : String(lv.level), small: lv.pct === null ? "" : lv.pct + "%", bar: lv.pct === null ? -1 : lv.pct / 100, dim: lv.level === null },
    { key: "ml", label: "MAGIC LEVEL", value: mlKnown ? String(o.ml) : "?", small: mlKnown ? (o.ml_zrodlo === "reczny" ? "wpis ręczny" : (mlPct === null ? "" : mlPct + "%")) : "brak odczytu", bar: mlPct === null ? -1 : mlPct / 100, dim: !mlKnown },
    { key: "hp", label: "HP MAX", value: maxHp.max === null ? "?" : (maxHp.approx ? APPROX : "") + maxHp.max, small: "", bar: -1, dim: maxHp.max === null },
    { key: "mana", label: "MANA MAX", value: maxMp.max === null ? "?" : (maxMp.approx ? APPROX : "") + maxMp.max, small: "", bar: -1, dim: maxMp.max === null },
    { key: "exp", label: "EXP", value: isNum(o.exp) ? groupDigits(o.exp) : "?", small: next !== null ? "do " + (lv.level + 1) + ": " + groupDigits(next) : "", bar: -1, dim: !isNum(o.exp) },
    { key: "gold", label: "GOLD Z SESJI", value: o.sesja && isNum(o.sesja.gold) ? groupDigits(o.sesja.gold) : "?", small: o.sesja && isNum(o.sesja.gold) ? "gp" : "", bar: -1, dim: !(o.sesja && isNum(o.sesja.gold)) }
  ]

  var c = cityOf(inst)
  var p = poz3(inst)
  var fl = floorLabel(inst)
  var where = [
    { k: "spot", v: spotOf(inst) || MISSING, tone: "fg2" },
    { k: "piętro", v: fl || MISSING, tone: "fg2" },
    { k: "pozycja", v: p ? p[0] + ", " + p[1] + ", z" + p[2] : MISSING, tone: "fg2" },
    { k: "miasto", v: c.city ? cityName(c.city) + (c.depo ? " · depo" : "") : (p ? "poza miastem" : MISSING), tone: "fg2" },
    { k: "tryb", v: modeOf(inst) || MISSING, tone: "fg2" }
  ]

  var s = o.sesja
  var when = MISSING
  if (s && isNum(s.start)) {
    var a = new Date(s.start * 1000)
    when = ddmm(a) + " " + hhmm(a)
    if (isNum(s.koniec)) {
      var b = new Date(s.koniec * 1000)
      when += "–" + hhmm(b) + " (" + spanLabel(s.koniec - s.start) + ")"
    } else when += " · trwała"
  }
  var gained = s && isNum(s.exp_start) && isNum(o.exp) ? "+" + groupDigits(o.exp - s.exp_start) : MISSING
  var end = koniecLabel(o.koniec_sesji)
  var last = [
    { k: "kiedy", v: when, tone: "fg2" },
    { k: "zabicia", v: s && isNum(s.zab) ? String(s.zab) : MISSING, tone: "fg2" },
    { k: "exp", v: gained, tone: "fg2" },
    { k: "koniec", v: end.text, tone: end.tone },
    { k: "stan bota", v: o.stan_bota ? String(o.stan_bota) : MISSING, tone: "fg2" }
  ]

  var al = alarmOf(inst, now)
  var sup = supervisionOf(inst)
  var supText = sup.text
  if (isLost(inst)) supText = "stracona · postać stracona (profil)"
  else if (isBank(inst)) supText = "bank · poza nadzorem (profil: rola)"
  else if (pr && pr.stan === "zawieszony" && !(pr.nadzor && pr.nadzor.do)) supText = "rezerwa · poza nadzorem (profil)"
  else if (pr && pr.nadzor && pr.nadzor.aktywny === false && pr.nadzor.do) supText = "zawieszony do " + doLabel(pr.nadzor.do)
  var sections = [
    { k: "ostatni alarm", v: al ? al.time + " " + al.text : MISSING, tone: al ? al.tone : "dim2" },
    { k: "nadzór", v: supText, tone: sup.tone }
  ]
  if (o.stop && (o.stop.powod || isNum(o.stop.t))) {
    sections.push({ k: "stop", v: (isNum(o.stop.t) ? whenLabel(o.stop.t, now) + " " : "") + stripAlarm(o.stop.powod || (o.stop.reczny ? "STOP ręczny" : "STOP")), tone: o.stop.reczny ? "warn" : "fg2" })
  }
  out.cols = [
    { title: "GDZIE STOI", rows: where },
    { title: "OSTATNIA SESJA", rows: last },
    { title: "ALARM I NADZÓR", rows: sections }
  ]
  var who = SOURCE_LABEL[o.zrodlo] || String(o.zrodlo || "?")
  var savedAt = isNum(o.zapisano) ? new Date(o.zapisano * 1000) : null
  out.source = "źródło: instancje/" + inst.id + "/ostatnie.json · zapisane " + (savedAt ? ddmm(savedAt) + " " + hhmm(savedAt) + ":" + pad2(savedAt.getSeconds()) : MISSING)
               + " przez " + who + (isList(o.przyblizone) && o.przyblizone.length ? " · przybliżone: " + Array.prototype.join.call(o.przyblizone, ", ") : "")
  return out
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    STAN_ORDER: STAN_ORDER, STAN_PILL: STAN_PILL, FILTERS: FILTERS, MISSING: MISSING,
    plural: plural, whenLabel: whenLabel, spanLabel: spanLabel, agoLabel: agoLabel, doLabel: doLabel,
    stanOf: stanOf, isTest: isTest, inGame: inGame, isReserve: isReserve, isLost: isLost, isBank: isBank, isOffline: isOffline, pillOf: pillOf, stanDotTone: stanDotTone,
    whereLabel: whereLabel, levelOf: levelOf, levelText: levelText, mlLabel: mlLabel, mlPctOf: mlPctOf, resource: resource, sinceText: sinceText, spotTimeOf: spotTimeOf,
    alarmOf: alarmOf, supervisionOf: supervisionOf, rowOf: rowOf, rowsOf: rowsOf, passes: passes, filterCounts: filterCounts,
    groupsOf: groupsOf, countersOf: countersOf, suspendedNote: suspendedNote, expBotsNote: expBotsNote, postaciLabel: postaciLabel,
    navBadge: navBadge, visibleInstances: visibleInstances, lostCount: lostCount, selectionAfter: selectionAfter, cardMode: cardMode, cardOffline: cardOffline, cardSubtitleTone: cardSubtitleTone, cardSubtitleText: cardSubtitleText,
    DEFAULT_SORT: DEFAULT_SORT, SORTS: SORTS, validSort: validSort, sortRows: sortRows, sortInstances: sortInstances,
    expToNext: expToNext, lastKnownVisible: lastKnownVisible, lastKnown: lastKnown, groupDigits: groupDigits, numOrDash: numOrDash, sessionRate: sessionRate
  }
}
