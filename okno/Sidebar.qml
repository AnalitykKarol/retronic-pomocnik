pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "OknoModel.js" as Model
import "RetronicModel.js" as Rules

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
  readonly property string message: ctl.selected ? (ctl.messages[ctl.selected.id] || "") : ""
  readonly property string hoverHint: btnReturn.hovered ? returnSpec.hint : (btnRefill.hovered ? refillSpec.hint
                                      : (btnSpot.hovered ? spotSpec.hint : (btnMain.hovered ? mainHint : "")))
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
          model: side.ctl.instances
          delegate: CharCard {
            required property var modelData
            width: cardsCol.width
            inst: modelData
            klasa: (side.ctl.statuses[modelData.id] && side.ctl.statuses[modelData.id].ok) ? side.ctl.statuses[modelData.id].klasa : "brak"
            selected: modelData.id === side.ctl.selectedId
            onChosen: side.ctl.select(modelData.id)
          }
        }
      }
    }

    Column {
      id: navCol
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
      NavItem { width: parent.width; icon: "▶"; label: "Sesja gry"; soon: "F4" }
      NavItem {
        width: parent.width; icon: "⌖"; label: "Mapa i tryb"
        objectName: "nav-mapa"
        current: side.ctl.section === "mapa"
        onChosen: side.ctl.setSection("mapa")
      }
      NavItem { width: parent.width; icon: "≡"; label: "Ustawienia"; soon: "F3" }
      NavItem {
        width: parent.width; icon: "✚"; label: "Ratunek"
        objectName: "nav-ratunek"
        current: side.ctl.section === "ratunek"
        count: side.ctl.selected && side.ctl.selected.ratunek_dzis ? side.ctl.selected.ratunek_dzis : 0
        onChosen: side.ctl.setSection("ratunek")
      }
    }

    Item { Layout.fillHeight: true }

    Column {
      id: actionsCol
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

      Btn {
        id: btnMain
        objectName: "akcja-glowna"
        width: parent.width
        label: side.kind === "stop" ? "■ Stop" : "▶ Start"
        tone: side.kind === "stop" ? "stop" : "ok"
        active: Rules.buttonEnabled(side.st)
        busy: side.ctl.actionBusy
        onActivated: side.ctl.runAction(side.kind)
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
          busy: side.ctl.actionBusy
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
          busy: side.ctl.actionBusy
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
          busy: side.ctl.actionBusy
          onActivated: side.ctl.runAction(side.spotSpec.action)
        }
      }

      Text {
        objectName: "akcje-linia"
        width: parent.width
        wrapMode: Text.WordWrap
        maximumLineCount: 3
        elide: Text.ElideRight
        text: side.message !== "" ? side.message : (side.hoverHint !== "" ? side.hoverHint : side.info.text)
        color: side.message !== "" || (side.hoverHint === "" && side.info.error) ? Theme.bad : Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.bold: side.message !== "" || (side.hoverHint === "" && side.info.error)
        // zawsze rezerwuj miejsce na dwie linie, żeby akcje nie skakały przy zmianie komunikatu
        height: Math.max(implicitHeight, 26)
      }
    }
  }
}
