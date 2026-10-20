import QtQuick
import Quickshell

// Tylko do testów (QA offscreen): wykonuje kroki z RETRONIC_OKNO_SCENARIUSZ, np.
//   "sekcja:mapa;mapa:raty;tryb:ml;klik:start-z-tym;klik:start-potwierdz;czekaj:2500;zrzut:/tmp/a.png;koniec"
// Bez zmiennej nic nie robi. Kliknięcia idą przez Btn.tryClick() (ta sama bramka co mysz: szary przycisk nie zadziała).
// Kroki: sekcja:<mapa|ratunek> · wybierz:<id|glowna> · klik:<objectName> · mapa:<nazwa> · tryb:<nazwa> · sygnal:<indeks>
//        czekaj:<ms> · zrzut:<plik.png> · zamknij (zamyka okno: proces ma wyjść sam) · koniec
// F3 (Ustawienia): sekcja:ustawienia · grupa:<nazwa> · filtr:<tekst> · zmienione (przełącza "tylko zmienione") · ustaw:KLUCZ=WART (jak z widoku:
//        ctl.setKnob) · suwak:KLUCZ=WART (puszczenie suwaka) · wpisz:KLUCZ=WART (Enter w polu liczby) · pokaz:KLUCZ (jak Enter w Ctrl+K)
//        paleta · paleta-wpisz:<tekst> · paleta-ruch:<n> · paleta-enter · paleta-esc  (Ctrl+K sprawdza się osobno, prawdziwym klawiszem)
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

  readonly property bool dataReady: ctl.loaded && (ctl.section === "ratunek" ? ctl.ratunekData !== null
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
