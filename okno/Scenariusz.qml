import QtQuick
import Quickshell
import "OknoModel.js" as Model
import "PrzegladModel.js" as Prz

// Tylko do testów (QA offscreen): wykonuje kroki z RETRONIC_OKNO_SCENARIUSZ, np.
//   "sekcja:mapa;mapa:raty;tryb:ml;klik:start-z-tym;klik:start-potwierdz;czekaj:2500;zrzut:/tmp/a.png;koniec"
// Bez zmiennej nic nie robi. Kliknięcia idą przez Btn.tryClick() (ta sama bramka co mysz: szary przycisk nie zadziała).
// Kroki: sekcja:<przeglad|sesja|mapa|spotkania|ustawienia> · wybierz:<id|glowna> · klik:<objectName> · mapa:<nazwa> · tryb:<nazwa> · sygnal:<indeks>
//        czekaj:<ms> · zrzut:<plik.png> · zamknij (zamyka okno: proces ma wyjść sam) · koniec
// F4 (Sesja gry): sekcja:sesja · wybierz:<id|glowna> · klik:sesja-uruchom|sesja-zamknij|sesja-zamknij-potwierdz|sesja-zamknij-anuluj|sesja-podglad
//        akcje-stan:<id,id..> (loguje zajętość akcji per instancja i klikalność Stop/Zamknij wybranej) · klik:nick-<id> (klik w nick na karcie = podgląd) · sesja-stan (loguje dostępność guzików, potwierdzenie i wynik akcji)
// F2 przeglądu: sekcja:przeglad · klik:filtr-wszystkie|filtr-w-grze|filtr-z-alarmem|filtr-stracone (chipy) · klik:wiersz-<id> (klik w wiersz tabeli = Sesja gry tej postaci) · klik:nav-przeglad
// F3 (Ustawienia): sekcja:ustawienia · grupa:<nazwa> · filtr:<tekst> · zmienione (przełącza "tylko zmienione") · ustaw:KLUCZ=WART (jak z widoku:
//        ctl.setKnob) · suwak:KLUCZ=WART (puszczenie suwaka) · wpisz:KLUCZ=WART (Enter w polu liczby) · pokaz:KLUCZ (jak Enter w Ctrl+K)
//        kolejka:K1=V1,K2=V2>id (kilka zapisów i od razu zmiana postaci w tym samym kroku: zapisy w kolejce muszą dojść do swojej instancji)
//        stan (loguje sekcję, grupę, filtr, pokrętło do pokazania, czy paleta otwarta i notkę zapisu) · paleta · paleta-wpisz:<tekst> · paleta-ruch:<n> · paleta-enter · paleta-esc  (skrót Ctrl+K i klawisze palety sprawdza osobno test/klawisze-sway.sh)
// Stracone (25.10): klik:pokaz-stracone (przełącznik w pasku bocznym, widoczny gdy są stracone) · lista-stan (loguje widoczne id, przełącznik, wybraną, liczniki i chip „stracone”)
// Sortowanie (25.10): klik:sort-level|sort-nazwa|sort-exp_h|sort-stan|sort-hp|sort-ostatnio (chipy w Przeglądzie) · kolejnosc (loguje wybrany klucz, kolejność wierszy tabeli od góry
//        z podziałem na grupy [w nawiasach] i kolejność kart w pasku bocznym; plik z zapamiętanym wyborem sprawdza qml-atrapa.sh)
// Spotkania (26.10): sekcja:spotkania · spotkania-stan (loguje linie kart: `karta-spotkania-<id>` i wiersze tabeli) · klik:nav-spotkania
// „Zaloguj postać” (24.10, loguje do gry BEZ bota): klik:akcja-zaloguj (pasek boczny, wybrana postać) · klik:zaloguj-<id> (przycisk w wierszu Przeglądu, tylko postacie poza grą)
//        zaloguj-stan:<id|glowna> (loguje stan guzika: wlaczony, powod, busy, podpowiedz, oraz Backend.loginId i wynik ostatniego logowania)
Item {
  id: sc

  required property var ctl
  required property Item target

  readonly property string script: Quickshell.env("RETRONIC_OKNO_SCENARIUSZ") || ""
  property var steps: script === "" ? [] : script.split(";")
  property int pos: 0
  property double notBefore: 0

  function find(item, name) {
    if (!item) return null
    if (item.objectName === name) return item
    var kids = item.children
    for (var i = 0; i < kids.length; i++) {
      var hit = find(kids[i], name)
      if (hit) return hit
    }
    return null
  }

  // pozycje (y na ekranie) wierszy tabeli, nagłówków grup i kart postaci w pasku, do kroku `kolejnosc`
  function collectOrder(item, out) {
    if (!item) return
    var n = item.objectName
    if (n && item.visible && (n.indexOf("wiersz-") === 0 || n.indexOf("nick-") === 0 || n.indexOf("grupa-") === 0)) out.push({ name: n, y: item.mapToItem(target, 0, 0).y })
    var kids = item.children
    for (var ci = 0; ci < kids.length; ci++) collectOrder(kids[ci], out)
  }

  // kolejność z ekranu (krok `kolejnosc`): wiersze tabeli Przeglądu, nagłówki grup i karty w pasku, sortowane po pozycji y (nie po modelu)
  function logOrder() {
    var found = []
    collectOrder(target, found)
    found.sort(function (a, b) { return a.y - b.y })
    var tab = []
    var kar = []
    for (var fi = 0; fi < found.length; fi++) {
      var nm = found[fi].name
      if (nm.indexOf("nick-") === 0) kar.push(nm.substring(5) === "" ? "glowna" : nm.substring(5))
      else if (nm.indexOf("wiersz-") === 0) tab.push(nm.substring(7) === "" ? "glowna" : nm.substring(7))
      else tab.push("[" + nm.substring(6) + "]")
    }
    console.log("[scenariusz] KOLEJNOSC sort=" + ctl.sortKey + " tabela=" + tab.join(",") + " pasek=" + kar.join(","))
  }
  Timer { id: orderTimer; interval: 500; onTriggered: sc.logOrder() }

  readonly property bool dataReady: ctl.loaded && (ctl.section === "przeglad" ? true
                                     : ctl.section === "sesja" ? ctl.sesjaData !== null
                                     : ctl.section === "spotkania" ? ctl.spotkaniaData !== null
                                     : (ctl.section === "ustawienia" ? ctl.pokretlaData !== null && ctl.mapyData !== null : ctl.mapyData !== null))

  function parseValue(text) {
    try { return JSON.parse(text) } catch (e) { return text }
  }

  function run(step) {
    var i = step.indexOf(":")
    var cmd = i < 0 ? step : step.substring(0, i)
    var arg = i < 0 ? "" : step.substring(i + 1)
    console.log("[scenariusz] " + step)
    if (cmd === "sekcja") ctl.setSection(arg)
    else if (cmd === "wybierz") ctl.select(arg === "glowna" ? "" : arg)
    else if (cmd === "mapa") ctl.chooseMap(arg)
    else if (cmd === "tryb") ctl.toggleMode(arg)
    else if (cmd === "grupa") { var g = find(target, "grupa-" + arg); if (g) g.tryClick(); else console.log("[scenariusz] BRAK grupy " + arg) }
    else if (cmd === "filtr") ctl.settingsText = arg
    else if (cmd === "zmienione") ctl.settingsOnlyChanged = !ctl.settingsOnlyChanged
    else if (cmd === "ustaw" || cmd === "suwak" || cmd === "wpisz") {
      var eq = arg.indexOf("=")
      var key = arg.substring(0, eq)
      var val = arg.substring(eq + 1)
      if (cmd === "ustaw") ctl.setKnob(key, parseValue(val))
      else if (cmd === "suwak") { var s = find(target, "suwak-" + key); if (s) s.committed(Number(val)); else console.log("[scenariusz] BRAK suwaka " + key) }
      else { var f = find(target, "pole-" + key); if (f) f.commit(val); else console.log("[scenariusz] BRAK pola " + key) }
    }
    else if (cmd === "sesja-stan") {
      var bt = ctl.sesjaData ? Model.sessionButtons(ctl.sesjaData) : null
      var cf = find(target, "sesja-potwierdzenie")
      console.log("[scenariusz] SESJA id=" + ctl.selectedId + " uruchom=" + (bt ? bt["gra-start"].enabled : "?") + " zamknij=" + (bt ? bt["gra-zamknij"].enabled : "?")
                  + " podglad=" + (bt ? bt["podglad"].enabled + ":" + bt["podglad"].label : "?") + " potwierdzenie=" + (cf ? cf.visible : "?")
                  + " wynik=" + ctl.sesjaNote.tone + ":" + ctl.sesjaNote.text)
    }
    else if (cmd === "lista-stan") {
      // lista postaci w pasku bocznym (25.10): widoczne id, przełącznik „pokaż stracone”, wybrana, liczniki Przeglądu i filtr
      var vids = []
      for (var vi = 0; vi < ctl.visibleInstances.length; vi++) vids.push(ctl.visibleInstances[vi].id === "" ? "glowna" : ctl.visibleInstances[vi].id)
      var tg = find(target, "pokaz-stracone")
      var cn = Prz.countersOf(ctl.instances)
      var fc = Prz.filterCounts(Prz.rowsOf(ctl.instances, new Date()))
      console.log("[scenariusz] LISTA widoczne=" + vids.join(",") + " stracone=" + ctl.lostCount + " pokazStracone=" + ctl.showLost
                  + " przelacznik=" + (tg ? tg.visible + ":" + tg.text : "brak") + " wybrana=" + (ctl.selectedId === "" ? "glowna" : ctl.selectedId)
                  + " total=" + cn.total + " offline=" + cn.offline + " wszystkie=" + fc["wszystkie"] + " stracone-chip=" + fc["stracone"])
    }
    else if (cmd === "spotkania-stan") {
      // karty w pasku (linie `karta-spotkania-<id>`) i wiersze tabeli zakładki; arg = lista id po przecinku
      var sids = arg === "" ? [] : arg.split(",")
      for (var si = 0; si < sids.length; si++) {
        var kc = find(target, "karta-spotkania-" + sids[si])
        var kr = find(target, "spotkania-wiersz-" + sids[si])
        console.log("[scenariusz] SPOTKANIA id=" + sids[si] + " karta=" + (kc ? (kc.visible ? kc.meetText + " | " + kc.timeText + " | hot=" + kc.hot : "ukryta") : "brak")
                    + " wiersz=" + (kr ? kr.spotText + " | " + kr.playersText + " | " + kr.meetText + " | " + kr.rateText + " | " + kr.regularText : "brak"))
      }
      console.log("[scenariusz] SPOTKANIA-DANE zmiany=" + (ctl.spotkaniaData ? ctl.spotkaniaData.zmiany.length : "brak") + " unikane=" + (ctl.spotkaniaData ? ctl.spotkaniaData.unikane.length : "brak")
                  + " blad=" + ctl.spotkaniaError + " nav=" + (find(target, "nav-spotkania") ? "jest" : "brak") + " nav-ratunek=" + (find(target, "nav-ratunek") ? "jest" : "brak"))
    }
    else if (cmd === "kolejnosc") { notBefore = Date.now() + 1100; orderTimer.restart() }       // odczyt po 500 ms: układ po zmianie sortowania zdąży się przeliczyć
    else if (cmd === "zaloguj-stan") {
      var lid = arg === "glowna" ? "" : arg
      var ls = ctl.loginState(lid)
      var ln = ctl.loginNotes[lid]
      console.log("[scenariusz] ZALOGUJ id=" + arg + " wlaczony=" + ls.enabled + " powod=" + ls.reason + " busy=" + ls.busy + " podpowiedz=" + ls.hint
                  + " loginId=" + ctl.loginId + " wynik=" + (ln ? (ln.ok ? "ok:" : "blad:") + ln.text : "brak"))
    }
    else if (cmd === "akcje-stan") {
      // zajętość akcji per instancja: busy=<id>:<bool>,... dla argumentu (lista id po przecinku, "glowna" = główna) oraz klikalność guzików wybranej
      var ids = arg === "" ? [] : arg.split(",")
      var parts = []
      for (var bi = 0; bi < ids.length; bi++) parts.push(ids[bi] + ":" + ctl.isBusy(ids[bi] === "glowna" ? "" : ids[bi]))
      var gl = find(target, "akcja-glowna")
      var zm = find(target, "sesja-zamknij")
      console.log("[scenariusz] AKCJE wybrana=" + ctl.selectedId + " busy=" + parts.join(",") + " stop-klikalny=" + (gl ? gl.canClick : "?")
                  + " zamknij-klikalny=" + (zm ? zm.canClick : "?"))
    }
    else if (cmd === "stan") console.log("[scenariusz] STAN section=" + ctl.section + " grupa=" + ctl.settingsGroup + " filtr=" + ctl.settingsText + " fokus=" + ctl.focusKey
                                         + " paleta=" + ctl.paletteOpen + " notka=" + ctl.knobNote.tone + ":" + ctl.knobNote.text)
    else if (cmd === "kolejka") {
      var gt = arg.indexOf(">")
      var pairs = arg.substring(0, gt).split(",")
      for (var q = 0; q < pairs.length; q++) {
        var qe = pairs[q].indexOf("=")
        ctl.setKnob(pairs[q].substring(0, qe), parseValue(pairs[q].substring(qe + 1)))
      }
      ctl.select(arg.substring(gt + 1) === "glowna" ? "" : arg.substring(gt + 1))
    }
    else if (cmd === "pokaz") ctl.openKnob(arg)
    else if (cmd === "paleta") ctl.openPalette()
    else if (cmd === "paleta-wpisz") { var pf = find(target, "paleta-pole"); if (pf) pf.text = arg; else console.log("[scenariusz] BRAK palety") }
    else if (cmd === "paleta-ruch") { var pn = find(target, "paleta-nakladka"); if (pn) pn.move(Number(arg)) }
    else if (cmd === "paleta-enter") { var pe = find(target, "paleta-nakladka"); if (pe) pe.accept() }
    else if (cmd === "paleta-esc") ctl.closePalette()
    else if (cmd === "czekaj") notBefore = Date.now() + Number(arg)
    else if (cmd === "sygnal") {
      var v = find(target, "widok-ratunek")
      if (v && v.shown.length > Number(arg)) v.pickedId = v.shown[Number(arg)].id
    } else if (cmd === "klik") {
      var b = find(target, arg)
      if (!b) console.log("[scenariusz] BRAK elementu " + arg)
      else if (b.tryClick) { console.log("[scenariusz] canClick=" + b.canClick); b.tryClick() }
      else if (b.activated) b.activated()
      else if (b.chosen) b.chosen()
    } else if (cmd === "zrzut") {
      target.grabToImage(function(result) { console.log("[scenariusz] zrzut " + arg + " " + result.saveToFile(arg)) })
      notBefore = Date.now() + 700
    } else if (cmd === "zamknij") target.Window.window.visible = false     // proces ma sam się zakończyć
    else if (cmd === "koniec") Qt.quit()
  }

  Timer {
    interval: 450
    repeat: true
    running: sc.steps.length > 0
    onTriggered: {
      if (Date.now() < sc.notBefore || sc.pos >= sc.steps.length) return
      if (!sc.dataReady) return
      sc.run(sc.steps[sc.pos++])
    }
  }
}
