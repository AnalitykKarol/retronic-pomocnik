pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "OknoModel.js" as Model
import "RetronicModel.js" as Rules
import "PrzegladModel.js" as Prz
import "SpotkaniaModel.js" as Spo

// Pasek boczny 260 px (makieta wariant B): karty postaci (lista przewijana, liczona na 10), menu sekcji wybranej postaci
// i akcje na dole: Stop/Start oraz ⌂ Miasto, ↻ Refill, ↗ Spot. Akcje i reguły szarości są te same co na pasku:
// stan guzików liczy Rules (RetronicModel.js), polecenia budują się w Backend.runAction przez Rules.actionCommand.
Rectangle {
  id: side

  required property var ctl

  readonly property var st: ctl.selectedStatus
  readonly property string kind: Rules.buttonKind(st)
  readonly property var returnSpec: Rules.returnButton(st)
  readonly property var refillSpec: Rules.refillButton(st)
  readonly property var spotSpec: Rules.spotButton(st)
  readonly property var info: Rules.cityInfo(st)
  readonly property var loginSpec: ctl.loginState(ctl.selectedId)       // „Zaloguj”: Model.loginState (szarości i powody), bez bota
  readonly property var loginNote: ctl.selected ? (ctl.loginNotes[ctl.selected.id] || null) : null    // wynik ostatniego logowania {ok, text}
  readonly property bool overview: ctl.section === "przeglad"          // w Przeglądzie nie ma wybranej postaci: bez menu postaci i akcji
  readonly property string message: ctl.selected ? (ctl.messages[ctl.selected.id] || "") : ""
  readonly property string hoverHint: btnReturn.hovered ? returnSpec.hint : (btnRefill.hovered ? refillSpec.hint
                                      : (btnSpot.hovered ? spotSpec.hint : (btnMain.hovered ? mainHint
                                      : (btnLogin.hovered ? loginSpec.hint : ""))))
  // Powód szarego Stop/Start (pasek go nie pokazuje; tu jest miejsce na linię pod guzikami).
  readonly property string mainHint: {
    if (!st || !st.ok) return "brak odczytu"
    if (kind === "start" && !Rules.buttonEnabled(st)) return Rules.serviceRunning(st) ? "serwis w toku" : "gra nie działa"
    return kind === "stop" ? "zatrzymuje bota (STOP)" : "start z ostatnią mapą i trybem"
  }

  color: Theme.bg2

  Rectangle {
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.right: parent.right
    width: 1
    color: Theme.line
  }

  ColumnLayout {
    anchors.fill: parent
    anchors.topMargin: 14
    anchors.bottomMargin: 14
    anchors.leftMargin: 12
    anchors.rightMargin: 13
    spacing: 14

    NavItem {
      Layout.fillWidth: true
      icon: "▦"; label: "Przegląd"
      objectName: "nav-przeglad"
      current: side.overview
      badge: Prz.navBadge(side.ctl.instances)
      badgeTone: "blue"
      onChosen: side.ctl.setSection("przeglad")
    }

    Item {
      Layout.fillWidth: true
      Layout.topMargin: -6
      implicitHeight: postacieLabel.implicitHeight + 4
      Text {
        id: postacieLabel
        anchors.left: parent.left
        anchors.leftMargin: 2
        text: "POSTACIE"
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.letterSpacing: 1
      }
      Text {
        objectName: "postacie-liczba"
        anchors.right: parent.right
        anchors.rightMargin: 2
        text: String(side.ctl.visibleInstances.length)
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
      }
    }

    Flickable {
      id: cardsFlick
      Layout.fillWidth: true
      // kart nie więcej niż ich treść (pod nimi od razu menu); gdy za mało miejsca (10 postaci) lista się kurczy i przewija
      Layout.fillHeight: true
      Layout.preferredHeight: cardsCol.implicitHeight
      Layout.maximumHeight: cardsCol.implicitHeight
      Layout.minimumHeight: 96
      contentWidth: width
      contentHeight: cardsCol.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      interactive: contentHeight > height
      ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

      Column {
        id: cardsCol
        width: cardsFlick.width
        spacing: 14

        Repeater {
          model: side.ctl.visibleInstances
          delegate: CharCard {
            required property var modelData
            width: cardsCol.width
            inst: modelData
            klasa: (side.ctl.statuses[modelData.id] && side.ctl.statuses[modelData.id].ok) ? side.ctl.statuses[modelData.id].klasa : "brak"
            now: side.ctl.refreshedAt || new Date()
            selected: modelData.id === side.ctl.selectedId && !side.overview
            preview: Rules.previewState(side.ctl.statuses[modelData.id] || null, modelData.id)
            busy: side.ctl.isBusy(modelData.id)
            onChosen: side.overview ? side.ctl.openChar(modelData.id) : side.ctl.select(modelData.id)
            onPreviewRequested: { side.ctl.select(modelData.id); side.ctl.previewFor(modelData.id) }
          }
        }
      }
    }

    // „pokaż stracone” (25.10): stracone postacie są domyślnie poza listą; ten jeden wiersz je pokazuje/ukrywa (widoczny tylko, gdy jakieś są)
    Text {
      id: lostToggle
      objectName: "pokaz-stracone"
      signal activated()
      onActivated: side.ctl.setShowLost(!side.ctl.showLost)
      visible: side.ctl.lostCount > 0
      Layout.fillWidth: true
      Layout.topMargin: -6
      leftPadding: 2
      text: (side.ctl.showLost ? "ukryj stracone" : "pokaż stracone") + " (" + side.ctl.lostCount + ")"
      color: toggleArea.containsMouse ? Theme.fg : Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.tiny
      MouseArea {
        id: toggleArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: lostToggle.activated()
      }
    }

    Column {
      id: navCol
      visible: !side.overview
      Layout.fillWidth: true
      // menu i akcje nigdy się nie zwijają: przy 10 postaciach kurczy się tylko lista kart (przewijana)
      Layout.minimumHeight: implicitHeight
      Layout.preferredHeight: implicitHeight
      spacing: 2

      Text {
        leftPadding: 10
        topPadding: 4
        bottomPadding: 6
        text: side.ctl.selected ? Model.nickOf(side.ctl.selected).toUpperCase() : ""
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.letterSpacing: 1
      }
      NavItem {
        width: parent.width; icon: "▶"; label: "Sesja gry"
        objectName: "nav-sesja"
        current: side.ctl.section === "sesja"
        onChosen: side.ctl.setSection("sesja")
      }
      NavItem {
        width: parent.width; icon: "⌖"; label: "Mapa i tryb"
        objectName: "nav-mapa"
        current: side.ctl.section === "mapa"
        onChosen: side.ctl.setSection("mapa")
      }
      NavItem {
        width: parent.width; icon: "≡"; label: "Ustawienia"
        objectName: "nav-ustawienia"
        current: side.ctl.section === "ustawienia"
        onChosen: side.ctl.setSection("ustawienia")
      }
      // 26.10: „Spotkania” w miejscu „Ratunku” (RatunekView.qml zostaje w plikach, nieużywany; RATUNEK_HAIKU=0 u wszystkich). Plakietka = ile postaci osiągnęło próg zmiany spotu.
      NavItem {
        width: parent.width; icon: "◎"; label: "Spotkania"
        objectName: "nav-spotkania"
        current: side.ctl.section === "spotkania"
        count: Spo.summaryOf(side.ctl.visibleInstances).hot
        onChosen: side.ctl.setSection("spotkania")
      }
    }

    Item { Layout.fillHeight: true }

    Column {
      id: actionsCol
      visible: !side.overview
      Layout.fillWidth: true
      Layout.minimumHeight: implicitHeight
      Layout.preferredHeight: implicitHeight
      spacing: 8

      Text {
        leftPadding: 2
        text: "AKCJE" + (side.ctl.selected ? " · " + Model.nickOf(side.ctl.selected).toUpperCase() : "")
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.letterSpacing: 1
      }

      Row {
        width: parent.width
        spacing: 6

        Btn {
          id: btnMain
          objectName: "akcja-glowna"
          width: (parent.width - 6) * 0.5
          label: side.kind === "stop" ? "■ Stop" : "▶ Start"
          tone: side.kind === "stop" ? "stop" : "ok"
          active: Rules.buttonEnabled(side.st)
          busy: side.ctl.isBusy(side.ctl.selectedId)
          onActivated: side.ctl.runAction(side.kind)
        }
        // „Zaloguj postać” (24.10): loguje postać do gry BEZ uruchamiania bota; szary: główna, stracona, już w grze, inne logowanie trwa
        Btn {
          id: btnLogin
          objectName: "akcja-zaloguj"
          width: (parent.width - 6) * 0.5
          label: side.loginSpec.label
          tone: "prim"
          active: side.loginSpec.enabled
          busy: side.loginSpec.busy
          onActivated: side.ctl.runLogin(side.ctl.selectedId)
        }
      }

      Row {
        width: parent.width
        spacing: 6

        Btn {
          id: btnReturn
          objectName: "akcja-miasto"
          width: (parent.width - 12) / 3
          compact: true
          label: side.returnSpec.label
          tone: side.returnSpec.tone === "off" ? "neutral" : side.returnSpec.tone
          active: side.returnSpec.enabled
          busy: side.ctl.isBusy(side.ctl.selectedId)
          onActivated: side.ctl.runAction(side.returnSpec.action)
        }
        Btn {
          id: btnRefill
          objectName: "akcja-refill"
          width: (parent.width - 12) / 3
          compact: true
          label: side.refillSpec.label
          tone: side.refillSpec.tone === "off" ? "neutral" : side.refillSpec.tone
          active: side.refillSpec.enabled
          busy: side.ctl.isBusy(side.ctl.selectedId)
          onActivated: side.ctl.runAction(side.refillSpec.action)
        }
        Btn {
          id: btnSpot
          objectName: "akcja-spot"
          width: (parent.width - 12) / 3
          compact: true
          label: side.spotSpec.label
          tone: side.spotSpec.tone === "off" ? "neutral" : side.spotSpec.tone
          active: side.spotSpec.enabled
          busy: side.ctl.isBusy(side.ctl.selectedId)
          onActivated: side.ctl.runAction(side.spotSpec.action)
        }
      }

      Text {
        objectName: "akcje-linia"
        width: parent.width
        wrapMode: Text.WordWrap
        maximumLineCount: 3
        elide: Text.ElideRight
        text: side.message !== "" ? side.message : (side.hoverHint !== "" ? side.hoverHint : (side.loginNote ? side.loginNote.text : side.info.text))
        color: side.message !== "" ? Theme.bad : (side.hoverHint === "" && side.loginNote ? (side.loginNote.ok ? Theme.ok : Theme.bad)
               : (side.hoverHint === "" && side.info.error ? Theme.bad : Theme.dim))
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.bold: side.message !== "" || (side.hoverHint === "" && (side.loginNote !== null || side.info.error))
        // zawsze rezerwuj miejsce na dwie linie, żeby akcje nie skakały przy zmianie komunikatu
        height: Math.max(implicitHeight, 26)
      }
    }
  }
}
