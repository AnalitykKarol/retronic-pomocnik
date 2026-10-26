pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "SpotkaniaModel.js" as Spo

// Zakładka Spotkania (26.10, Karol: statystyki spotkań z graczami na spocie; zajęła miejsce Ratunku w menu). Cztery bloki: tabela per postać (kolejność i ukrywanie
// straconych jak w Przeglądzie: ctl.visibleInstances), „Czas i tempo” wybranej postaci, „Zmiany spotu” z dzisiejszego dziennika nadzorcy i lista unikanych spotów.
// Bez „Historii dnia”. Liczniki i czasy idą ze `stan` (inst.spotkania, tylko bieżąca sesja bota, „-” przy braku danych), zmiany i unikane z `okno_api spotkania`
// (ctl.spotkaniaData). Okno niczego nie liczy: logika prezentacji w SpotkaniaModel.js. Klik w wiersz tabeli wybiera postać (blok „Czas i tempo”).
Item {
  id: view

  required property var ctl

  readonly property var feed: ctl.spotkaniaData
  readonly property var insts: ctl.visibleInstances
  readonly property var rows: Spo.rowsOf(insts)
  readonly property var summary: Spo.summaryOf(insts)
  readonly property var seen: Spo.lastSeen(insts, ctl.refreshedAt || new Date())
  readonly property var tempo: ctl.selected ? Spo.tempoOf(ctl.selected) : null
  readonly property var changes: Spo.changeRows(feed, insts)
  readonly property var avoided: Spo.avoidRows(feed, insts)
  readonly property var limits: Spo.limitsOf(feed)

  // kolumny tabeli: POSTAĆ · NA SPOCIE · GRACZY · WIDZIANI · SPOTKAŃ · PRÓG BOTA n/próg · /H · BYWALEC (26.10: „widziani” = różni obcy gracze w zasięgu wzroku od wejścia na ten spot;
  // „spotkań” i bywalec = spotkania bez minimalnego czasu widoku, „próg bota” = licznik decyzyjny bota, >= 15 s w widoku);
  // w wąskim oknie tabela przewija się poziomo
  readonly property var colW: [170, 90, 60, 80, 80, 110, 50, 150]
  readonly property var heads: ["postać", "na spocie", "graczy", "widziani", "spotkań", "próg bota", "/h", "bywalec"]
  readonly property var rightCols: [1, 2, 3, 4, 5, 6]
  readonly property int gap: 12
  readonly property int lead: 14          // dodatkowy odstęp przed ostatnią kolumną tekstową (bywalec), żeby nie dotykała liczb po prawej
  readonly property int pad: 22
  readonly property int tableW: Math.max(body.width, 910)

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Spotkania z graczami"
      subtitle: Spo.subtitleOf(view.feed)

      Chip {
        objectName: "spotkania-ostatni"
        label: view.seen ? "ostatnio: " + view.seen.text : "ostatnio widziany gracz: -"
        textColor: view.seen ? Theme.fg2 : Theme.dim
      }
    }

    Flickable {
      id: body
      objectName: "spotkania-tresc"
      Layout.fillWidth: true
      Layout.fillHeight: true
      contentWidth: view.tableW
      contentHeight: content.implicitHeight + 28
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      flickableDirection: Flickable.AutoFlickDirection
      ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
      ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }

      Column {
        id: content
        width: view.tableW
        spacing: 0

        Text {
          visible: view.ctl.spotkaniaError !== ""
          x: view.pad
          topPadding: 12
          width: parent.width - 2 * view.pad
          wrapMode: Text.Wrap
          text: "błąd odczytu spotkań: " + view.ctl.spotkaniaError + (view.feed ? " (pokazuję ostatni odczyt)" : "")
          color: Theme.bad
          font.family: Theme.font
          font.pixelSize: Theme.small
        }

        // ---------- tabela per postać
        SecLabel { title: "per postać"; note: view.summary.withData + " z " + view.summary.total + " z danymi" + (view.summary.hot > 0 ? " · " + view.summary.hot + " na progu" : "") }
        Rectangle {
          width: parent.width
          height: 30
          color: Theme.bg
          Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
          Row {
            x: view.pad
            height: parent.height
            spacing: view.gap
            Repeater {
              model: view.heads
              delegate: Item {
                id: headCell
                required property int index
                required property string modelData
                width: view.colW[index]
                height: 30
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.right: view.rightCols.indexOf(headCell.index) >= 0 ? parent.right : undefined
                  anchors.left: view.rightCols.indexOf(headCell.index) >= 0 ? undefined : parent.left
                  anchors.leftMargin: headCell.index === 7 ? view.lead : 0
                  text: headCell.modelData.toUpperCase()
                  color: Theme.dim2
                  font.family: Theme.font
                  font.pixelSize: Theme.tiny
                  font.letterSpacing: 1
                }
              }
            }
          }
        }
        Repeater {
          model: view.rows
          delegate: Rectangle {
            id: tr
            required property var modelData
            readonly property bool picked: modelData.id === view.ctl.selectedId
            objectName: "spotkania-wiersz-" + modelData.id
            readonly property string meetText: modelData.meet
            readonly property string spotsText: modelData.spots
            readonly property string spotText: modelData.onSpot
            readonly property string playersText: modelData.players
            readonly property string seenText: modelData.seen
            readonly property string rateText: modelData.perHour
            readonly property string regularText: modelData.regular
            width: content.width
            height: 38
            color: mouse.containsMouse ? Theme.alpha(Theme.blue, 0.07) : (picked ? Theme.alpha(Theme.blue, 0.05) : "transparent")
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
            Rectangle { visible: tr.picked; anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 3; color: Theme.blue }

            function tryClick() { view.ctl.select(modelData.id) }
            MouseArea {
              id: mouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: tr.tryClick()
              ToolTip.visible: containsMouse
              ToolTip.delay: 500
              ToolTip.text: tr.modelData.ok
                ? "spotkań: gracz w zasięgu wzroku choćby na chwilę (ten sam gracz znów po 5 min bez niego)\npróg bota " + tr.modelData.meet + ": licznik decyzyjny bota (>= 15 s w widoku; po progu nadzorca zmienia spot)"
                  + (tr.modelData.botRegular !== "-" ? "\nnajczęściej wg bota: " + tr.modelData.botRegular : "")
                : "brak danych o spotkaniach: " + tr.modelData.why
            }

            Row {
              x: view.pad
              height: parent.height
              spacing: view.gap
              Cell {
                w: view.colW[0]
                Row {
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: 8
                  Text { text: tr.modelData.nick; color: tr.modelData.ok ? Theme.fg : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                  Text { text: tr.modelData.idLabel; color: Theme.dim2; font.family: Theme.font; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
                }
              }
              Cell { w: view.colW[1]; alignRight: true; txt: tr.modelData.onSpot; dim: !tr.modelData.ok }
              Cell { w: view.colW[2]; alignRight: true; txt: tr.modelData.players; dim: !tr.modelData.ok }
              Cell { w: view.colW[3]; alignRight: true; txt: tr.modelData.seen; dim: !tr.modelData.ok }
              Cell { w: view.colW[4]; alignRight: true; txt: tr.modelData.spots; dim: !tr.modelData.ok }
              Cell { w: view.colW[5]; alignRight: true; txt: tr.modelData.meet; dim: !tr.modelData.ok; hot: tr.modelData.hot }
              Cell { w: view.colW[6]; alignRight: true; txt: tr.modelData.perHour; dim: !tr.modelData.ok }
              Cell {
                w: view.colW[7]
                lead: view.lead
                txt: tr.modelData.ok ? tr.modelData.regular : "-  " + tr.modelData.whyShort
                dim: !tr.modelData.ok || tr.modelData.regular === "-"
              }
            }
          }
        }
        Text {
          visible: view.rows.length === 0
          x: view.pad
          topPadding: 12
          text: "brak postaci"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.body
        }

        // ---------- czas i tempo wybranej postaci
        SecLabel { title: "czas i tempo"; note: view.tempo ? "· " + view.tempo.nick : "" }
        Flow {
          objectName: "spotkania-tempo"
          x: view.pad
          width: parent.width - 2 * view.pad
          topPadding: 14
          bottomPadding: 16
          spacing: 40
          StatBlock { label: "Na spocie od startu"; value: view.tempo ? view.tempo.onSpot : "-"; valueColor: view.tempo && view.tempo.ok ? Theme.fg : Theme.dim2; objectName: "tempo-czas" }
          StatBlock {
            label: "Widziani na tym spocie"; value: view.tempo ? view.tempo.seen : "-"; valueColor: view.tempo && view.tempo.seen !== "-" ? Theme.fg : Theme.dim2
            suffix: view.tempo ? view.tempo.seenSince : ""; objectName: "tempo-widziani"
          }
          StatBlock {
            label: "Spotkań / h"; value: view.tempo ? view.tempo.perHour : "-"; valueColor: view.tempo && view.tempo.perHour !== "-" ? Theme.fg : Theme.dim2
            suffix: view.tempo ? view.tempo.perHourNote : ""; objectName: "tempo-spotkan"
          }
          StatBlock { label: "Exp / h"; value: view.tempo ? view.tempo.expH : "-"; valueColor: view.tempo && view.tempo.expH !== "-" ? Theme.fg : Theme.dim2; objectName: "tempo-exp" }
          StatBlock { label: "Zabicia / h"; value: view.tempo ? view.tempo.zabH : "-"; valueColor: view.tempo && view.tempo.zabH !== "-" ? Theme.fg : Theme.dim2; objectName: "tempo-zab" }
          Text {
            objectName: "tempo-widziani-nicki"
            visible: view.tempo && view.tempo.ok && view.tempo.seenNames.length > 0
            width: parent.width
            wrapMode: Text.Wrap
            text: view.tempo ? "widziani: " + view.tempo.seenNames.join(" · ") : ""
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
          }
          Text {
            visible: view.tempo && view.tempo.ok && view.tempo.seen === "-" && view.tempo.seenWhy !== ""
            text: "widziani: brak danych (" + (view.tempo ? view.tempo.seenWhy : "") + ")"
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
          }
          Text {
            visible: view.tempo && !view.tempo.ok
            topPadding: 16
            text: "brak danych o spotkaniach: " + (view.tempo ? view.tempo.why : "")
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
          }
        }

        // ---------- zmiany spotu dziś
        SecLabel { title: "zmiany spotu · dziś"; note: view.changes.length > 0 ? "· " + view.changes.length : "" }
        Repeater {
          model: view.changes
          delegate: Rectangle {
            id: cr
            required property var modelData
            objectName: "zmiana-spotu"
            width: content.width
            height: 34
            color: "transparent"
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
            Row {
              x: view.pad
              height: parent.height
              spacing: view.gap
              Cell { w: 56; txt: cr.modelData.time; dim: true }
              Cell { w: 120; txt: cr.modelData.nick; strong: true }
              Cell { w: 300; txt: cr.modelData.route }
              Cell { w: 350; txt: cr.modelData.reason + (cr.modelData.repeat > 1 ? " (×" + cr.modelData.repeat + ")" : ""); dim: true }
              Cell { w: 90; txt: cr.modelData.status; tone: cr.modelData.tone }
            }
          }
        }
        Text {
          visible: view.changes.length === 0
          objectName: "zmiany-brak"
          x: view.pad
          topPadding: 12
          bottomPadding: 4
          text: "dziś bez zmian spotu po spotkaniach z graczami"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.small
        }

        // ---------- unikane spoty
        SecLabel { title: "unikane spoty"; note: view.avoided.length > 0 ? "· " + view.avoided.length + " · spot, na którym spotkano gracza, jest omijany przy wyborze nowego" : "" }
        Repeater {
          model: view.avoided
          delegate: Rectangle {
            id: ur
            required property var modelData
            objectName: "unikany-spot"
            width: content.width
            height: 34
            color: "transparent"
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
            Row {
              x: view.pad
              height: parent.height
              spacing: view.gap
              Cell { w: 120; txt: ur.modelData.nick; strong: true }
              Cell { w: 300; txt: ur.modelData.spot + (ur.modelData.map !== "" && ur.modelData.map !== ur.modelData.spot ? "  (" + ur.modelData.map + ")" : "") }
              Cell { w: 190; txt: "przez gracza " + ur.modelData.player; dim: true }
              Cell { w: 150; txt: "jeszcze " + ur.modelData.left; tone: "warn" }
            }
          }
        }
        Text {
          visible: view.avoided.length === 0
          objectName: "unikane-brak"
          x: view.pad
          topPadding: 12
          bottomPadding: 4
          text: "brak unikanych spotów"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.small
        }

        // ---------- granice danych
        Column {
          x: view.pad
          width: parent.width - 2 * view.pad
          topPadding: 22
          spacing: 4
          Repeater {
            model: view.limits
            delegate: Text {
              required property string modelData
              width: parent.width
              wrapMode: Text.Wrap
              text: "· " + modelData
              color: Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.small
            }
          }
        }
      }
    }
  }

  // etykieta bloku: WERSALIKI, notka po prawej od tytułu (jak nagłówki grup w Przeglądzie)
  component SecLabel: Rectangle {
    id: sl
    property string title: ""
    property string note: ""
    width: content.width
    height: 30
    color: Theme.bg2
    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: Theme.line }
    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
    Row {
      x: view.pad
      anchors.verticalCenter: parent.verticalCenter
      spacing: 10
      Text { text: sl.title.toUpperCase(); color: Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.tiny; font.letterSpacing: 1; font.bold: true }
      Text { visible: sl.note !== ""; text: sl.note; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny }
    }
  }

  // komórka tabeli o stałej szerokości; right = wyrównanie do prawej (liczby), hot = wyróżnienie progu (Theme.warn), dim = brak danych
  component Cell: Item {
    id: cell
    property real w: 100
    property string txt: ""
    property bool alignRight: false
    property bool dim: false
    property bool hot: false
    property bool strong: false
    property real lead: 0
    property string tone: ""
    default property alias slot: holder.data
    width: w
    height: parent ? parent.height : 34
    Item { id: holder; anchors.fill: parent }
    Text {
      visible: cell.txt !== ""
      anchors.verticalCenter: parent.verticalCenter
      anchors.left: cell.alignRight ? undefined : parent.left
      anchors.leftMargin: cell.lead
      anchors.right: cell.alignRight ? parent.right : undefined
      width: Math.min(implicitWidth, parent.width)
      text: cell.txt
      elide: Text.ElideRight
      color: cell.tone !== "" ? Theme.tone(cell.tone) : (cell.hot ? Theme.warn : (cell.dim ? Theme.dim2 : Theme.fg2))
      font.family: Theme.font
      font.pixelSize: Theme.body
      font.bold: cell.hot || cell.strong
    }
  }
}
