import QtQuick
import QtQuick.Controls
import "OknoModel.js" as Model
import "PrzegladModel.js" as Prz
import "SpotkaniaModel.js" as Spo

// Karta postaci w pasku bocznym (makieta wariant B): kropka stanu, nick, instancja, mapa · tryb, lvl, mini HP/MP. Klik = wybór postaci.
// Klik w nick = podgląd tej instancji (`previewRequested`, spec 2026-10-20-retronic-lvl-i-podglad.md Q1); znacznik przy nicku jak na pasku:
// podgląd otwarty = akcent, zamknięty = przygaszony, brak sesji (albo główna) = bez znacznika i nick nieklikalny.
// Przegląd (spec 2026-10-22-retronic-przeglad.md): postać poza grą (`przeglad.w_grze` false) ma zamiast pasków HP/MP dwie linie ostatnio znanych danych
// (gdzie stoi + kiedy; HP/MP max, ML i powód blokady), tło przygaszone; „Karol gra” = kropka i podtytuł w cyan. Wysokość karty bez zmian (2 x 14 px).
Rectangle {
  id: card

  property var inst: ({})
  property string klasa: "brak"
  property bool selected: false
  property var preview: ({ state: "main", label: "", enabled: false, hint: "" })     // wynik Rules.previewState
  property bool busy: false      // akcja TEJ instancji w toku (ctl.isBusy(id)): nick nie przyjmuje kliknięcia; inne instancje nie wpływają

  property var now: new Date()     // chwila odświeżenia stanu (do „wczoraj 20:14” na karcie offline)

  readonly property var marker: Model.previewMarker(preview)
  readonly property string mode: Prz.cardMode(inst)                // live | offline | legacy (brak pola przeglad: karta jak dotąd)
  readonly property bool offline: mode === "offline"
  readonly property var spo: Spo.cardLines(inst)                   // 26.10: dwie linie spotkań z graczami (okno_api `spotkania` w `stan`); stary stan bez pola = bez linii
  readonly property var off: offline ? Prz.cardOffline(inst, now) : null
  readonly property bool lost: mode !== "legacy" && Prz.isLost(inst)                // postać stracona (profil `stracony`): nie „Karol gra”, kropka szara
  readonly property bool karolGra: Prz.stanOf(inst) === "karol_gra" && mode !== "legacy" && !lost

  signal chosen()
  signal previewRequested()

  implicitHeight: col.implicitHeight + 22
  radius: 10
  color: offline ? Theme.alpha(Theme.sur, 0.45) : Theme.sur
  border.width: 1
  border.color: selected ? Theme.blue : (mouse.containsMouse ? Theme.line2 : Theme.line)

  // delikatna obwódka od środka dla wybranej (box-shadow inset z makiety)
  Rectangle {
    anchors.fill: parent
    anchors.margins: 1
    radius: 9
    color: "transparent"
    border.width: card.selected ? 1 : 0
    border.color: Theme.alpha(Theme.blue, 0.25)
  }

  Column {
    id: col
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.margins: 12
    anchors.topMargin: 11
    spacing: 0

    Item {
      width: parent.width
      height: 20

      Rectangle {
        id: dot
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 9
        height: 9
        radius: 4.5
        color: card.karolGra ? Theme.cyan : (card.lost ? Theme.dim2 : Theme.stateColor(card.klasa))
      }
      Item {
        id: nickBox
        anchors.left: dot.right
        anchors.leftMargin: 8
        anchors.right: tag.left
        anchors.rightMargin: 8
        height: parent.height

        Text {
          id: nick
          anchors.verticalCenter: parent.verticalCenter
          width: Math.min(implicitWidth, nickBox.width - (marker.visible ? 16 : 0))
          text: Model.nickOf(card.inst)
          color: card.offline ? Theme.fg2 : Theme.fg
          font.family: Theme.font
          font.pixelSize: Theme.body
          font.bold: true
          font.underline: nickMouse.enabled && nickMouse.containsMouse
          elide: Text.ElideRight
        }
        // znacznik podglądu: wypełnione koło w akcencie = otwarty, pusty pierścień = zamknięty; brak sesji = bez znacznika
        Rectangle {
          id: marker
          objectName: "podglad-znacznik"
          visible: card.marker.visible
          anchors.left: nick.right
          anchors.leftMargin: 7
          anchors.verticalCenter: parent.verticalCenter
          width: 9
          height: 9
          radius: 4.5
          color: card.marker.filled ? Theme.tone(card.marker.tone) : "transparent"
          border.width: 1
          border.color: Theme.tone(card.marker.tone)
        }
        MouseArea {
          id: nickMouse
          objectName: "nick-" + card.inst.id
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          width: marker.visible ? marker.x + marker.width : nick.width
          height: parent.height
          enabled: card.preview.enabled && !card.busy
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          function tryClick() { if (enabled) card.previewRequested() }
          onClicked: tryClick()
        }
      }
      Chip {
        id: tag
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        small: true
        label: Model.instanceLabel(card.inst)
      }
    }

    Item {
      width: parent.width
      height: subtitle.implicitHeight + 12

      Text {
        id: lvl
        objectName: "karta-lvl"
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 4
        text: card.mode === "legacy" ? Model.levelText(card.inst) : Prz.levelText(card.inst)
        visible: text !== ""
        color: card.offline ? Theme.dim : Theme.fg2
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.bold: true
      }
      Text {
        id: subtitle
        anchors.left: parent.left
        anchors.right: lvl.visible ? lvl.left : parent.right
        anchors.rightMargin: lvl.visible ? 8 : 0
        anchors.top: parent.top
        anchors.topMargin: 4
        text: Prz.cardSubtitleText(card.inst, Model.cardSubtitle(card.inst))
        color: card.karolGra ? Theme.cyan : (card.lost ? Theme.bad : Theme.dim)
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        elide: Text.ElideRight
      }
    }

    Mini { visible: !card.offline; width: parent.width; label: "HP"; fillColor: Theme.bad; value: Model.hpFraction(card.inst) }
    Mini { visible: !card.offline; width: parent.width; label: "MP"; fillColor: Theme.blue; value: Model.mpFraction(card.inst) }

    // blanki i gotowe runy (okno_api `runy`, odczyt pamięci; 25.10): jedna linia pod paskami, mało blanków = żółty, brak odczytu = linia ukryta
    Item {
      objectName: "karta-runy"
      readonly property string txt: Prz.runyText(card.inst)
      visible: !card.offline && txt !== ""
      width: parent.width
      height: visible ? 14 : 0
      Text {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: parent.txt
        color: Prz.runyLow(card.inst) ? Theme.warn : Theme.fg2
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        elide: Text.ElideRight
      }
    }

    // spotkania z graczami (26.10): cienka linia i dwie krótkie linie pod paskami. Licznik n/próg od ostatniego startu bota + najczęstszy gracz; czas na spocie + spotkań/h.
    // Licznik >= próg: bursztyn (Theme.warn). Brak danych (bot stoi, inna sesja, jeszcze nie policzone): „-” zamiast zer; powód w podpowiedzi.
    Rectangle {
      objectName: "karta-spotkania-linia"
      visible: !card.offline && card.spo.shown
      width: parent.width
      height: visible ? 1 : 0
      color: Theme.line
    }
    Item {
      objectName: "karta-spotkania-" + (card.inst.id === undefined ? "" : card.inst.id)
      visible: !card.offline && card.spo.shown
      width: parent.width
      height: visible ? 16 + 14 + 16 : 0                    // + trzecia linia „widziani” (26.10)
      readonly property string meetText: card.spo.meet
      readonly property string timeText: card.spo.time
      readonly property string seenText: card.spo.seen
      readonly property bool hot: card.spo.hot

      Text {
        id: meetLine
        objectName: "karta-spotkania-licznik"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 5
        height: 14
        text: card.spo.meet
        color: card.spo.hot ? Theme.warn : (card.spo.ok ? Theme.fg2 : Theme.dim2)
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.bold: card.spo.hot
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
      }
      Text {
        objectName: "karta-spotkania-czas"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: meetLine.bottom
        anchors.topMargin: 2
        height: 14
        text: card.spo.time
        color: card.spo.ok ? Theme.dim : Theme.dim2
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
      }
      // 26.10 (Karol): widziani = różni obcy gracze w zasięgu wzroku od wejścia na ten spot (>= 1 próbka, bez progu 15 s); „-” gdy brak początku huntu / danych
      Text {
        objectName: "karta-spotkania-widziani"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 5 + 14 + 2 + 14 + 2
        height: 14
        text: card.spo.seen
        color: card.spo.seenOk ? Theme.fg2 : Theme.dim2
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
      }
      HoverHandler { id: spoHover }                         // pasywny: nie zabiera kliknięcia karcie
      ToolTip.visible: spoHover.hovered && card.spo.tip !== ""
      ToolTip.delay: 500
      ToolTip.text: card.spo.tip
    }

    // postać poza grą: ostatnio znane dane zamiast pasków (dwie linie po 14 px = wysokość dwóch pasków)
    Item {
      objectName: "karta-offline-1"
      visible: card.offline
      width: parent.width
      height: card.offline ? 14 : 0
      Text {
        anchors.left: parent.left
        anchors.right: whenText.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: card.off ? card.off.place : ""
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        elide: Text.ElideRight
      }
      Text {
        id: whenText
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: card.off ? card.off.when : ""
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
      }
    }
    Item {
      objectName: "karta-offline-2"
      visible: card.offline
      width: parent.width
      height: card.offline ? 14 : 0
      Text {
        anchors.left: parent.left
        anchors.right: reason.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        textFormat: Text.StyledText
        text: card.off ? "HP <font color=\"" + Theme.fg2 + "\">" + card.off.hp + "</font> · MP <font color=\"" + Theme.fg2 + "\">" + card.off.mp
                         + "</font> · ML <font color=\"" + (card.off.mlKnown ? Theme.fg2 : Theme.dim2) + "\">" + card.off.ml + "</font>" + (card.off.mlPct !== null && card.off.mlPct !== undefined ? " " + card.off.mlPct + "%" : "") : ""
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        elide: Text.ElideRight
      }
      Text {
        id: reason
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: card.off ? card.off.right.text : ""
        color: card.off ? Theme.tone(card.off.right.tone) : Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
      }
    }
  }

  component Mini: Item {
    id: mini
    property string label: ""
    property color fillColor: Theme.blue
    property real value: 0
    height: 14

    Text {
      id: lbl
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: 28
      text: mini.label
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.tiny
      font.letterSpacing: 1
    }
    Rectangle {
      anchors.left: lbl.right
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      height: 6
      radius: 3
      color: Theme.line
      clip: true
      Rectangle {
        width: parent.width * mini.value
        height: parent.height
        radius: 3
        color: mini.fillColor
      }
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: card.chosen()
  }
}
