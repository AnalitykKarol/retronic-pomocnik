pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "OknoModel.js" as Model

// Sekcja Sesja gry (F4b): karta stanu sesji (sway, gra, bot, proxy, podgląd, od kiedy), blok profilu TYLKO DO ODCZYTU (D-F4-1: proxy,
// użytkownik, oczekiwane IP i IP z ostatniego startu z odznaką zgodne/niezgodne, postać, konto, tożsamość, uwagi, błąd/ostrzeżenie profilu),
// ostatnie linie logu startu i akcji oraz guziki: Uruchom grę, Zamknij grę (z potwierdzeniem), Otwórz podgląd. Okno nic nie liczy:
// dane z `okno_api sesja` (odświeżane co 2 s), reguły aktywności i teksty z OknoModel.js, akcje to sesja_gry.py start|zamknij|podglad.
// Główna instancja: tylko wyjaśnienie, bez guzików (startuje ręcznie).
Item {
  id: view

  required property var ctl

  property bool confirming: false

  readonly property var s: ctl.sesjaData
  readonly property bool isMain: ctl.selected !== null && ctl.selected.id === ""
  readonly property string nick: ctl.selected ? Model.nickOf(ctl.selected) : ""
  readonly property var now: ctl.refreshedAt || new Date()
  readonly property var buttons: Model.sessionButtons(s)
  readonly property bool canStop: buttons["gra-zamknij"].enabled
  readonly property var summary: Model.sessionSummary(s)
  readonly property var confirm: Model.closeConfirm(s, nick)
  readonly property var ipBadge: Model.ipBadge(s)
  readonly property var notice: Model.profileNotice(s)
  readonly property var stateRows: Model.stateRows(s, now)
  readonly property var profileRows: Model.profileRows(s)
  readonly property string note: ctl.sesjaNote.id === ctl.selectedId ? ctl.sesjaNote.text : ""
  readonly property string startedHint: Model.startHint(s, ctl.sesjaStarted === ctl.selectedId)
  readonly property string hoverHint: btnStart.hovered ? buttons["gra-start"].hint
                                      : (btnStop.hovered ? buttons["gra-zamknij"].hint : (btnPreview.hovered ? buttons["podglad"].hint : ""))
  readonly property string idleHint: {
    if (isMain) return ""
    if (!buttons["gra-start"].enabled && !Model.sessionAlive(s)) return buttons["gra-start"].hint
    return Model.ipAdvice(s)
  }

  function toneColor(t) { return t === "fg" ? Theme.fg : Theme.tone(t) }

  // Zmiana postaci albo stanu, w którym zamknięcie nie jest już możliwe, unieważnia otwarte potwierdzenie.
  onCanStopChanged: if (!canStop) confirming = false
  Connections {
    target: view.ctl
    function onSelectedIdChanged() { view.confirming = false }
  }

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Sesja gry · " + view.nick
      subtitle: view.isMain ? "główna instancja startuje ręcznie" : "start i zamknięcie gry tej instancji; profil (proxy, IP, konto) tylko do odczytu"
      Chip {
        objectName: "sesja-podsumowanie"
        visible: !view.isMain && view.s !== null
        label: "sesja: " + view.summary.text
        textColor: view.toneColor(view.summary.tone)
      }
    }

    // ---------- główna instancja: wyjaśnienie zamiast guzików
    Item {
      objectName: "sesja-glowna"
      visible: view.isMain
      Layout.fillWidth: true
      Layout.fillHeight: true

      Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 22
        anchors.topMargin: 18
        height: mainCol.implicitHeight + 32
        radius: 10
        color: Theme.sur
        border.width: 1
        border.color: Theme.line

        Column {
          id: mainCol
          anchors.fill: parent
          anchors.margins: 16
          spacing: 8
          Text {
            text: "Główna instancja jest prowadzona ręcznie"
            color: Theme.fg
            font.family: Theme.font
            font.pixelSize: Theme.body
            font.bold: true
          }
          Text {
            width: parent.width
            wrapMode: Text.Wrap
            text: "Startuje i kończy się po staremu (retronic.sh / sesja.sh), nie z okna: ma własny prefiks i nie ma stałego profilu proxy. " +
                  "Okno nie uruchamia i nie zamyka jej gry, więc nie ma tu guzików. Bota tej postaci obsługujesz w pasku bocznym (Stop / Start)."
            color: Theme.fg2
            font.family: Theme.font
            font.pixelSize: Theme.small + 1
          }
          Text {
            visible: view.s !== null
            width: parent.width
            wrapMode: Text.Wrap
            text: "Teraz: sesja " + (view.s && view.s.sesja ? "działa" : "nie działa") + " · gra " + (view.s && view.s.gra ? "działa" : "nie działa")
                  + " · bot " + (view.s && view.s.bot ? "działa" : "stoi")
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small + 1
          }
        }
      }
    }

    // ---------- pozostałe instancje: stan, profil, logi
    Flickable {
      id: flick
      objectName: "sesja-tresc"
      visible: !view.isMain
      Layout.fillWidth: true
      Layout.fillHeight: true
      contentWidth: width
      contentHeight: body.implicitHeight + 36
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

      Text {
        anchors.centerIn: parent
        visible: view.s === null
        text: view.ctl.sesjaError !== "" ? "błąd odczytu sesji: " + view.ctl.sesjaError : "odczyt sesji…"
        color: view.ctl.sesjaError !== "" ? Theme.bad : Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.body
      }

      Column {
        id: body
        visible: view.s !== null
        x: 22
        y: 18
        width: flick.width - 44
        spacing: 14

        RowLayout {
          width: parent.width
          spacing: 14

          // ----- stan sesji
          Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            title: "STAN SESJI"
            Repeater {
              model: view.stateRows
              delegate: KV {
                required property var modelData
                label: modelData.etykieta
                value: modelData.wartosc
                valueColor: view.toneColor(modelData.ton)
                objectName: "stan-" + modelData.klucz
              }
            }
          }

          // ----- profil (tylko odczyt)
          Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            title: "PROFIL · tylko do odczytu"

            Rectangle {
              objectName: "sesja-ip"
              visible: view.s !== null && !view.isMain && (view.s.ip !== null || (view.s.profil !== null && view.s.profil.jest))
              width: parent.width
              height: ipText.implicitHeight + 14
              radius: 6
              color: Theme.alpha(view.toneColor(view.ipBadge.tone), 0.14)
              border.width: 1
              border.color: Theme.alpha(view.toneColor(view.ipBadge.tone), 0.5)
              Text {
                id: ipText
                anchors.fill: parent
                anchors.margins: 7
                text: view.ipBadge.text
                color: view.toneColor(view.ipBadge.tone)
                font.family: Theme.font
                font.pixelSize: Theme.small + 1
                font.bold: true
                wrapMode: Text.Wrap
              }
            }
            Rectangle {
              objectName: "sesja-profil-blad"
              visible: view.notice !== null
              width: parent.width
              height: noticeText.implicitHeight + 14
              radius: 6
              color: Theme.alpha(view.toneColor(view.notice ? view.notice.tone : "dim"), 0.14)
              border.width: 1
              border.color: Theme.alpha(view.toneColor(view.notice ? view.notice.tone : "dim"), 0.5)
              Text {
                id: noticeText
                anchors.fill: parent
                anchors.margins: 7
                text: view.notice ? (view.notice.tone === "bad" ? "Profil: " : "Uwaga: ") + view.notice.text : ""
                color: view.toneColor(view.notice ? view.notice.tone : "dim")
                font.family: Theme.font
                font.pixelSize: Theme.small + 1
                wrapMode: Text.Wrap
              }
            }
            Repeater {
              model: view.profileRows
              delegate: KV {
                required property var modelData
                label: modelData.etykieta
                value: modelData.wartosc
                valueColor: view.toneColor(modelData.ton)
                objectName: "profil-" + modelData.klucz
              }
            }
            Text {
              visible: view.s !== null && !view.s.profil
              width: parent.width
              wrapMode: Text.Wrap
              text: "brak profilu instancji"
              color: Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.small + 1
            }
          }
        }

        // ----- logi
        Card {
          width: parent.width
          title: "OSTATNI START · sway.log" + (view.s && view.s.log_startu_czas ? " · " + Model.clock(new Date(view.s.log_startu_czas * 1000)) : "")
          LogLines { objectName: "log-startu"; lines: view.s ? view.s.log_startu : [] }
        }
        Card {
          width: parent.width
          title: "OSTATNIE AKCJE · " + (view.s && view.s.log_akcji_plik ? String(view.s.log_akcji_plik).split("/").pop() : "brak pliku")
          LogLines { objectName: "log-akcji"; lines: view.s ? view.s.log_akcji : [] }
        }
      }
    }

    // ---------- pasek akcji
    Rectangle {
      visible: !view.isMain
      Layout.fillWidth: true
      Layout.preferredHeight: visible ? Math.max(72, barText.implicitHeight + 28) : 0
      color: Theme.bg2

      Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }

      Column {
        id: barText
        anchors.left: parent.left
        anchors.leftMargin: 22
        anchors.right: actions.left
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        Text {
          objectName: "sesja-wynik"
          width: parent.width
          visible: text !== ""
          text: view.note
          color: view.ctl.sesjaNote.tone === "bad" ? Theme.bad : Theme.ok
          font.family: Theme.font
          font.pixelSize: Theme.body
          font.bold: true
          wrapMode: Text.Wrap
          maximumLineCount: 2
          elide: Text.ElideRight
        }
        Text {
          objectName: "sesja-podpowiedz"
          width: parent.width
          text: view.hoverHint !== "" ? view.hoverHint : (view.startedHint !== "" ? view.startedHint : view.idleHint)
          visible: text !== ""
          color: view.hoverHint !== "" ? Theme.dim : (view.startedHint !== "" ? Theme.cyan : (view.ipBadge.tone === "bad" ? Theme.warn : Theme.dim))
          font.family: Theme.font
          font.pixelSize: Theme.small
          wrapMode: Text.Wrap
          maximumLineCount: 2
          elide: Text.ElideRight
        }
      }

      Row {
        id: actions
        anchors.right: parent.right
        anchors.rightMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        Btn {
          id: btnStart
          objectName: "sesja-uruchom"
          label: "▶ Uruchom grę"
          tone: "ok"
          active: view.buttons["gra-start"].enabled
          busy: view.ctl.isBusy(view.ctl.selectedId)
          onActivated: view.ctl.sessionAction("gra-start")
        }
        Btn {
          id: btnStop
          objectName: "sesja-zamknij"
          label: "■ Zamknij grę"
          tone: "stop"
          active: view.buttons["gra-zamknij"].enabled
          busy: view.ctl.isBusy(view.ctl.selectedId)
          onActivated: view.confirming = true
        }
        Btn {
          id: btnPreview
          objectName: "sesja-podglad"
          label: view.buttons["podglad"].label
          tone: "prim"
          active: view.buttons["podglad"].enabled
          busy: view.ctl.isBusy(view.ctl.selectedId)
          onActivated: view.ctl.sessionAction("podglad")
        }
      }
    }
  }

  // ---------- potwierdzenie "Zamknij grę" (okno nad widokiem)
  Rectangle {
    objectName: "sesja-potwierdzenie"
    anchors.fill: parent
    visible: view.confirming
    color: Theme.alpha(Theme.bg, 0.78)

    MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: view.confirming = false }

    Rectangle {
      anchors.centerIn: parent
      width: Math.min(500, parent.width - 44)
      height: dialogCol.implicitHeight + 40
      radius: 12
      color: Theme.sur
      border.width: 1
      border.color: view.confirm.botRuns ? Theme.warn : Theme.line2

      MouseArea { anchors.fill: parent }       // klik w okno nie zamyka go przez tło

      Column {
        id: dialogCol
        anchors.fill: parent
        anchors.margins: 20
        spacing: 10

        Text {
          objectName: "sesja-potwierdzenie-tytul"
          width: parent.width
          text: view.confirm.title
          color: Theme.fg
          font.family: Theme.font
          font.pixelSize: Theme.title - 2
          font.bold: true
          wrapMode: Text.Wrap
        }
        Repeater {
          model: view.confirm.lines
          delegate: Text {
            required property var modelData
            required property int index
            width: dialogCol.width
            text: modelData
            wrapMode: Text.Wrap
            // druga linia to ostrzeżenie o działającym bocie
            color: index > 0 ? Theme.warn : Theme.fg2
            font.family: Theme.font
            font.pixelSize: Theme.small + 1
            font.bold: index > 0
          }
        }
        Row {
          spacing: 8
          topPadding: 6
          Btn {
            objectName: "sesja-zamknij-potwierdz"
            label: view.confirm.botRuns ? "Tak, zatrzymaj bota i zamknij grę" : "Tak, zamknij grę"
            tone: "stop"
            active: view.canStop
            busy: view.ctl.isBusy(view.ctl.selectedId)
            onActivated: { view.confirming = false; view.ctl.sessionAction("gra-zamknij") }
          }
          Btn {
            objectName: "sesja-zamknij-anuluj"
            label: "Anuluj"
            onActivated: view.confirming = false
          }
        }
      }
    }
  }

  // ---------- małe komponenty widoku
  component Card: Rectangle {
    id: card
    property string title: ""
    default property alias content: inner.data
    implicitHeight: inner.implicitHeight + head.implicitHeight + 36
    radius: 10
    color: Theme.sur
    border.width: 1
    border.color: Theme.line

    Text {
      id: head
      x: 14
      y: 12
      width: parent.width - 28
      text: card.title
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.tiny
      font.letterSpacing: 1
      elide: Text.ElideRight
    }
    Column {
      id: inner
      x: 14
      y: head.y + head.implicitHeight + 10
      width: parent.width - 28
      spacing: 6
    }
  }

  component KV: Item {
    id: kv
    property string label: ""
    property string value: ""
    property color valueColor: Theme.fg
    width: parent ? parent.width : 0
    implicitHeight: Math.max(k.implicitHeight, v.implicitHeight)
    height: implicitHeight

    Text {
      id: k
      width: 128
      text: kv.label
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.small + 1
    }
    Text {
      id: v
      anchors.left: k.right
      anchors.leftMargin: 10
      anchors.right: parent.right
      text: kv.value
      color: kv.valueColor
      font.family: Theme.font
      font.pixelSize: Theme.small + 1
      wrapMode: Text.Wrap
    }
  }

  component LogLines: Column {
    id: log
    property var lines: []
    readonly property var shown: Model.logTail(lines, 6, 170)
    width: parent ? parent.width : 0
    spacing: 2

    Repeater {
      model: log.shown
      delegate: Text {
        required property var modelData
        width: log.width
        text: modelData
        color: Theme.fg2
        font.family: Theme.font
        font.pixelSize: Theme.small
        elide: Text.ElideRight
      }
    }
    Text {
      visible: log.shown.length === 0
      text: "brak wpisów"
      color: Theme.dim2
      font.family: Theme.font
      font.pixelSize: Theme.small
    }
  }
}
