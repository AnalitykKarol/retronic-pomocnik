import QtQuick
import qs.Commons
import "RetronicModel.js" as Model

// Zawartość panelu: nagłówek (z guzikiem "▣ Otwórz okno") i wiersz na instancję (kropka stanu, nazwa, stan, osobny Stop/Start,
// pod nim "⌂ Miasto", "↻ Refill" i "↗ Spot" z jedną linią o cyklu spot -> miasto -> refill -> spot, potem HP/mana,
// ostatni start, proxy, krótki błąd). Bez logiki bota: dostaje obiekty Instance i je rysuje.
Column {
  id: content

  property var rows: []
  property string summary: ""
  property color foreground: Color.foreground
  property color urgent: Color.urgent
  property color okColor: "#6fbf73"
  property color warnColor: "#d9a441"
  property string fontFamily: Style.font.family
  // "Otwórz okno" jest jeden dla całego panelu (nie per instancja): stan i błąd trzyma Panel.qml.
  property bool windowBusy: false
  property string windowMessage: ""

  signal openWindowRequested()

  readonly property color dim: Qt.darker(foreground, 1.55)

  function stateColor(klasa) {
    if (klasa === "alarm") return content.urgent
    if (klasa === "dziala") return content.okColor
    if (klasa === "stop") return content.warnColor
    return content.dim
  }

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  spacing: Style.space(10)

  // ---------- Nagłówek ----------
  Column {
    width: parent.width
    spacing: Style.space(2)

    Item {
      width: parent.width
      height: Math.max(titleText.implicitHeight, windowButton.height)

      Text {
        id: titleText
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: "Retronic"
        color: content.foreground
        font.family: content.fontFamily
        font.pixelSize: Style.font.title
        font.bold: true
      }

      // Otwiera osobne okno zarządzania (okno.sh); to samo CityButton co ⌂ ↻ ↗, tylko myszą.
      CityButton {
        id: windowButton
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(112)
        spec: Model.windowButton()
        busy: content.windowBusy
        foreground: content.foreground
        urgent: content.urgent
        okColor: content.okColor
        warnColor: content.warnColor
        fontFamily: content.fontFamily
        onActivated: content.openWindowRequested()
      }
    }
    Text {
      width: parent.width
      text: content.summary
      color: content.dim
      font.family: content.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
    Text {
      visible: text !== ""
      width: parent.width
      text: content.windowMessage
      color: content.urgent
      font.family: content.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
      elide: Text.ElideRight
    }
  }

  // ---------- Wiersz na instancję ----------
  Repeater {
    model: content.rows

    Column {
      id: card
      required property var modelData
      required property int index
      readonly property var inst: modelData
      readonly property var st: inst.status
      readonly property string klasa: st && st.ok ? st.klasa : "brak"
      readonly property string kind: Model.buttonKind(st)
      readonly property bool canClick: Model.buttonEnabled(st) && !inst.busy
      readonly property color accentColor: kind === "stop" ? content.urgent : content.okColor
      // Guziki miasta: stan wylicza Model, tu tylko rysunek. Pod myszą powód szarego guzika zastępuje linię o cyklu.
      readonly property var returnSpec: Model.returnButton(st)
      readonly property var refillSpec: Model.refillButton(st)
      readonly property var spotSpec: Model.spotButton(st)
      readonly property var info: Model.cityInfo(st)
      readonly property string hoverHint: returnButton.hovered ? returnSpec.hint : (refillButton.hovered ? refillSpec.hint : (spotButton.hovered ? spotSpec.hint : ""))

      width: content.width
      spacing: Style.space(3)

      Rectangle {
        visible: card.index > 0
        width: parent.width
        height: 1
        color: content.alpha(content.foreground, 0.12)
      }

      Item {
        width: parent.width
        height: Math.max(actionButton.height, nameText.implicitHeight)

        Rectangle {
          id: dot
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          width: Style.space(10)
          height: width
          radius: width / 2
          color: content.stateColor(card.klasa)
        }

        Text {
          id: nameText
          anchors.left: dot.right
          anchors.leftMargin: Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          text: Model.displayName(card.inst.instanceId)
          color: content.foreground
          font.family: content.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Text {
          anchors.left: nameText.right
          anchors.leftMargin: Style.space(8)
          anchors.right: actionButton.left
          anchors.rightMargin: Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          text: Model.stateLabel(card.st)
          color: card.klasa === "alarm" ? content.urgent : content.dim
          font.family: content.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.bold: card.klasa === "alarm"
          elide: Text.ElideRight
        }

        // Stop i Start różnią się kolorem, znaczkiem i napisem; po kliknięciu przycisk blokuje się na chwilę,
        // więc drugi klik nie trafi w przycisk, który zdążył zmienić się w przeciwny.
        Rectangle {
          id: actionButton
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          width: Style.space(78)
          height: Style.space(26)
          radius: Style.cornerRadius
          color: card.canClick ? content.alpha(card.accentColor, buttonMouse.containsMouse ? 0.30 : 0.16) : "transparent"
          border.width: 1
          border.color: card.canClick ? card.accentColor : content.alpha(content.foreground, 0.2)

          Text {
            anchors.centerIn: parent
            text: card.inst.busy ? "…" : (card.kind === "stop" ? "■ Stop" : "▶ Start")
            color: card.canClick ? card.accentColor : content.dim
            font.family: content.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }

          MouseArea {
            id: buttonMouse
            anchors.fill: parent
            enabled: card.canClick
            hoverEnabled: true
            cursorShape: card.canClick ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: card.inst.run(card.kind)
          }
        }
      }

      Row {
        leftPadding: Style.space(18)
        spacing: Style.space(6)

        CityButton {
          id: returnButton
          spec: card.returnSpec
          busy: card.inst.busy
          foreground: content.foreground
          urgent: content.urgent
          okColor: content.okColor
          warnColor: content.warnColor
          fontFamily: content.fontFamily
          onActivated: card.inst.run(card.returnSpec.action)
        }

        CityButton {
          id: refillButton
          spec: card.refillSpec
          busy: card.inst.busy
          foreground: content.foreground
          urgent: content.urgent
          okColor: content.okColor
          warnColor: content.warnColor
          fontFamily: content.fontFamily
          onActivated: card.inst.run(card.refillSpec.action)
        }

        CityButton {
          id: spotButton
          spec: card.spotSpec
          busy: card.inst.busy
          foreground: content.foreground
          urgent: content.urgent
          okColor: content.okColor
          warnColor: content.warnColor
          fontFamily: content.fontFamily
          onActivated: card.inst.run(card.spotSpec.action)
        }
      }

      Text {
        visible: text !== ""
        width: parent.width
        leftPadding: Style.space(18)
        text: card.hoverHint !== "" ? card.hoverHint : card.info.text
        color: card.hoverHint === "" && card.info.error ? content.urgent : content.dim
        font.family: content.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: card.hoverHint === "" && card.info.error
        elide: Text.ElideRight
      }

      Text {
        visible: text !== ""
        width: parent.width
        leftPadding: Style.space(18)
        text: Model.resourcesLabel(card.st)
        color: content.dim
        font.family: content.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        leftPadding: Style.space(18)
        text: Model.lastStartLabel(card.st)
        color: content.dim
        font.family: content.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }

      Text {
        visible: text !== ""
        width: parent.width
        leftPadding: Style.space(18)
        text: Model.proxyLabel(card.st)
        color: content.dim
        font.family: content.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }

      Text {
        visible: text !== ""
        width: parent.width
        leftPadding: Style.space(18)
        text: card.inst.message
        color: content.urgent
        font.family: content.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
        elide: Text.ElideRight
      }
    }
  }
}
